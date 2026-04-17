"""
COMITE_ROUTES.PY - Rutas del comité de crédito
===============================================
CORREGIDO: 2026-01-18 - Agregada variable stats para el template
"""

from flask import render_template, request, redirect, url_for, session, jsonify, flash
from functools import wraps
import json
import traceback
from datetime import datetime

from . import comite_bp


def login_required(f):
    """Decorador que requiere autenticación"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("autorizado"):
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function


def requiere_permiso(permiso):
    """Decorador que requiere un permiso específico"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("autorizado"):
                return redirect(url_for("auth.login"))
            
            import sys
            from pathlib import Path
            BASE_DIR = Path(__file__).parent.parent.parent.resolve()
            if str(BASE_DIR) not in sys.path:
                sys.path.insert(0, str(BASE_DIR))
            
            from permisos import tiene_permiso
            
            if not tiene_permiso(permiso):
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({
                        'error': 'Permiso denegado',
                        'code': 'PERMISSION_DENIED'
                    }), 403
                flash("No tienes permiso para acceder a esta función", "error")
                return redirect(url_for("main.dashboard"))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@comite_bp.route("/admin/comite-credito")
@login_required
@requiere_permiso("com_ver_todos")
def comite_credito():
    """Panel del comité de crédito"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers import obtener_casos_comite, cargar_configuracion, cargar_scoring
    from db_helpers_comite import evaluar_criterios_borderline
    
    # Obtener casos por estado
    casos_pendientes = obtener_casos_comite({"estado_comite": "pending"})
    casos_aprobados = obtener_casos_comite({"estado_comite": "approved", "limite": 50})
    casos_rechazados = obtener_casos_comite({"estado_comite": "rejected", "limite": 50})
    
    # Evaluar criterios borderline y calcular tiempo de espera para cada caso pendiente
    ahora = datetime.now()
    for caso in casos_pendientes:
        linea_id = caso.get('linea_credito_id', 5)  # Default LoansiFlex
        evaluacion = evaluar_criterios_borderline(caso, linea_id)
        caso['evaluacion_borderline'] = evaluacion
        caso['alertas_activas'] = evaluacion.get('alertas_activas', [])
        caso['total_alertas'] = evaluacion.get('total_alertas', 0)
        
        # Calcular horas de espera desde que llegó al comité
        fecha_ref = caso.get('fecha_envio_comite') or caso.get('timestamp')
        if fecha_ref:
            try:
                # Parsear timestamp ISO (puede tener timezone)
                ts_str = str(fecha_ref).replace('T', ' ')
                # Remover timezone info para comparar con datetime.now()
                if '+' in ts_str:
                    ts_str = ts_str[:ts_str.index('+')]
                elif ts_str.count('-') > 2:
                    # Formato con timezone negativo como -05:00
                    parts = ts_str.rsplit('-', 1)
                    if ':' in parts[-1] and len(parts[-1]) <= 6:
                        ts_str = parts[0]
                ts_str = ts_str.strip()
                fecha_caso = datetime.fromisoformat(ts_str)
                delta = ahora - fecha_caso
                horas = int(delta.total_seconds() / 3600)
                caso['tiempo_espera_horas'] = max(0, horas)
                caso['alerta_tiempo'] = horas >= 24
            except (ValueError, TypeError) as e:
                print(f"⚠️ Error calculando tiempo espera: {e}")
                caso['tiempo_espera_horas'] = 0
                caso['alerta_tiempo'] = False
        else:
            caso['tiempo_espera_horas'] = 0
            caso['alerta_tiempo'] = False
    
    # Configuración
    config = cargar_configuracion()
    scoring = cargar_scoring()
    
    config_comite = config.get("COMITE_CREDITO", {})
    niveles_riesgo = scoring.get("niveles_riesgo", [])
    
    # =====================================================
    # CRÍTICO: Calcular estadísticas para el template
    # =====================================================
    # Contar casos con alerta (nivel de riesgo alto o muy alto)
    casos_con_alerta = 0
    for caso in casos_pendientes:
        nivel = caso.get('nivel_riesgo', '').lower()
        if 'alto' in nivel or 'critico' in nivel or 'muy alto' in nivel:
            casos_con_alerta += 1
    
    # Contar decisiones de hoy
    hoy = datetime.now().strftime('%Y-%m-%d')
    decisiones_hoy = 0
    for caso in casos_aprobados + casos_rechazados:
        # Usar 'or {}' para manejar casos donde decision_admin es None
        decision = caso.get('decision_admin') or {}
        timestamp = decision.get('timestamp', '')
        if timestamp and timestamp.startswith(hoy):
            decisiones_hoy += 1
    
    stats = {
        'pendientes': len(casos_pendientes),
        'con_alerta': casos_con_alerta,
        'decisiones_hoy': decisiones_hoy,
        'aprobados': len(casos_aprobados),
        'rechazados': len(casos_rechazados)
    }
    
    # Combinar aprobados y rechazados en decisiones_recientes, ordenados por fecha
    decisiones_recientes = casos_aprobados + casos_rechazados
    decisiones_recientes.sort(
        key=lambda c: (c.get('decision_admin') or {}).get('timestamp', ''),
        reverse=True
    )
    
    return render_template(
        "admin/comite_credito.html",
        casos_pendientes=casos_pendientes,
        casos_aprobados=casos_aprobados,
        casos_rechazados=casos_rechazados,
        decisiones_recientes=decisiones_recientes,
        config_comite=config_comite,
        niveles_riesgo=niveles_riesgo,
        stats=stats
    )


@comite_bp.route("/admin/comite-credito/aprobar", methods=["POST"])
@login_required
@requiere_permiso("com_aprobar")
def aprobar_caso():
    """Aprobar un caso del comité"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers import obtener_evaluacion_por_timestamp, actualizar_evaluacion
    from ..utils.timezone import obtener_hora_colombia
    from ..utils.formatting import parse_currency_value
    
    try:
        # Soporte para JSON y Form Data
        if request.is_json:
            data = request.get_json()
            timestamp = data.get("timestamp")
            monto_aprobado = data.get("monto_aprobado")
            nivel_riesgo_ajustado = data.get("nivel_riesgo_ajustado")
            comentario = (data.get("justificacion_modificacion") or data.get("comentario") or "").strip()
        else:
            timestamp = request.form.get("timestamp")
            monto_aprobado = parse_currency_value(request.form.get("monto_aprobado"))
            nivel_riesgo_ajustado = request.form.get("nivel_riesgo_ajustado")
            comentario = request.form.get("comentario", "").strip()
        
        if not timestamp:
            if request.is_json:
                return jsonify({"success": False, "error": "Timestamp no especificado"}), 400
            flash("Timestamp no especificado", "error")
            return redirect(url_for("comite.comite_credito"))
        
        # Obtener evaluación
        evaluacion = obtener_evaluacion_por_timestamp(timestamp)
        
        if not evaluacion:
            if request.is_json:
                return jsonify({"success": False, "error": "Evaluación no encontrada"}), 404
            flash("Evaluación no encontrada", "error")
            return redirect(url_for("comite.comite_credito"))
        
        if evaluacion.get("estado_comite") != "pending":
            if request.is_json:
                return jsonify({"success": False, "error": "Este caso ya fue procesado"}), 400
            flash("Este caso ya fue procesado", "error")
            return redirect(url_for("comite.comite_credito"))
        
        # Actualizar evaluación
        decision_admin = {
            "accion": "aprobar",
            "admin": session.get("username"),
            "timestamp": obtener_hora_colombia().isoformat(),
            "comentario": comentario,
            "monto_aprobado": monto_aprobado or evaluacion.get("monto_solicitado"),
            "nivel_riesgo_ajustado": nivel_riesgo_ajustado
        }
        
        actualizar_evaluacion(timestamp, {
            "estado_comite": "approved",
            "decision_admin": decision_admin,
            "monto_aprobado": monto_aprobado or evaluacion.get("monto_solicitado"),
            "nivel_riesgo_ajustado": nivel_riesgo_ajustado
        })
        
        flash(f"Caso aprobado para {evaluacion.get('nombre_cliente')}", "success")
        return jsonify({"success": True, "message": f"Caso aprobado para {evaluacion.get('nombre_cliente')}"})
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@comite_bp.route("/admin/comite-credito/rechazar", methods=["POST"])
@login_required
@requiere_permiso("com_rechazar")
def rechazar_caso():
    """Rechazar un caso del comité"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers import obtener_evaluacion_por_timestamp, actualizar_evaluacion
    from ..utils.timezone import obtener_hora_colombia
    
    try:
        # Soporte para JSON y Form Data (para compatibilidad con tests y frontend)
        if request.is_json:
            data = request.get_json()
            timestamp = data.get("timestamp")
            motivo = data.get("motivo", "").strip()
        else:
            timestamp = request.form.get("timestamp")
            motivo = request.form.get("motivo", "").strip()
        
        if not timestamp:
            return jsonify({"success": False, "error": "Timestamp no especificado"}), 400
        
        if not motivo:
            return jsonify({"success": False, "error": "El motivo de rechazo es requerido"}), 400
        
        # Obtener evaluación
        evaluacion = obtener_evaluacion_por_timestamp(timestamp)
        
        if not evaluacion:
            return jsonify({"success": False, "error": "Evaluación no encontrada"}), 404
        
        if evaluacion.get("estado_comite") != "pending":
            return jsonify({"success": False, "error": "Este caso ya fue procesado"}), 400
        
        # Actualizar evaluación
        decision_admin = {
            "accion": "rechazar",
            "admin": session.get("username"),
            "timestamp": obtener_hora_colombia().isoformat(),
            "motivo": motivo
        }
        
        actualizar_evaluacion(timestamp, {
            "estado_comite": "rejected",
            "decision_admin": decision_admin
        })
        
        flash(f"Caso rechazado para {evaluacion.get('nombre_cliente')}", "success")
        return jsonify({"success": True, "message": f"Caso rechazado para {evaluacion.get('nombre_cliente')}"})
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# CONFIGURACIÓN DEL COMITÉ POR LÍNEA
# ============================================================================

@comite_bp.route("/admin/comite-credito/config")
@login_required
@requiere_permiso("cfg_comite_ver")
def comite_config_page():
    """Página de configuración del comité por línea de crédito - Arquitectura 2 Niveles"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers_comite import (
        obtener_todas_configs_comite,
        obtener_config_global_comite,
        obtener_criterios_borderline,
        obtener_alertas_dinamicas
    )
    from db_helpers_scoring_linea import obtener_config_scoring_linea
    
    # NIVEL 1: Configuración Global
    config_global = obtener_config_global_comite()
    
    # NIVEL 2: Configuraciones por línea
    configs_lineas = obtener_todas_configs_comite()
    
    # Agregar criterios borderline, alertas dinámicas y umbral de aprobación
    for config in configs_lineas:
        linea_id = config.get("linea_id")
        config["criterios_borderline"] = obtener_criterios_borderline(linea_id)
        config["alertas_dinamicas"] = obtener_alertas_dinamicas(linea_id)
        
        # Obtener umbral de aprobación desde Scoring Interno (fuente única de verdad)
        scoring_config = obtener_config_scoring_linea(linea_id)
        if scoring_config and "config_general" in scoring_config:
            config["puntaje_minimo_aprobacion"] = scoring_config["config_general"].get("puntaje_minimo_aprobacion", 38)
        else:
            config["puntaje_minimo_aprobacion"] = config.get("puntaje_minimo", 38)
    
    return render_template(
        "admin/comite_config.html",
        config_global=config_global,
        configs_lineas=configs_lineas
    )


