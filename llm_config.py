"""
Meridian — Configuração da LLM (provedor: Groq).

Este módulo guarda APENAS configuração: credenciais, endpoint, limites e prompts.
O Groq usa o formato da API da OpenAI (chat/completions), o mesmo do Gemini
(endpoint compatível), do Ollama e do OpenRouter. Por isso, trocar de provedor
no futuro é questão de mudar LLM_BASE_URL, LLM_MODEL e a chave no .env.
"""
import os

from dotenv import load_dotenv
load_dotenv()


# =====================================================================
# CREDENCIAIS E ENDPOINT
# =====================================================================
LLM_API_KEY = os.environ.get("GROQ_API_KEY")

# URL base do provedor. Para trocar de provedor, sobrescreva no .env:
#     Ollama local -> LLM_BASE_URL=http://localhost:11434/v1
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
LLM_API_URL = f"{LLM_BASE_URL}/chat/completions"

# Modelo padrão do free tier do Groq. A lista de modelos muda com o tempo:
# confira em https://console.groq.com/docs/models e, se preciso, troque no .env.
LLM_MODEL = os.environ.get("LLM_MODEL", "openai/gpt-oss-120b")


# =====================================================================
# PARÂMETROS DE GERAÇÃO
# =====================================================================
LLM_MAX_TOKENS = 2048
LLM_TIMEOUT = 30  
LLM_TEMPERATURE = 0
LLM_JSON_MODE = True
LLM_REASONING_EFFORT = os.environ.get("LLM_REASONING_EFFORT", "low")


def montar_headers():
    """Formato OpenAI: a chave vai no header Authorization como Bearer token."""
    return {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }


# =====================================================================
# PROMPTS
# =====================================================================

# System Prompt definido na arquitetura (texto original preservado).
SYSTEM_PROMPT = (
    "Aja como um auditor financeiro rigoroso. O texto fornecido foi extraído de uma imagem "
    "por um motor OCR e contém ruído visual e erros de digitação comuns (ex: confundir a "
    "letra 'S' com o número '5', ou a letra 'O' com '0'). Diretiva de Reconciliação: Antes "
    "de finalizar o objeto JSON, calcule matematicamente a soma do 'total_price' de todos os "
    "itens extraídos. Compare essa soma com o valor declarado em 'total_amount' no cabeçalho "
    "da fatura. Se a conta não fechar de forma exata, utilize a lógica dedutiva para corrigir "
    "ativamente as falhas do OCR nos itens ou no total. O JSON final deve conter a raiz com "
    "'store_name', 'purchase_date' e 'total_amount', e um array chamado 'items' contendo "
    "'description', 'quantity', 'unit_price' e 'total_price'."
)

# Contrato de saída em forma de MOLDE (placeholders <...>), sem valores reais
FORMATO_SAIDA = """

Formato de saída obrigatório: responda APENAS com um objeto JSON neste formato exato, sem markdown, sem crases e sem nenhum texto antes ou depois:
{
  "store_name": "<nome da loja>",
  "purchase_date": "<AAAA-MM-DD>",
  "total_amount": <número com ponto decimal>,
  "items": [
    {"description": "<texto>", "quantity": <número>, "unit_price": <número>, "total_price": <número>}
  ]
}

Regras do formato:
- Os placeholders <...> indicam apenas o tipo esperado; nunca os copie literalmente.
- Valores numéricos são números JSON com ponto decimal (ex: 12.5), nunca strings como "12,50".
- Se o nome da loja ou a data não estiverem legíveis no texto, use null (sem aspas) em vez de inventar um valor.
- O array "items" deve conter um objeto para cada produto da nota."""


def montar_system_prompt():
    return SYSTEM_PROMPT + FORMATO_SAIDA
