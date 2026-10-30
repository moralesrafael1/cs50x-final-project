from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from decorators import login_required, error
from werkzeug.security import check_password_hash, generate_password_hash
import os
from dotenv import load_dotenv; load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
app.config["SESSION_COOKIE_HTTPONLY"] = True
db = SQL("sqlite:///finance.db")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/home", methods=["GET", "POST"])
@login_required
def home(): 
    return render_template("home.html")

@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    return render_template("upload.html")

@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    return render_template("home.html")

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
        return redirect ("/home")
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
            return error("type your password", 400)
        else:
            username = request.form.get("username")
            password = request.form.get("password")
            hash = generate_password_hash(password)
            email = request.form.get("email")
        try:
            novo_user_id = db.execute("INSERT INTO users (username, hash, email) VALUES (?, ?, ?)", username, hash, email)
            session["user_id"] = novo_user_id
            return redirect ("/home")
        except ValueError:
            return error("Username already in use", 400)
    

