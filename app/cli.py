import click
from email_validator import EmailNotValidError, validate_email
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import User
from .services import cleanup_expired_previews


def register_commands(app):
    @app.cli.command("create-teacher")
    @click.option("--name", prompt="Nome completo")
    @click.option("--email", prompt="E-mail")
    def create_teacher(name, email):
        """Create a teacher account for initial or administrative access."""
        name = name.strip()
        if not name:
            raise click.ClickException("O nome do docente não pode ficar vazio.")

        try:
            normalized_email = validate_email(
                email.strip(), check_deliverability=False
            ).normalized.lower()
        except EmailNotValidError as error:
            raise click.ClickException(f"E-mail inválido: {error}") from error

        if db.session.query(User.id).filter_by(email=normalized_email).first():
            raise click.ClickException("Já existe um docente com esse e-mail.")

        password = click.prompt(
            "Senha (mínimo de 12 caracteres)",
            hide_input=True,
            confirmation_prompt=True,
        )
        if len(password) < 12:
            raise click.ClickException("A senha deve ter pelo menos 12 caracteres.")

        teacher = User(name=name, email=normalized_email)
        teacher.set_password(password)
        db.session.add(teacher)

        try:
            db.session.commit()
        except IntegrityError as error:
            db.session.rollback()
            raise click.ClickException(
                "Não foi possível criar o docente; verifique se o e-mail já está cadastrado."
            ) from error

        click.echo(f"Docente {teacher.email} criado com sucesso.")

    @app.cli.command("cleanup-expired-previews")
    @app.cli.command("cleanup-student-imports")
    def cleanup_expired_previews_command():
        """Delete expired temporary import and FIAP previews."""
        imports, fiaps = cleanup_expired_previews()
        click.echo(
            f"{imports} prévias de importação e {fiaps} prévias de FIAP removidas."
        )
