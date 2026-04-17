from flask import Blueprint

psicometrico_bp = Blueprint(
    'psicometrico',
    __name__,
    template_folder='templates',
    url_prefix='/psicometrico'
)

from . import routes  # noqa: E402
