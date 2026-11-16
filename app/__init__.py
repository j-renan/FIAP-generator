import os

from flask import Flask

from .config import Config
from .extensions import csrf, db, login_manager, migrate
from .models import User


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("Configure SECRET_KEY antes de iniciar a aplicação.")

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Entre com sua conta para continuar."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    from .auth import bp as auth_bp
    from .catalogs import bp as catalogs_bp
    from .fiaps import bp as fiaps_bp
    from .main import bp as main_bp
    from .students import bp as students_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(catalogs_bp)
    app.register_blueprint(fiaps_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(students_bp)

    from .cli import register_commands

    register_commands(app)

    return app
