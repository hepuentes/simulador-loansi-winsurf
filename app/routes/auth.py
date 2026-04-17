"""
AUTH.PY - Rutas de autenticación
=================================
"""

from flask import render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash

from . import auth_bp
from ..utils.security import check_rate_limit, record_failed_attempt, clear_attempts
from ..utils.logging import log_security_event


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Página y procesamiento de login"""
    # Importar aquí para evitar importaciones circulares
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers import cargar_configuracion
    
    # Si ya está autenticado, redirigir
    if session.get("autorizado"):
        return redirect(url_for("main.dashboard"))
    
    # Verificar rate limiting
    ip_address = request.remote_addr
    rate_status = check_rate_limit(ip_address)
    
    if rate_status['is_locked']:
        minutos_restantes = rate_status['remaining_time'] // 60
        segundos_restantes = rate_status['remaining_time'] % 60
        flash(
            f"Demasiados intentos fallidos. Intenta de nuevo en {minutos_restantes}:{segundos_restantes:02d}",
            "error"
        )
        return render_template("login.html", locked=True, 
                             remaining_time=rate_status['remaining_time'])
    
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        
        if not username or not password:
            flash("Por favor ingresa usuario y contraseña", "error")
            return render_template("login.html")
        
        # Cargar usuarios
        config = cargar_configuracion()
        usuarios = config.get("USUARIOS", {})
        
        # Verificar credenciales
        if username in usuarios:
            user_data = usuarios[username]
            password_hash = user_data.get("password_hash", "")
            
            if check_password_hash(password_hash, password):
                # Login exitoso
                clear_attempts(ip_address)
                
                session.permanent = True
                session["autorizado"] = True
                session["username"] = username
                session["rol"] = user_data.get("rol", "asesor")
                session["nombre_completo"] = user_data.get("nombre_completo", username)
                
                log_security_event("LOGIN_SUCCESS", user=username, ip=ip_address)
                
                # Redirigir según rol
                if session["rol"] in ["admin", "admin_tecnico"]:
                    return redirect(url_for("admin.admin_panel"))
                elif session["rol"] == "comite_credito":
                    return redirect(url_for("comite.comite_credito"))
                else:
                    return redirect(url_for("main.dashboard"))
        
        # Login fallido
        record_failed_attempt(ip_address)
        log_security_event("LOGIN_FAILED", f"Usuario: {username}", user=username, ip=ip_address)
        
        rate_status = check_rate_limit(ip_address)
        if rate_status['attempts_left'] > 0:
            flash(f"Credenciales incorrectas. Te quedan {rate_status['attempts_left']} intentos.", "error")
        else:
            flash("Demasiados intentos fallidos. Cuenta bloqueada temporalmente.", "error")
        
        return render_template("login.html", 
                             attempts_left=rate_status['attempts_left'],
                             locked=rate_status['is_locked'])
    
    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """Cerrar sesión"""
    username = session.get("username", "anónimo")
    ip_address = request.remote_addr
    
    # Limpiar sesión
    session.clear()
    
    log_security_event("LOGOUT", user=username, ip=ip_address)
    flash("Has cerrado sesión correctamente", "success")
    
    return redirect(url_for("auth.login"))
