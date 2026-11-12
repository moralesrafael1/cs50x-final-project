import json
import os

import pytesseract
import requests
from cs50 import SQL
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from PIL import Image, UnidentifiedImageError
from werkzeug.security import check_password_hash, generate_password_hash

from functions import (
    consultar_llm,
    error,
    extrair_texto,
    limpar_cercas,
    login_required,
    validar_nota,
)
from llm_config import LLM_API_KEY

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

db = SQL("sqlite:///meridian.db")

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


# =====================================================================
# FILTROS JINJA (camada de apresentação)
# =====================================================================

@app.template_filter("brl")
def formatar_brl(centavos):
    """Centavos inteiros -> texto em reais. Ex: 1250 -> 'R$ 12,50'.

    Só para EXIBIÇÃO: o banco e os cálculos continuam em centavos inteiros.
    Uso no template: {{ nota.total_cents | brl }}
    """
    if centavos is None:
        return "—"
    texto = f"{centavos / 100:,.2f}"  # padrão americano: '1,234.50'
    # Troca os separadores para o padrão brasileiro: '1.234,50'
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


@app.template_filter("data_br")
def formatar_data(iso):
    """'2019-07-10' -> '10/07/2019'. Se vier fora do padrão, devolve como está."""
    try:
        ano, mes, dia = str(iso).split("-")
        return f"{dia}/{mes}/{ano}"
    except ValueError:
        return iso


@app.template_filter("qtd")
def formatar_quantidade(valor):
    """1.0 -> '1' e 0.452 -> '0,452' (produtos a granel)."""
    if valor is None:
        return "—"
    return f"{float(valor):g}".replace(".", ",")


# =====================================================================
# CONSULTAS REUTILIZADAS (Model: só leitura, sempre filtrada por user_id)
# =====================================================================

def usuario_atual():
    # Devolve {username, email} do usuário logado, ou None se ele não existe mais
    # (ex: o banco foi recriado, mas o cookie de sessão antigo continua no navegador).
    
    linhas = db.execute("SELECT username, email FROM users WHERE id = ?", session["user_id"])
    return linhas[0] if linhas else None


def resumo_usuario(user_id):
    # Totais para os cards do painel e para a caixa da página de upload.
    
    resumo = db.execute(
        "SELECT COUNT(*) AS notas, COALESCE(SUM(total_cents), 0) AS total_cents "
        "FROM receipts WHERE user_id = ?",
        user_id,
    )[0]
    resumo["itens"] = db.execute(
        "SELECT COUNT(*) AS n FROM receipt_items "
        "JOIN receipts ON receipts.id = receipt_items.receipt_id "
        "WHERE receipts.user_id = ?",
        user_id,
    )[0]["n"]
    return resumo


def gastos_por_mes(user_id, limite=6):
    # Últimos `limite` meses COM compras, em ordem cronológica, prontos para o gráfico.
    # Agrupa pela data impressa no cupom (purchase_date), não pela data do envio.
    
    meses = db.execute(
        "SELECT strftime('%Y-%m', purchase_date) AS mes, SUM(total_cents) AS total_cents "
        "FROM receipts WHERE user_id = ? "
        "GROUP BY mes ORDER BY mes DESC LIMIT ?",
        user_id, limite,
    )
    meses.reverse()  # do mais antigo para o mais recente, da esquerda para a direita

    maior = max((m["total_cents"] for m in meses), default=0)
    for m in meses:
        ano, mes = m["mes"].split("-")
        m["rotulo"] = f"{MESES[int(mes) - 1]}/{ano[2:]}"          # 'jul/19'
        m["pct"] = round(m["total_cents"] / maior * 100) if maior > 0 else 0
    return meses


