from flask import Blueprint


bp = Blueprint("fiaps", __name__, url_prefix="/fiaps")

from . import routes