@comite_bp.route("/api/comite/config/<int:linea_id>", methods=["GET"])
@login_required
@requiere_permiso("cfg_comite_ver")
def api_obtener_config_comite(linea_id):
    """API para obtener configuración de comité de una línea"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers_comite import obtener_config_comite, obtener_miembros_comite
    
    try:
        config = obtener_config_comite(linea_id)
        miembros = obtener_miembros_comite(linea_id)
        
        return jsonify({
            "success": True,
            "config": config,
            "miembros": miembros
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@comite_bp.route("/api/comite/config/<int:linea_id>", methods=["POST"])
@login_required
@requiere_permiso("cfg_comite_editar")
def api_guardar_config_comite(linea_id):
    """API para guardar configuración de comité de una línea"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers_comite import guardar_config_comite
    
    try:
        datos = request.get_json()
        
        if not datos:
            return jsonify({"success": False, "error": "No se recibieron datos"}), 400
        
        resultado = guardar_config_comite(linea_id, datos)
        
        if resultado:
            return jsonify({"success": True, "message": "Configuración guardada"})
        else:
            return jsonify({"success": False, "error": "Error al guardar"}), 500
            
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# API: CONFIGURACIÓN GLOBAL DEL COMITÉ (NIVEL 1)
# ============================================================================