# =====================================================================
# ROTAS
# =====================================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/home")
@login_required
def home():
    usuario = usuario_atual()
    if usuario is None:
        session.clear()
        return redirect(url_for("login"))

    user_id = session["user_id"]
    notas = db.execute(
        "SELECT receipts.id, receipts.store_name, receipts.purchase_date, receipts.total_cents, "
        "       COUNT(receipt_items.id) AS itens "
        "FROM receipts "
        "LEFT JOIN receipt_items ON receipt_items.receipt_id = receipts.id "
        "WHERE receipts.user_id = ? "
        "GROUP BY receipts.id "
        "ORDER BY receipts.id DESC",   # ordem de ENVIO: a nota recém-enviada fica no topo
        user_id,
    )
    return render_template(
        "home.html",
        username=usuario["username"],
        resumo=resumo_usuario(user_id),
        meses=gastos_por_mes(user_id),
        notas=notas,
    )


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "GET":
        user_id = session["user_id"]
        # As 3 últimas notas enviadas, cada uma com seus itens, para a coluna da direita.
        recentes = db.execute(
            "SELECT id, store_name, total_cents FROM receipts "
            "WHERE user_id = ? ORDER BY id DESC LIMIT 3",
            user_id,
        )
        for nota in recentes:
            nota["itens"] = db.execute(
                "SELECT description, quantity, total_price_cents FROM receipt_items "
                "WHERE receipt_id = ? ORDER BY id",
                nota["id"],
            )
        return render_template("upload.html", resumo=resumo_usuario(user_id), recentes=recentes)

    #  Passo 1: receber o arquivo (sem salvar em disco)
    arquivo = request.files.get("foto")
    if arquivo is None or arquivo.filename == "":
        return error("Nenhum arquivo foi enviado.", 400)

    #  Passos 1 e 2: memória RAM + Tesseract
    try:
        texto_bruto = extrair_texto(arquivo)
    except (UnidentifiedImageError, Image.DecompressionBombError, ValueError):
        return error("Formato inválido. Envie uma foto JPG, PNG ou WEBP.", 400)
    except pytesseract.TesseractNotFoundError:
        app.logger.exception("Tesseract não instalado no servidor")
        return error("O motor de leitura está indisponível no momento.", 500)

    # Falha rápida: se o OCR não leu quase nada, não vale gastar uma chamada à API.
    if len(texto_bruto.strip()) < 20:
        return error("Não foi possível processar a imagem. Envie uma foto mais nítida.", 422)

    #  Passo 3: chamada semântica à LLM
    if not LLM_API_KEY:
        app.logger.error("GROQ_API_KEY não configurada no .env")
        return error("Serviço de leitura não configurado.", 500)

    try:
        resposta_ia = consultar_llm(texto_bruto)
    except requests.RequestException:
        # Cobre timeout, falha de conexão e status HTTP de erro (raise_for_status).
        app.logger.exception("Falha na chamada à LLM")
        return error("O serviço de leitura está indisponível. Tente novamente em instantes.", 502)

    #  Passo 4: validação (aqui os valores já viram CENTAVOS inteiros)
    try:
        dados = json.loads(limpar_cercas(resposta_ia))
        nota = validar_nota(dados)
    except json.JSONDecodeError:
        return error("Não foi possível processar a imagem. Envie uma foto mais nítida.", 422)
    except (ValueError, TypeError, KeyError):
        return error("A leitura da nota veio incompleta. Envie uma foto mais nítida.", 422)

    #  Passo 5: persistência atômica
    # BEGIN/COMMIT garantem o "tudo ou nada": se o 3º item falhar, a nota e os
    # itens 1 e 2 também são desfeitos pelo ROLLBACK.
    db.execute("BEGIN TRANSACTION")
    try:
        receipt_id = db.execute(
            "INSERT INTO receipts (user_id, store_name, purchase_date, total_cents) VALUES (?, ?, ?, ?)",
            session["user_id"], nota["store_name"], nota["purchase_date"], nota["total_cents"],
        )
        for item in nota["items"]:
            db.execute(
                "INSERT INTO receipt_items (receipt_id, description, quantity, unit_price_cents, total_price_cents) "
                "VALUES (?, ?, ?, ?, ?)",
                receipt_id, item["description"], item["quantity"],
                item["unit_price_cents"], item["total_price_cents"],
            )
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        app.logger.exception("Falha ao gravar a nota")
        return error("Não foi possível salvar a nota. Nada foi gravado, tente novamente.", 500)

    #  Passo 6: Post/Redirect/Get
    # Redirecionar (em vez de renderizar) impede que um F5 reenvie o formulário,
    # o que gravaria a nota duas vezes e gastaria outra chamada à LLM.
    n = len(nota["items"])
    flash(f"Nota de {nota['store_name']} registrada com {n} {'item' if n == 1 else 'itens'}.")
    return redirect(url_for("receipt", receipt_id=receipt_id))


@app.route("/receipt/<int:receipt_id>")
@login_required
def receipt(receipt_id):
    # Proteção contra IDOR: a nota precisa ser do usuário logado, não basta existir.
    linhas = db.execute(
        "SELECT id, store_name, purchase_date, total_cents FROM receipts WHERE id = ? AND user_id = ?",
        receipt_id, session["user_id"],
    )
    if not linhas:
        # 404 e não 403: um 403 confirmaria que a nota existe, só que é de outra pessoa.
        return error("Nota não encontrada.", 404)
    nota = linhas[0]

    itens = db.execute(
        "SELECT description, quantity, unit_price_cents, total_price_cents "
        "FROM receipt_items WHERE receipt_id = ? ORDER BY id",
        receipt_id,
    )
    # Conferência informativa: em centavos inteiros, a soma é exata.
    soma_itens = sum(item["total_price_cents"] for item in itens)
    return render_template(
        "receipt.html",
        nota=nota,
        itens=itens,
        soma_itens=soma_itens,
        diferenca=nota["total_cents"] - soma_itens,
    )


@app.route("/account")
@login_required
def account():
    usuario = usuario_atual()
    if usuario is None:
        session.clear()
        return redirect(url_for("login"))
    return render_template("account.html", usuario=usuario, resumo=resumo_usuario(session["user_id"]))


@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()

    if request.method == 'POST':
        if not request.form.get("email"):
            return error("provide email", 400)
        elif not request.form.get("password"):
            return error("provide password", 400)
        rows = db.execute("SELECT * FROM users WHERE email = ?", request.form.get("email"))
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return error("Wrong username or password! try again", 400)
        session["user_id"] = rows[0]["id"]
        return redirect("/home")
    else:
        return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == 'GET':
        return render_template("register.html")
    if request.method == 'POST':
        if not request.form.get("username"):
            return error("type username", 400)
        if not request.form.get("email"):
            return error("type your email", 400)
        if request.form.get("password") != request.form.get("confirm_password"):
            return error("Passwords do not match", 400)
        else:
            username = request.form.get("username")
            password = request.form.get("password")
            hash = generate_password_hash(password)
            email = request.form.get("email")
        try:
            novo_user_id = db.execute("INSERT INTO users (username, hash, email) VALUES (?, ?, ?)", username, hash, email)
            session["user_id"] = novo_user_id
            return redirect("/home")
        except ValueError:
            return error("Username already in use", 400)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))
