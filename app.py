from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from decorators import login_required
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
db = SQL("sqlite:///finance.db")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/singup")
def register():
    return render_template("register.html")

@app.route("/home")
@login_required
def home():
    return render_template("home.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/register")
def register():
    if request.method == 'GET':
        return render_template("register.html")
    if request.method == 'POST':
        if not request.form.get("username"):
            return apology()
        if not request.form.get("email"):
            return apology()
        if request.form.get("password") != request.form.get("confirm_password"):
            return apology()
        else:
            username = request.form.get("username")
            password = request.form.get("password")
            hash = generate_password_hash(password)
        try:
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)
        except ValueError:
            return apology()
        redirect ("/home")

