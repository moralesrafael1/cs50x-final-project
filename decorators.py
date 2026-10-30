from flask import redirect, session, render_template
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function

def error(message, code):
    return render_template("error.html", message=message, code=code), code