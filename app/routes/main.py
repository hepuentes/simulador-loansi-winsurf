"""
MAIN.PY - Rutas principales (home, dashboard)
==============================================
"""

from flask import render_template, redirect, url_for, session
from functools import wraps

from . import main_bp


def login_required(f):
    """Decorador que requiere autenticación"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("autorizado"):
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function


@main_bp.route("/")
def home():
    """Página principal - Simulador público si no hay sesión, o dashboard si hay sesión"""
    if session.get("autorizado"):
        return redirect(url_for("main.dashboard"))
    
    # Si no está logueado, mostrar simulador público
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
        
    from db_helpers import cargar_configuracion
    
    config = cargar_configuracion()
    lineas_credito = config.get("LINEAS_CREDITO", {})
    
    return render_template(
        "cliente/formulario.html",
        lineas=lineas_credito
    )


@main_bp.route("/simulador-publico")
def simulador_publico():
    """Alias explícito para el simulador público"""
    return home()


@main_bp.route("/dashboard")
@login_required
def dashboard():
    """Dashboard principal según rol del usuario"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers_dashboard import obtener_estadisticas_por_rol
    
    rol = session.get("rol", "asesor")
    username = session.get("username")
    
    # Obtener estadísticas según rol
    stats = obtener_estadisticas_por_rol(rol, username)
    
    # Determinar template según rol
    template_map = {
        "admin": "dashboards/admin_tecnico.html",
        "admin_tecnico": "dashboards/admin_tecnico.html",
        "supervisor": "dashboards/supervisor.html",
        "auditor": "dashboards/auditor.html",
        "gerente": "dashboards/gerente.html",
        "comite_credito": "dashboards/comite_credito.html",
        "asesor": "dashboards/asesor.html"
    }
    
    template = template_map.get(rol, "dashboards/asesor.html")
    
    return render_template(template, 
                         stats=stats, 
                         rol=rol, 
                         username=username,
                         nombre_completo=session.get("nombre_completo", username))


@main_bp.route("/toggle_theme", methods=["POST"])
def toggle_theme():
    """Alternar tema claro/oscuro"""
    from flask import jsonify
    
    current_theme = session.get("theme", "light")
    new_theme = "dark" if current_theme == "light" else "light"
    session["theme"] = new_theme
    
    return jsonify({"theme": new_theme})
