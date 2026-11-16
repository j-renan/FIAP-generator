from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy import func, select

from . import bp
from .forms import LoginForm
from ..extensions import db
from ..models import User


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = db.session.scalar(
            select(User).where(func.lower(User.email) == email)
        )
        if user and user.is_active and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for("main.dashboard"))

        flash("E-mail ou senha inválidos.", "error")

    return render_template("auth/login.html", form=form)


@bp.post("/logout")
def logout():
    logout_user()
    flash("Você saiu do sistema.", "success")
    return redirect(url_for("auth.login"))
