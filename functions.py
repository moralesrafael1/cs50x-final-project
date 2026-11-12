"""
Meridian — Decorators e funções auxiliares.

Organização do arquivo:
  1. DECORATORS          -> envolvem rotas (ex: @login_required)
  2. RESPOSTAS HTTP      -> atalhos para respostas padronizadas (error)
  3. PIPELINE DE OCR     -> funções puras usadas pela rota /upload
"""
import io
import os
from datetime import date, datetime
from functools import wraps

import pytesseract
import requests
from flask import redirect, render_template, session
from PIL import Image, ImageOps

from llm_config import (
    LLM_API_URL,
    LLM_JSON_MODE,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_REASONING_EFFORT,
    LLM_TEMPERATURE,
    LLM_TIMEOUT,
    montar_headers,
    montar_system_prompt,
)


# =====================================================================
# 1. DECORATORS
# =====================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


# =====================================================================
# 2. RESPOSTAS HTTP
# =====================================================================

def error(message, code):
    return render_template("error.html", message=message, code=code), code


# =====================================================================
# 3. PIPELINE DE OCR HÍBRIDO
# =====================================================================

_caminho_tesseract = os.environ.get("TESSERACT_CMD")
if _caminho_tesseract:
    pytesseract.pytesseract.tesseract_cmd = _caminho_tesseract

FORMATOS_PERMITIDOS = {"JPEG", "PNG", "WEBP"}
VALORES_VAZIOS = {"", "null", "none", "n/a"}


def extrair_texto(arquivo):
    # Passos 1 e 2: lê o upload na RAM e roda o Tesseract.
    # Levanta: UnidentifiedImageError, Image.DecompressionBombError, ValueError,
    #         pytesseract.TesseractNotFoundError
    # arquivo.read() devolve os bytes; BytesIO faz esses bytes se comportarem como um arquivo.
    imagem = Image.open(io.BytesIO(arquivo.read()))
    # Zero Trust: o formato é detectado pelos bytes do arquivo, não pelo nome dele.
    if imagem.format not in FORMATOS_PERMITIDOS:
        raise ValueError("Formato de imagem não suportado")

    # Fotos de celular guardam a rotação no EXIF; sem isso o Tesseract lê o cupom "deitado".
    imagem = ImageOps.exif_transpose(imagem)
    # Tons de cinza: menos ruído de cor e OCR mais estável em papel térmico.
    imagem = imagem.convert("L")

    # lang="por" exige o pacote de idioma instalado (por.traineddata na pasta tessdata).
    return pytesseract.image_to_string(imagem, lang="por")


def consultar_llm(texto_bruto):
    #Passo 3: envia APENAS o texto (nunca a imagem) e devolve a resposta textual da IA.
    #Formato OpenAI (chat/completions), usado pelo Groq e por provedores compatíveis.
    #Levanta: requests.RequestException (timeout, conexão, status 4xx/5xx, corpo de resposta que não é JSON)

    payload = {
        "model": LLM_MODEL,
        "max_completion_tokens": LLM_MAX_TOKENS,
        "temperature": LLM_TEMPERATURE,
        # gpt-oss aceita "low", "medium" ou "high" (padrão do Groq: "medium").
        "reasoning_effort": LLM_REASONING_EFFORT,
        "messages": [
            {"role": "system", "content": montar_system_prompt()},
            {
                "role": "user",
                "content": f"Texto extraído pelo OCR:\n<ocr>\n{texto_bruto}\n</ocr>",
            },
        ],
    }
    if LLM_JSON_MODE:
        payload["response_format"] = {"type": "json_object"}

    resposta = requests.post(LLM_API_URL, headers=montar_headers(), json=payload, timeout=LLM_TIMEOUT)
    resposta.raise_for_status()  # status 4xx/5xx (inclusive 429 = limite do free tier) viram HTTPError

    corpo = resposta.json()
    # No formato OpenAI, o texto fica em choices[0].message.content.
    # Se a estrutura vier diferente, devolvemos "" e o json.loads() da rota
    # levanta JSONDecodeError, caindo no tratamento de erro que já existe.
    try:
        return corpo["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return ""


def limpar_cercas(texto):
    #Remove ```json ... ``` caso o modelo desobedeça e envolva o JSON em markdown.
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.strip("`")
        if texto.lower().startswith("json"):
            texto = texto[4:]
    return texto.strip()


def para_centavos(valor):
    # Converte reais em centavos inteiros: 12.5 -> 1250.
    return round(float(valor) * 100)


def validar_nota(dados):
    # Passo 4 (parte 2): confere a ESTRUTURA e os TIPOS do JSON e converte os valores em dinheiro para CENTAVOS inteiros.
    # Devolve um dicionário limpo no formato:
    #    {"store_name": str, "purchase_date": str (AAAA-MM-DD), "total_cents": int,
    #     "items": [{"description": str, "quantity": float,
    #                "unit_price_cents": int, "total_price_cents": int}, ...]}
    # Levanta: ValueError, TypeError, KeyError
    
    if not isinstance(dados, dict):
        raise ValueError("A raiz do JSON não é um objeto")

    for chave in ("total_amount", "items"):
        if chave not in dados:
            raise ValueError(f"Chave obrigatória ausente: {chave}")

    if not isinstance(dados["items"], list) or not dados["items"]:
        raise ValueError("'items' precisa ser uma lista não vazia")

    itens_limpos = []
    for item in dados["items"]:
        if not isinstance(item, dict):
            raise ValueError("Item com formato inválido")

        descricao = str(item.get("description") or "").strip()[:200]
        if descricao.lower() in VALORES_VAZIOS:
            raise ValueError("Item sem descrição")

        quantidade = float(item.get("quantity", 1))
        if quantidade <= 0:
            raise ValueError("Quantidade inválida")

        # Sem checagem de sinal: linhas de desconto no cupom podem ser negativas.
        itens_limpos.append({
            "description": descricao,
            "quantity": quantidade,
            "unit_price_cents": para_centavos(item["unit_price"]),
            "total_price_cents": para_centavos(item["total_price"]),
        })

    # O banco recusa total negativo (CHECK); barrar aqui gera um 422 claro de: ("leitura incompleta") em vez de um 500 genérico na gravação.
    total_centavos = para_centavos(dados["total_amount"])
    if total_centavos < 0:
        raise ValueError("Total negativo")

    # Nome da loja: aceita null de verdade E a string "null" que o modelo às vezes devolve.
    nome_loja = str(dados.get("store_name") or "").strip()[:120]
    if nome_loja.lower() in VALORES_VAZIOS:
        nome_loja = "Estabelecimento desconhecido"

    # A data é obrigatória no banco (NOT NULL). Se vier ilegível, fora do padrão
    # ISO ou null, usamos a data do upload como estimativa.
    # LIMITAÇÃO CONHECIDA: nada registra que essa data foi estimada.
    try:
        data_compra = datetime.strptime(str(dados.get("purchase_date")), "%Y-%m-%d").date().isoformat()
    except (ValueError, TypeError):
        data_compra = date.today().isoformat()

    return {
        "store_name": nome_loja,
        "purchase_date": data_compra,
        "total_cents": total_centavos,
        "items": itens_limpos,
    }
