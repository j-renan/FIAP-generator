from flask import Blueprint


bp = Blueprint("students", __name__, url_prefix="/alunos")

from . import routes
