"""
ROUTES - Módulo de rutas de la aplicación Loansi
=================================================

Este módulo contiene todos los blueprints de rutas organizados por dominio.
"""

from flask import Blueprint

# Crear blueprints
auth_bp = Blueprint('auth', __name__)
main_bp = Blueprint('main', __name__)
simulador_bp = Blueprint('simulador', __name__)
scoring_bp = Blueprint('scoring', __name__)
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
comite_bp = Blueprint('comite', __name__)
api_bp = Blueprint('api', __name__, url_prefix='/api')
asesor_bp = Blueprint('asesor', __name__, url_prefix='/asesor')


def register_blueprints(app):
    """
    Registra todos los blueprints en la aplicación Flask.
    
    Args:
        app: Instancia de Flask
    """
    # Importar rutas (esto registra las funciones en los blueprints)
    from . import auth
    from . import main
    from . import simulador
    from . import scoring_routes
    from . import admin_routes
    from . import comite_routes
    from . import api_routes
    from . import asesor_routes
    from .extraccion_routes import extraccion_bp
    from psicometrico import psicometrico_bp
    
    # Registrar blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(simulador_bp)
    app.register_blueprint(scoring_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(comite_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(asesor_bp)
    app.register_blueprint(extraccion_bp)
    app.register_blueprint(psicometrico_bp)
    
    print("✅ Blueprints registrados:")
    print("   - auth: /login, /logout")
    print("   - main: /, /dashboard")
    print("   - simulador: /simulador, /capacidad_pago, /historial_simulaciones")
    print("   - scoring: /scoring")
    print("   - admin: /admin/*")
    print("   - comite: /admin/comite-credito")
    print("   - api: /api/*")
    print("   - asesor: /asesor/*")
    print("   - extraccion: /api/extraccion/*")
    print("   - psicometrico: /psicometrico/*")
