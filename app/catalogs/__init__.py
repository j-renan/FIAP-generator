from flask import Blueprint


bp = Blueprint("catalogs", __name__, url_prefix="/cadastros")

from . import routes
