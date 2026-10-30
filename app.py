from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from decorators import login_required, error
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
db = SQL("sqlite:///finance.db")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/home", methods=["GET", "POST"])
@login_required
def home(): 
    return render_template("home.html")

@app.route("/login", methods=["GET", "POST"])
def login():
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
            db.execute("INSERT INTO users (username, hash, email) VALUES (?, ?, ?)", username, hash, email)
            return redirect ("/home")
        except ValueError:
            return error("Username already in use", 400)
    