@comite_bp.route("/api/comite/config-global", methods=["GET"])
@login_required
@requiere_permiso("cfg_comite_ver")
def api_obtener_config_global():
    """API para obtener configuración global del comité"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers_comite import obtener_config_global_comite
    
    try:
        config = obtener_config_global_comite()
        return jsonify({"success": True, "config": config})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@comite_bp.route("/api/comite/config-global", methods=["POST"])
@login_required
@requiere_permiso("cfg_comite_editar")
def api_guardar_config_global():
    """API para guardar configuración global del comité"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers_comite import guardar_config_global_comite
    
    try:
        datos = request.get_json()
        if not datos:
            return jsonify({"success": False, "error": "No se recibieron datos"}), 400
        
        resultado = guardar_config_global_comite(datos)
        if resultado:
            return jsonify({"success": True, "message": "Configuración global guardada"})
        else:
            return jsonify({"success": False, "error": "Error al guardar"}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# API: CRITERIOS BORDERLINE POR LÍNEA (NIVEL 2 - SECCIÓN B)
# ============================================================================

@comite_bp.route("/api/comite/criterios-borderline/<int:linea_id>", methods=["GET"])
@login_required
@requiere_permiso("cfg_comite_ver")
def api_obtener_criterios_borderline(linea_id):
    """API para obtener criterios borderline de una línea"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers_comite import obtener_criterios_borderline
    
    try:
        criterios = obtener_criterios_borderline(linea_id)
        return jsonify({"success": True, "criterios": criterios})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@comite_bp.route("/api/comite/criterios-borderline/<int:linea_id>", methods=["POST"])
@login_required
@requiere_permiso("cfg_comite_editar")
def api_guardar_criterios_borderline(linea_id):
    """API para guardar criterios borderline de una línea"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers_comite import guardar_criterios_borderline
    
    try:
        datos = request.get_json()
        if not datos:
            return jsonify({"success": False, "error": "No se recibieron datos"}), 400
        
        resultado = guardar_criterios_borderline(linea_id, datos)
        if resultado:
            return jsonify({"success": True, "message": "Criterios borderline guardados"})
        else:
            return jsonify({"success": False, "error": "Error al guardar"}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# API: SEÑALES DE ALERTA DINÁMICAS POR LÍNEA (NIVEL 2 - SECCIÓN C)
# ============================================================================

@comite_bp.route("/api/comite/alertas-config/<int:linea_id>", methods=["GET"])
@login_required
@requiere_permiso("cfg_comite_ver")
def api_obtener_alertas_config(linea_id):
    """API para obtener configuración de alertas dinámicas de una línea"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers_comite import obtener_alertas_dinamicas
    
    try:
        alertas = obtener_alertas_dinamicas(linea_id)
        return jsonify({"success": True, "alertas": alertas})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@comite_bp.route("/api/comite/alertas-config/<int:linea_id>", methods=["POST"])
@login_required
@requiere_permiso("cfg_comite_editar")
def api_guardar_alertas_config(linea_id):
    """API para guardar configuración de alertas dinámicas de una línea"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers_comite import guardar_alertas_dinamicas
    
    try:
        datos = request.get_json()
        if not datos:
            return jsonify({"success": False, "error": "No se recibieron datos"}), 400
        
        # datos es una lista de alertas: [{criterio_codigo, habilitada, valor_umbral, operador, valor_alerta}]
        alertas_list = datos if isinstance(datos, list) else datos.get("alertas", [])
        
        resultado = guardar_alertas_dinamicas(linea_id, alertas_list)
        if resultado:
            return jsonify({"success": True, "message": "Configuración de alertas guardada"})
        else:
            return jsonify({"success": False, "error": "Error al guardar"}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@comite_bp.route("/api/comite/comentarios/<timestamp>", methods=["GET"])
@login_required
@requiere_permiso("com_ver_todos")
def api_obtener_comentarios(timestamp):
    """API para obtener comentarios de una evaluación"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers_comite import obtener_comentarios_comite
    
    try:
        comentarios = obtener_comentarios_comite(timestamp)
        return jsonify({"success": True, "comentarios": comentarios})
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@comite_bp.route("/api/comite/comentarios/<timestamp>", methods=["POST"])
@login_required
@requiere_permiso("com_ver_todos")
def api_agregar_comentario(timestamp):
    """API para agregar un comentario a una evaluación"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers_comite import agregar_comentario_comite
    
    try:
        datos = request.get_json()
        comentario = datos.get("comentario", "").strip()
        tipo = datos.get("tipo", "nota")
        
        if not comentario:
            return jsonify({"success": False, "error": "Comentario vacío"}), 400
        
        # Obtener usuario_id de la sesión
        from db_helpers import obtener_usuario_por_username
        usuario = obtener_usuario_por_username(session.get("username"))
        
        if not usuario:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 400
        
        comentario_id = agregar_comentario_comite(timestamp, usuario["id"], comentario, tipo)
        
        if comentario_id:
            return jsonify({"success": True, "comentario_id": comentario_id})
        else:
            return jsonify({"success": False, "error": "Error al guardar"}), 500
            
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500