import importlib

from app.extensions import db
from app.models import User


def create_teacher():
    teacher = User(name="Docente Teste", email="docente@senai.br")
    teacher.set_password("Senha-segura-123")
    db.session.add(teacher)
    db.session.commit()
    return teacher


def test_login_redirects_to_dashboard(client, app):
    with app.app_context():
        create_teacher()

    response = client.post(
        "/auth/login",
        data={"email": "docente@senai.br", "password": "Senha-segura-123"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Bem-vindo(a), Docente Teste." in response.data


def test_invalid_password_does_not_authenticate(client, app):
    with app.app_context():
        create_teacher()

    response = client.post(
        "/auth/login",
        data={"email": "docente@senai.br", "password": "senha-incorreta"},
    )

    assert response.status_code == 200
    assert b"E-mail ou senha inv\xc3\xa1lidos." in response.data


def test_dashboard_requires_authentication(client):
    response = client.get("/dashboard")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_password_is_stored_as_a_hash(app):
    with app.app_context():
        teacher = create_teacher()

        assert teacher.password_hash != "Senha-segura-123"
        assert teacher.check_password("Senha-segura-123")
        assert not teacher.check_password("senha-incorreta")


def test_logout_form_contains_csrf_field(client, app):
    with app.app_context():
        teacher = create_teacher()
        teacher_id = teacher.id

    with client.session_transaction() as session:
        session["_user_id"] = str(teacher_id)
        session["_fresh"] = True

    response = client.get("/dashboard")

    assert b'name="csrf_token" value="' in response.data


def test_login_displays_senai_logo(client):
    response = client.get("/auth/login")

    assert response.status_code == 200
    assert b"/static/img/logo_senai.png" in response.data
    image = client.get("/static/img/logo_senai.png")
    assert image.status_code == 200
    assert image.mimetype == "image/png"


def test_create_teacher_command_hashes_password(app):
    result = app.test_cli_runner().invoke(
        args=["create-teacher"],
        input="Docente CLI\ncli@senai.br\nSenha-segura-123\nSenha-segura-123\n",
    )

    assert result.exit_code == 0
    with app.app_context():
        teacher = db.session.scalar(
            db.select(User).where(User.email == "cli@senai.br")
        )
        assert teacher is not None
        assert teacher.check_password("Senha-segura-123")


def test_database_config_uses_postgresql_environment_variables(monkeypatch):
    from app import config

    monkeypatch.setenv("DB_HOST", "db.example.test")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_NAME", "school")
    monkeypatch.setenv("DB_USER", "teacher")
    monkeypatch.setenv("DB_PASSWORD", "p@ss:word/with?chars")

    refreshed_config = importlib.reload(config).Config
    database_url = refreshed_config.SQLALCHEMY_DATABASE_URI

    assert database_url.drivername == "postgresql+psycopg"
    assert database_url.host == "db.example.test"
    assert database_url.port == 5433
    assert database_url.database == "school"
    assert database_url.username == "teacher"
    assert database_url.password == "p@ss:word/with?chars"
