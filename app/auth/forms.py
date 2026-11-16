from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length


class LoginForm(FlaskForm):
    email = StringField(
        "E-mail",
        validators=[DataRequired(), Email(), Length(max=254)],
    )
    password = PasswordField("Senha", validators=[DataRequired()])
    submit = SubmitField("Entrar")
