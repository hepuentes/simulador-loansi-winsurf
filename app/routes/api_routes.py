"""
API_ROUTES.PY - Rutas de la API REST
=====================================
CORREGIDO: 2026-01-18 - Agregado success:true a endpoints que lo necesitan
"""

from flask import request, jsonify, session
from functools import wraps
import json
import traceback

from . import api_bp


def api_login_required(f):
    """Decorador que requiere autenticación para API"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("autorizado"):
            return jsonify({
                'error': 'No autorizado',
                'code': 'AUTH_REQUIRED'
            }), 401
        return f(*args, **kwargs)
    return decorated_function


def api_requiere_permiso(permiso):
    """Decorador que requiere un permiso específico para API"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("autorizado"):
                return jsonify({
                    'error': 'No autorizado',
                    'code': 'AUTH_REQUIRED'
                }), 401
            
            import sys
            from pathlib import Path
            BASE_DIR = Path(__file__).parent.parent.parent.resolve()
            if str(BASE_DIR) not in sys.path:
                sys.path.insert(0, str(BASE_DIR))
            
            from permisos import tiene_permiso
            
            if not tiene_permiso(permiso):
                return jsonify({
                    'error': 'Permiso denegado',
                    'code': 'PERMISSION_DENIED',
                    'required': permiso
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ============================================================================
# API DE SESIÓN Y CSRF
# ============================================================================

@api_bp.route("/csrf-token", methods=["GET"])
def api_csrf_token():
    """Obtener token CSRF"""
    from flask_wtf.csrf import generate_csrf
    
    return jsonify({
        "csrf_token": generate_csrf()
    })


@api_bp.route("/session-status", methods=["GET"])
def api_session_status():
    """Verificar estado de sesión"""
    if session.get("autorizado"):
        return jsonify({
            "authenticated": True,
            "username": session.get("username"),
            "rol": session.get("rol"),
            "nombre_completo": session.get("nombre_completo")
        })
    return jsonify({"authenticated": False})


# ============================================================================
# API DE CONFIGURACIÓN
# ============================================================================

@api_bp.route("/lineas-config", methods=["GET"])
@api_login_required
def api_lineas_config():
    """Obtener configuración de líneas de crédito"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers import cargar_configuracion
    
    config = cargar_configuracion()
    
    return jsonify({
        "lineas_credito": config.get("LINEAS_CREDITO", {}),
        "costos_asociados": config.get("COSTOS_ASOCIADOS", {})
    })


@api_bp.route("/capacidad-config", methods=["GET"])
@api_login_required
def api_capacidad_config():
    """Obtener configuración de capacidad de pago"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers import cargar_configuracion
    
    config = cargar_configuracion()
    
    return jsonify(config.get("PARAMETROS_CAPACIDAD_PAGO", {}))


# ============================================================================
# API DE COMITÉ
# ============================================================================

@api_bp.route("/comite/pendientes", methods=["GET"])
@api_login_required
@api_requiere_permiso("com_ver_todos")
def api_comite_pendientes():
    """Obtener casos pendientes del comité"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers import obtener_casos_comite
    
    casos = obtener_casos_comite({"estado_comite": "pending"})
    
    return jsonify({
        "success": True,
        "casos": casos,
        "total": len(casos)
    })


@api_bp.route("/detalle_evaluacion/<timestamp>", methods=["GET"])
@api_login_required
def api_detalle_evaluacion(timestamp):
    """Obtener detalle de una evaluación"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers import obtener_evaluacion_por_timestamp
    
    try:
        evaluacion = obtener_evaluacion_por_timestamp(timestamp)
        
        if not evaluacion:
            return jsonify({
                "success": False,
                "error": "Evaluación no encontrada"
            }), 404
        
        # Asegurar que los campos críticos existen
        if 'monto_solicitado' not in evaluacion:
            evaluacion['monto_solicitado'] = 0
        if 'resultado' not in evaluacion:
            evaluacion['resultado'] = {}
        
        return jsonify({
            "success": True,
            "evaluacion": evaluacion
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@api_bp.route("/badge-count", methods=["GET"])
@api_login_required
def api_badge_count():
    """Obtener contadores para badges del navbar"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers import contar_casos_nuevos_asesor, obtener_casos_comite
    
    username = session.get("username")
    rol = session.get("rol")
    
    response = {
        "casos_nuevos": 0,
        "pendientes_comite": 0
    }
    
    # Casos nuevos para el asesor
    if username:
        try:
            response["casos_nuevos"] = contar_casos_nuevos_asesor(username)
        except:
            response["casos_nuevos"] = 0
    
    # Pendientes de comité (para admin y comité)
    if rol in ["admin", "admin_tecnico", "comite_credito"]:
        try:
            casos_pendientes = obtener_casos_comite({"estado_comite": "pending"})
            response["pendientes_comite"] = len(casos_pendientes)
        except:
            response["pendientes_comite"] = 0
    
    return jsonify(response)


# ============================================================================
# API DE USUARIOS
# ============================================================================

@api_bp.route("/usuarios/lista", methods=["GET"])
@api_login_required
@api_requiere_permiso("usr_ver")
def api_usuarios_lista():
    """Obtener lista de usuarios"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers import obtener_usuarios_completos
    
    usuarios = obtener_usuarios_completos()
    
    return jsonify({
        "success": True,
        "usuarios": usuarios,
        "total": len(usuarios)
    })


@api_bp.route("/usuarios/<username>/id", methods=["GET"])
@api_login_required
def api_usuario_id(username):
    """Obtener ID de un usuario por username"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from database import conectar_db
    
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM usuarios WHERE username = ? AND activo = 1", (username,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return jsonify({
                "success": True,
                "id": row[0],
                "username": username
            })
        
        return jsonify({
            "success": False,
            "error": "Usuario no encontrado"
        }), 404
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# API DE SCORING POR LÍNEA
# ============================================================================

@api_bp.route("/scoring/lineas-credito", methods=["GET"])
@api_login_required
def api_scoring_lineas():
    """Obtener líneas de crédito con info de scoring"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    # from app.utils.decorators import no_cache_and_check_session, admin_required, requiere_permiso (ERROR: Module not found)
    
    # from db_helpers import (
    #     obtener_parametros_capacidad, guardar_parametros_capacidad
    # )
    from db_helpers_scoring_linea import (
        obtener_config_scoring_linea, 
        guardar_config_scoring_linea,
        guardar_niveles_riesgo_linea,
        obtener_lineas_credito_scoring,
        guardar_factores_rechazo_linea,
        guardar_criterios_completos_linea,
        copiar_config_scoring
    )
    # from db_helpers_comite import obtener_casos_pendientes_comite (Check if used? It is not used in this function)
    
    try:
        lineas = obtener_lineas_credito_scoring()
        
        # CORRECCIÓN: El JavaScript espera success: true
        return jsonify({
            "success": True,
            "lineas": lineas,
            "total": len(lineas)
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "lineas": []
        })


@api_bp.route("/scoring/linea/<int:linea_id>/config", methods=["GET"])
@api_login_required
def api_scoring_linea_config(linea_id):
    """Obtener configuración de scoring para una línea"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    try:
        from db_helpers_scoring_linea import obtener_config_scoring_linea
        
        config = obtener_config_scoring_linea(linea_id)
        
        return jsonify({
            "success": True,
            "config": config
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        })


@api_bp.route("/scoring/linea/<int:linea_id>/config", methods=["POST"])
@api_login_required
@api_requiere_permiso("cfg_sco_editar")
def api_scoring_linea_guardar(linea_id):
    """Guardar configuración de scoring para una línea"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers_scoring_linea import guardar_config_scoring_linea
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "error": "No se recibieron datos"}), 400
        
        if guardar_config_scoring_linea(linea_id, data):
            return jsonify({
                "success": True,
                "message": "Configuración guardada"
            })
        else:
            return jsonify({"success": False, "error": "Error al guardar configuración"}), 500
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/scoring/linea/<int:linea_id>/niveles-riesgo", methods=["GET"])
@api_login_required
def api_scoring_niveles_riesgo(linea_id):
    """Obtener niveles de riesgo para una línea"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    try:
        from db_helpers_scoring_linea import obtener_niveles_riesgo_linea
        
        niveles = obtener_niveles_riesgo_linea(linea_id)
        
        return jsonify({
            "success": True,
            "niveles": niveles,
            "total": len(niveles)
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "niveles": []
        })


@api_bp.route("/scoring/linea/<int:linea_id>/niveles-riesgo", methods=["POST"])
@api_login_required
@api_requiere_permiso("cfg_sco_editar")
def api_scoring_niveles_guardar(linea_id):
    """Guardar niveles de riesgo para una línea"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers_scoring_linea import guardar_niveles_riesgo_linea
    
    try:
        data = request.get_json()
        
        if not data or 'niveles' not in data:
            return jsonify({"success": False, "error": "Datos de niveles no especificados"}), 400
        
        if guardar_niveles_riesgo_linea(linea_id, data['niveles']):
            return jsonify({
                "success": True,
                "message": "Niveles de riesgo guardados"
            })
        else:
            return jsonify({"success": False, "error": "Error al guardar niveles"}), 500
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# API DE ESTADOS DE CRÉDITO
# ============================================================================

@api_bp.route("/credito/marcar-desembolsado", methods=["POST"])
@api_login_required
@api_requiere_permiso("com_marcar_desembolso")
def api_marcar_desembolsado():
    """Marcar un crédito como desembolsado"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    try:
        from db_helpers_estados import marcar_desembolsado
    except ImportError:
        return jsonify({"success": False, "error": "Módulo de estados no disponible"}), 500
    
    try:
        data = request.get_json()
        
        timestamp = data.get("timestamp")
        comentario = data.get("comentario")
        
        if not timestamp:
            return jsonify({"success": False, "error": "Timestamp no especificado"}), 400
        
        resultado = marcar_desembolsado(
            timestamp, 
            session.get("username"),
            comentario
        )
        
        if resultado['success']:
            return jsonify(resultado)
        else:
            return jsonify(resultado), 400
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/credito/marcar-desistido", methods=["POST"])
@api_login_required
@api_requiere_permiso("com_marcar_desistido")
def api_marcar_desistido():
    """Marcar un crédito como desistido"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    try:
        from db_helpers_estados import marcar_desistido
    except ImportError:
        return jsonify({"success": False, "error": "Módulo de estados no disponible"}), 500
    
    try:
        data = request.get_json()
        
        timestamp = data.get("timestamp")
        motivo = data.get("motivo")
        
        if not timestamp:
            return jsonify({"success": False, "error": "Timestamp no especificado"}), 400
        
        resultado = marcar_desistido(
            timestamp,
            session.get("username"),
            motivo
        )
        
        if resultado['success']:
            return jsonify(resultado)
        else:
            return jsonify(resultado), 400
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/credito/estadisticas-estados", methods=["GET"])
@api_login_required
def api_estadisticas_estados():
    """Obtener estadísticas de estados de crédito"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    try:
        from db_helpers_estados import obtener_estadisticas_estados
        
        estadisticas = obtener_estadisticas_estados()
        
        return jsonify({
            "success": True,
            "estadisticas": estadisticas
        })
        
    except ImportError:
        return jsonify({
            "success": False,
            "error": "Módulo de estados no disponible"
        }), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500





@api_bp.route("/scoring/linea/<int:linea_id>/criterios", methods=["POST"])
@api_login_required
@api_requiere_permiso("admin_panel_acceso")
def guardar_criterios_linea(linea_id):
    """Guarda los criterios de scoring para una línea específica"""
    from db_helpers_scoring_linea import guardar_criterios_completos_linea
    
    try:
        data = request.get_json()
        # El frontend puede mandar 'criterios' o ser una lista directa
        criterios = data.get("criterios", data) if isinstance(data, dict) else data
        
        if guardar_criterios_completos_linea(linea_id, criterios):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Error al guardar criterios"}), 500
            
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/scoring/invalidar-cache", methods=["POST"])
@api_login_required
@api_requiere_permiso("admin_panel_acceso")
def api_invalidar_cache():
    """Invalida el caché de configuración de scoring"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    try:
        from db_helpers_scoring_linea import invalidar_cache_scoring_linea
        from db_helpers import cargar_configuracion # To force reload if needed
        
        # Invalidar cache de scoring
        invalidar_cache_scoring_linea()
        
        return jsonify({
            "success": True, 
            "message": "Caché invalidado correctamente"
        })
            
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/scoring/copiar-config", methods=["POST"])
@api_login_required
@api_requiere_permiso("admin_panel_acceso")
def copiar_configuracion_scoring():
    """Copia la configuración de scoring de una línea a otra"""
    from db_helpers_scoring_linea import copiar_config_scoring
    try:
        data = request.get_json()
        linea_origen_id = data.get("linea_origen_id")
        linea_destino_id = data.get("linea_destino_id")
        incluir_criterios = data.get("incluir_criterios", True)
        incluir_niveles = data.get("incluir_niveles", True)
        incluir_aprobacion = data.get("incluir_aprobacion", True)
        
        if not linea_origen_id or not linea_destino_id:
            return jsonify({"success": False, "error": "IDs de línea requeridos"}), 400
        
        # Validar que al menos una opción esté seleccionada
        if not incluir_criterios and not incluir_niveles and not incluir_aprobacion:
            return jsonify({"success": False, "error": "Seleccione al menos una opción para copiar"}), 400
            
        if copiar_config_scoring(linea_origen_id, linea_destino_id, 
                                 incluir_criterios=incluir_criterios,
                                 incluir_niveles=incluir_niveles,
                                 incluir_aprobacion=incluir_aprobacion):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Error al copiar configuración"}), 500
            
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/scoring/linea/<int:linea_id>/factores-rechazo", methods=["POST"])
@api_login_required
@api_requiere_permiso("admin_panel_acceso")
def guardar_factores_rechazo(linea_id):
    """Guarda los factores de rechazo para una línea específica"""
    try:
        data = request.get_json()
        # El frontend manda {factores: [...]} o [...]
        factores = data.get("factores", data) if isinstance(data, dict) else data

        from db_helpers_scoring_linea import guardar_factores_rechazo_linea

        if guardar_factores_rechazo_linea(linea_id, factores):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Error al guardar factores de rechazo"}), 500
            
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/scoring/linea/<int:linea_id>/criterios-factores-rechazo", methods=["GET"])
@api_login_required
def api_criterios_factores_rechazo(linea_id):
    """
    Obtiene los criterios disponibles para factores de rechazo.
    Incluye: criterios del sistema + criterios de scoring de la línea + opción personalizado.
    """
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    try:
        from criterios_sistema import obtener_criterios_sistema, OPERADORES_TEXTO
        from db_helpers_scoring_linea import obtener_config_scoring_linea
        from db_helpers import cargar_configuracion
        
        # 1. Criterios del sistema (predefinidos)
        criterios_sistema = obtener_criterios_sistema()
        
        # 2. Criterios de scoring de la línea actual
        criterios_scoring = []
        config_linea = obtener_config_scoring_linea(linea_id)
        
        if config_linea and "criterios" in config_linea:
            for criterio_id, criterio_data in config_linea["criterios"].items():
                criterios_scoring.append({
                    "id": criterio_id,
                    "nombre": criterio_data.get("nombre", criterio_id),
                    "tipo": "numerico" if criterio_data.get("tipo_campo") != "select" else "select",
                    "unidad": "puntos",
                    "descripcion": f"Criterio de scoring: {criterio_data.get('nombre', criterio_id)}",
                    "peso": criterio_data.get("peso", 0),
                    "mensaje_sugerido": f"{criterio_data.get('nombre', criterio_id)} {{operador_texto}} {{valor}}"
                })
        
        # 3. Obtener nombre de la línea
        config = cargar_configuracion()
        lineas = config.get("LINEAS_CREDITO", {})
        nombre_linea = "Línea actual"
        for nombre, datos in lineas.items():
            if datos.get("id") == linea_id:
                nombre_linea = nombre
                break
        
        return jsonify({
            "success": True,
            "criterios_sistema": criterios_sistema,
            "criterios_scoring": criterios_scoring,
            "nombre_linea": nombre_linea,
            "operadores": OPERADORES_TEXTO
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/scoring/generar-mensaje-rechazo", methods=["POST"])
@api_login_required
def api_generar_mensaje_rechazo():
    """
    Genera un mensaje de rechazo sugerido basado en el criterio seleccionado.
    """
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    try:
        from criterios_sistema import generar_mensaje_rechazo, obtener_criterio_sistema_por_id
        
        data = request.get_json()
        criterio_id = data.get("criterio_id", "")
        operador = data.get("operador", "<")
        valor = data.get("valor", 0)
        
        # Intentar generar mensaje desde criterio del sistema
        mensaje = generar_mensaje_rechazo(criterio_id, operador, valor)
        
        # Obtener info del criterio para validaciones
        criterio_info = obtener_criterio_sistema_por_id(criterio_id)
        
        return jsonify({
            "success": True,
            "mensaje_sugerido": mensaje,
            "criterio_info": criterio_info
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/debug/session", methods=["GET"])
@api_login_required
@api_requiere_permiso("aud_ver_todos")
def api_debug_session():
    """Endpoint temporal para debugging de sesión"""
    return jsonify(
        {
            "session_keys": list(session.keys()),
            "username": session.get("username"),
            "rol": session.get("rol"),
            "session_id": session.get("_id", "N/A"),
            "permanent": session.permanent,
            "all_session": dict(session),
        }
    )


@api_bp.route("/db_diagnostics", methods=["GET"])
@api_login_required
@api_requiere_permiso("aud_ver_todos")
def api_db_diagnostics():
    """
    Endpoint de diagnóstico para verificar estado de SQLite.
    Solo accesible por admin.
    """
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
        
    try:
        from database import (
            conectar_db,
            verificar_integridad_db,
            listar_tablas,
            contar_registros_tabla
        )
        import sqlite3

        # 1. Verificar conexión
        conn = conectar_db()
        conn.close()

        # 2. Verificar integridad (usando función existente)
        tablas_ok = verificar_integridad_db()

        # 3. Obtener estadísticas de tablas (manual loop)
        tablas = listar_tablas()
        stats = {}
        for tabla in tablas:
            stats[tabla] = contar_registros_tabla(tabla)

        # 4. Verificar WAL mode
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0]
        conn.close()

        return jsonify(
            {
                "status": "ok",
                "database_connection": "success",
                "tables_integrity": tablas_ok,
                "table_stats": stats,
                "journal_mode": journal_mode,
                "python_sqlite_version": sqlite3.version,
                "sqlite_lib_version": sqlite3.sqlite_version,
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify(
            {"status": "error", "error": str(e), "traceback": traceback.format_exc()}
        ), 500


# ============================================================================
# API DE PERMISOS
# ============================================================================

@api_bp.route("/permisos/cache/invalidar", methods=["POST"])
@api_login_required
@api_requiere_permiso("usr_permisos")
def api_permisos_cache_invalidar():
    """Invalidar cache de permisos"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    try:
        from permisos import invalidar_cache_permisos
        invalidar_cache_permisos()
        
        print("🔄 [API] Cache de permisos invalidado")
        
        return jsonify({
            "success": True,
            "message": "Cache de permisos invalidado correctamente"
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/permisos/matriz", methods=["GET"])
@api_login_required
@api_requiere_permiso("usr_permisos")
def api_permisos_matriz():
    """Obtener matriz de permisos por rol"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    try:
        from permisos import obtener_matriz_permisos, obtener_todos_permisos
        
        datos = obtener_matriz_permisos()
        
        response = {"success": True}
        response.update(datos)
        
        return jsonify(response)
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/permisos/protegidos", methods=["GET"])
@api_login_required
@api_requiere_permiso("usr_permisos")
def api_permisos_protegidos():
    """Obtener lista de permisos protegidos"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    try:
        from permisos import obtener_permisos_protegidos
        
        protegidos_dict = obtener_permisos_protegidos()
        # El frontend espera una lista plana, devolvemos los de admin por defecto
        lista_protegidos = protegidos_dict.get('admin', [])
        
        return jsonify({
            "success": True,
            "permisos_protegidos": lista_protegidos
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/permisos/usuario/<int:user_id>", methods=["GET"])
@api_login_required
@api_requiere_permiso("usr_permisos")
def api_permisos_usuario(user_id):
    """Obtener permisos detallados de un usuario"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    try:
        from permisos import obtener_permisos_usuario_detallados
        
        permisos = obtener_permisos_usuario_detallados(user_id)
        
        response = {"success": True}
        if permisos:
            response.update(permisos)
            
        return jsonify(response)
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/permisos/limpiar-overrides", methods=["POST"])
@api_login_required
@api_requiere_permiso("usr_permisos")
def api_permisos_limpiar_overrides():
    """Limpiar overrides de permisos sin efecto"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    try:
        from permisos import limpiar_overrides_sin_efecto
        
        eliminados = limpiar_overrides_sin_efecto()
        
        print(f"🧹 [API] Overrides limpiados: {eliminados}")
        
        return jsonify({
            "success": True,
            "eliminados": eliminados
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# RUTAS DE PERMISOS FALTANTES (MIGRADO DE PERMISOS.PY)
# ============================================================================

@api_bp.route("/permisos/mis-permisos", methods=["GET"])
@api_login_required
def api_mis_permisos():
    """Obtener permisos del usuario actual"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
        
    try:
        from permisos import obtener_permisos_usuario_actual
        
        permisos = obtener_permisos_usuario_actual()
        
        return jsonify({
            "success": True,
            "username": session.get("username"),
            "rol": session.get("rol"),
            "permisos": permisos,
            "total": len(permisos)
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/permisos/verificar/<permiso>", methods=["GET"])
@api_login_required
def api_verificar_permiso(permiso):
    """Verificar si usuario tiene permiso"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    try:
        from permisos import tiene_permiso
        
        return jsonify({
            "success": True,
            "permiso": permiso,
            "tiene": tiene_permiso(permiso)
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/permisos/todos", methods=["GET"])
@api_login_required
@api_requiere_permiso("usr_permisos")
def api_todos_permisos():
    """Obtener todos los permisos del sistema"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
        
    try:
        from permisos import obtener_todos_permisos
        
        datos = obtener_todos_permisos()
        return jsonify(datos)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/permisos/usuario/<int:usuario_id>/agregar", methods=["POST"])
@api_login_required
@api_requiere_permiso("usr_permisos")
def api_agregar_permiso_usuario(usuario_id):
    """Agregar permiso a usuario"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    try:
        from permisos import agregar_permiso_usuario
        
        data = request.get_json()
        if not data or 'permiso' not in data:
            return jsonify({'success': False, 'error': 'Permiso no especificado'}), 400
            
        resultado = agregar_permiso_usuario(
            usuario_id,
            data['permiso'],
            data.get('motivo')
        )
        
        if resultado.get('success'):
            return jsonify(resultado)
        else:
            return jsonify(resultado), 400
            
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/permisos/usuario/<int:usuario_id>/quitar", methods=["POST"])
@api_login_required
@api_requiere_permiso("usr_permisos")
def api_quitar_permiso_usuario(usuario_id):
    """Quitar permiso a usuario"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    try:
        from permisos import quitar_permiso_usuario
        
        data = request.get_json()
        if not data or 'permiso' not in data:
            return jsonify({'success': False, 'error': 'Permiso no especificado'}), 400
            
        resultado = quitar_permiso_usuario(
            usuario_id,
            data['permiso'],
            data.get('motivo')
        )
        
        if resultado.get('success'):
            return jsonify(resultado)
        else:
            return jsonify(resultado), 400
            
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/permisos/usuario/<int:usuario_id>/restaurar", methods=["POST"])
@api_login_required
@api_requiere_permiso("usr_permisos")
def api_restaurar_permiso_usuario(usuario_id):
    """Restaurar permiso de usuario"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    try:
        from permisos import restaurar_permiso_usuario
        
        data = request.get_json()
        if not data or 'permiso' not in data:
            return jsonify({'success': False, 'error': 'Permiso no especificado'}), 400
            
        resultado = restaurar_permiso_usuario(usuario_id, data['permiso'])
        
        if resultado.get('success'):
            return jsonify(resultado)
        else:
            return jsonify(resultado), 400
            
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/permisos/rol/<rol>/agregar", methods=["POST"])
@api_login_required
@api_requiere_permiso("usr_permisos")
def api_agregar_permiso_rol(rol):
    """Agregar permiso a rol"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    try:
        from permisos import agregar_permiso_rol
        
        data = request.get_json()
        if not data or 'permiso' not in data:
            return jsonify({'success': False, 'error': 'Permiso no especificado'}), 400
            
        resultado = agregar_permiso_rol(rol, data['permiso'])
        
        if resultado.get('success'):
            return jsonify(resultado)
        else:
            return jsonify(resultado), 400
            
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/permisos/rol/<rol>/quitar", methods=["POST"])
@api_login_required
@api_requiere_permiso("usr_permisos")
def api_quitar_permiso_rol(rol):
    """Quitar permiso a rol"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    try:
        from permisos import quitar_permiso_rol
        
        data = request.get_json()
        if not data or 'permiso' not in data:
            return jsonify({'success': False, 'error': 'Permiso no especificado'}), 400
            
        resultado = quitar_permiso_rol(rol, data['permiso'])
        
        if resultado.get('success'):
            return jsonify(resultado)
        else:
            return jsonify(resultado), 400
            
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# APIs DE INTERPOLACIÓN DINÁMICA Y DEGRADACIÓN
# ============================================================================

@api_bp.route("/scoring/interpolacion/calcular", methods=["POST"])
@api_login_required
def api_calcular_interpolacion():
    """
    Calcula la tasa y aval interpolados para un score específico.
    
    Body JSON:
        - linea_id: ID de la línea de crédito
        - score: Score del cliente (0-100)
        - forzar_interpolacion: bool (opcional)
    """
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    try:
        from app.services.interpolation_service import calcular_interpolacion
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Datos no proporcionados"}), 400
            
        linea_id = data.get("linea_id")
        score = data.get("score")
        forzar = data.get("forzar_interpolacion", False)
        
        if linea_id is None or score is None:
            return jsonify({"success": False, "error": "linea_id y score son requeridos"}), 400
        
        resultado = calcular_interpolacion(int(linea_id), float(score), forzar)
        
        if not resultado:
            return jsonify({
                "success": False, 
                "error": "No se encontró nivel para el score especificado"
            }), 404
        
        return jsonify({
            "success": True,
            "interpolacion": {
                "score_cliente": resultado.score_cliente,
                "nivel_nombre": resultado.nivel_nombre,
                "nivel_codigo": resultado.nivel_codigo,
                "score_min_nivel": resultado.score_min_nivel,
                "score_max_nivel": resultado.score_max_nivel,
                "factor_posicion": resultado.factor_posicion,
                "tasa_ea": resultado.tasa_ea_interpolada,
                "tasa_nominal_mensual": resultado.tasa_nominal_interpolada,
                "aval_porcentaje": resultado.aval_interpolado,
                "color_nivel": resultado.color_nivel,
                "interpolacion_activa": resultado.interpolacion_activa,
                "desglose": resultado.desglose
            }
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/scoring/interpolacion/completo", methods=["POST"])
@api_login_required
def api_calcular_scoring_completo():
    """
    Calcula el scoring completo con degradaciones e interpolación.
    
    Body JSON:
        - linea_id: ID de la línea de crédito
        - score_base: Score base calculado
        - datos_cliente: {
            monto_mora_telcos: float,
            consultas_30_dias: int,
            meses_desde_mora_pagada: int,
            tiene_historial: bool,
            empleadores_ultimo_anio: int,
            cambios_direccion_12_meses: int
        }
    """
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    try:
        from app.services.interpolation_service import calcular_scoring_completo
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Datos no proporcionados"}), 400
            
        linea_id = data.get("linea_id")
        score_base = data.get("score_base")
        datos_cliente = data.get("datos_cliente", {})
        
        if linea_id is None or score_base is None:
            return jsonify({"success": False, "error": "linea_id y score_base son requeridos"}), 400
        
        resultado = calcular_scoring_completo(int(linea_id), float(score_base), datos_cliente)
        
        return jsonify({
            "success": resultado.get("exito", False),
            **resultado
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/scoring/degradacion/reglas", methods=["GET"])
@api_login_required
def api_obtener_reglas_degradacion():
    """Obtiene las reglas de degradación configuradas."""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    try:
        from app.services.interpolation_service import obtener_reglas_degradacion
        
        linea_id = request.args.get("linea_id", type=int)
        tipo_regla = request.args.get("tipo_regla")
        
        reglas = obtener_reglas_degradacion(linea_id, tipo_regla)
        
        return jsonify({
            "success": True,
            "reglas": reglas
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/scoring/linea/<int:linea_id>/nivel/<int:nivel_id>/interpolacion", methods=["GET", "POST"])
@api_login_required
def api_config_interpolacion_nivel(linea_id, nivel_id):
    """
    GET: Obtiene la configuración de interpolación de un nivel.
    POST: Guarda la configuración de interpolación de un nivel.
    """
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    try:
        from app.services.interpolation_service import (
            obtener_config_interpolacion_nivel,
            guardar_config_interpolacion_nivel
        )
        
        if request.method == "GET":
            config = obtener_config_interpolacion_nivel(nivel_id)
            if not config:
                return jsonify({"success": False, "error": "Nivel no encontrado"}), 404
            return jsonify({"success": True, "config": config})
        
        else:  # POST
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "error": "Datos no proporcionados"}), 400
            
            exito = guardar_config_interpolacion_nivel(nivel_id, data)
            
            if exito:
                return jsonify({"success": True, "message": "Configuración guardada"})
            else:
                return jsonify({"success": False, "error": "Error al guardar"}), 500
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/fuentes-extraccion", methods=["GET"])
@api_login_required
def obtener_fuentes_extraccion():
    """Retorna las fuentes de extracción disponibles para criterios de scoring"""
    try:
        from app.config_extraccion import FUENTES_EXTRACCION
        return jsonify({"success": True, "fuentes": FUENTES_EXTRACCION})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# API DE PROVEEDORES DE IA (CRUD dinámico)
# ============================================================================

import logging as _logging
_ia_logger = _logging.getLogger(__name__)


def _get_db_conn():
    """Retorna conexión SQLite a loansi.db."""
    import sqlite3
    from pathlib import Path
    db_path = str(Path(__file__).parent.parent.parent.resolve() / "loansi.db")
    return sqlite3.connect(db_path)


def _row_to_proveedor(row):
    """Convierte una fila de ia_proveedores a dict, enmascarando API key."""
    api_key = row[4] or ""
    return {
        "id": row[0],
        "nombre": row[1],
        "proveedor_tipo": row[2],
        "modelo": row[3],
        "api_key_masked": ("•" * 16 + api_key[-6:]) if len(api_key) > 6 else ("•" * len(api_key) if api_key else ""),
        "api_key_exists": bool(api_key),
        "url_base": row[5] or "",
        "activo": bool(row[6]),
        "fecha_creacion": row[7] or "",
        "prioridad": row[8] if len(row) > 8 else 0
    }


@api_bp.route("/config/ia/proveedores", methods=["GET"])
@api_login_required
def api_ia_proveedores_list():
    """Lista todos los proveedores de IA configurados."""
    try:
        conn = _get_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre, proveedor_tipo, modelo, api_key, url_base, activo, fecha_creacion, prioridad FROM ia_proveedores ORDER BY prioridad ASC, activo DESC, id ASC")
        proveedores = [_row_to_proveedor(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({"success": True, "proveedores": proveedores})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/config/ia/proveedores", methods=["POST"])
@api_login_required
def api_ia_proveedores_create():
    """Crea un nuevo proveedor de IA."""
    try:
        if session.get("rol") != "admin":
            return jsonify({"success": False, "error": "Requiere rol administrador"}), 403

        data = request.get_json()
        if not data or not data.get("nombre") or not data.get("proveedor_tipo"):
            return jsonify({"success": False, "error": "Nombre y tipo son obligatorios"}), 400

        conn = _get_db_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ia_proveedores (nombre, proveedor_tipo, modelo, api_key, url_base, activo)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (
            data["nombre"].strip(),
            data["proveedor_tipo"].strip(),
            data.get("modelo", "").strip(),
            data.get("api_key", "").strip(),
            data.get("url_base", "").strip()
        ))
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()

        _ia_logger.info(f"Proveedor IA creado: id={new_id}, nombre={data['nombre']}")
        return jsonify({"success": True, "id": new_id, "message": "Proveedor creado"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/config/ia/proveedores/<int:prov_id>", methods=["PUT"])
@api_login_required
def api_ia_proveedores_update(prov_id):
    """Edita un proveedor de IA existente."""
    try:
        if session.get("rol") != "admin":
            return jsonify({"success": False, "error": "Requiere rol administrador"}), 403

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Datos no proporcionados"}), 400

        conn = _get_db_conn()
        cursor = conn.cursor()

        # Verificar que existe
        cursor.execute("SELECT id, api_key FROM ia_proveedores WHERE id = ?", (prov_id,))
        existing = cursor.fetchone()
        if not existing:
            conn.close()
            return jsonify({"success": False, "error": "Proveedor no encontrado"}), 404

        # Si api_key viene vacía, mantener la existente
        new_api_key = data.get("api_key", "").strip()
        if not new_api_key:
            new_api_key = existing[1] or ""

        cursor.execute("""
            UPDATE ia_proveedores
            SET nombre = ?, proveedor_tipo = ?, modelo = ?, api_key = ?, url_base = ?
            WHERE id = ?
        """, (
            data.get("nombre", "").strip(),
            data.get("proveedor_tipo", "").strip(),
            data.get("modelo", "").strip(),
            new_api_key,
            data.get("url_base", "").strip(),
            prov_id
        ))
        conn.commit()
        conn.close()

        _ia_logger.info(f"Proveedor IA actualizado: id={prov_id}")
        return jsonify({"success": True, "message": "Proveedor actualizado"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/config/ia/proveedores/<int:prov_id>", methods=["DELETE"])
@api_login_required
def api_ia_proveedores_delete(prov_id):
    """Elimina un proveedor de IA."""
    try:
        if session.get("rol") != "admin":
            return jsonify({"success": False, "error": "Requiere rol administrador"}), 403

        conn = _get_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT activo FROM ia_proveedores WHERE id = ?", (prov_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({"success": False, "error": "Proveedor no encontrado"}), 404

        era_activo = bool(row[0])
        cursor.execute("DELETE FROM ia_proveedores WHERE id = ?", (prov_id,))
        conn.commit()
        conn.close()

        _ia_logger.info(f"Proveedor IA eliminado: id={prov_id}")
        return jsonify({"success": True, "message": "Proveedor eliminado"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/config/ia/proveedores/<int:prov_id>/activar", methods=["POST"])
@api_login_required
def api_ia_proveedores_activar(prov_id):
    """Activa un proveedor (desactiva todos los demás)."""
    try:
        if session.get("rol") != "admin":
            return jsonify({"success": False, "error": "Requiere rol administrador"}), 403

        conn = _get_db_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM ia_proveedores WHERE id = ?", (prov_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"success": False, "error": "Proveedor no encontrado"}), 404

        # Desactivar todos y activar el seleccionado
        cursor.execute("UPDATE ia_proveedores SET activo = 0")
        cursor.execute("UPDATE ia_proveedores SET activo = 1 WHERE id = ?", (prov_id,))
        conn.commit()
        conn.close()

        _ia_logger.info(f"Proveedor IA activado: id={prov_id}")
        return jsonify({"success": True, "message": "Proveedor activado"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/config/ia/proveedores/prioridades", methods=["POST"])
@api_login_required
def api_ia_proveedores_prioridades():
    """Actualiza el orden de prioridad de los proveedores para failover."""
    try:
        if session.get("rol") != "admin":
            return jsonify({"success": False, "error": "Requiere rol administrador"}), 403

        data = request.get_json()
        orden = data.get("orden", [])  # Lista de IDs en orden de prioridad
        if not orden:
            return jsonify({"success": False, "error": "Lista de orden vacía"}), 400

        conn = _get_db_conn()
        cursor = conn.cursor()
        for idx, prov_id in enumerate(orden, start=1):
            cursor.execute(
                "UPDATE ia_proveedores SET prioridad = ? WHERE id = ?",
                (idx, prov_id)
            )
        conn.commit()
        conn.close()

        _ia_logger.info(f"Prioridades actualizadas: {orden}")
        return jsonify({"success": True, "message": "Orden de prioridad actualizado"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/config/ia/proveedores/<int:prov_id>/test", methods=["POST"])
@api_login_required
def api_ia_proveedores_test(prov_id):
    """Prueba conexión con un proveedor específico."""
    try:
        if session.get("rol") != "admin":
            return jsonify({"success": False, "error": "Requiere rol administrador"}), 403

        conn = _get_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre, proveedor_tipo, modelo, api_key, url_base FROM ia_proveedores WHERE id = ?", (prov_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({"success": False, "error": "Proveedor no encontrado"}), 404

        nombre, tipo, modelo, api_key, url_base = row[1], row[2], row[3], row[4], row[5]

        if tipo == "anthropic":
            try:
                import anthropic
            except ImportError:
                return jsonify({"success": False, "error": "Librería 'anthropic' no instalada. Ejecuta: pip install anthropic"})

            client = anthropic.Anthropic(api_key=api_key)
            respuesta = client.messages.create(
                model=modelo,
                max_tokens=10,
                messages=[{"role": "user", "content": "Responde solo: OK"}],
                timeout=15.0
            )
            texto = respuesta.content[0].text.strip()

        elif tipo in ("openai", "openai_compatible"):
            try:
                from openai import OpenAI
            except ImportError:
                return jsonify({"success": False, "error": "Librería 'openai' no instalada. Ejecuta: pip install openai"})

            client_kwargs = {"api_key": api_key or "not-needed"}
            if url_base:
                client_kwargs["base_url"] = url_base
            client = OpenAI(**client_kwargs)
            respuesta = client.chat.completions.create(
                model=modelo,
                max_tokens=10,
                messages=[{"role": "user", "content": "Responde solo: OK"}],
                timeout=15.0
            )
            texto = (respuesta.choices[0].message.content or "(respuesta vacía)").strip()

        elif tipo == "gemini":
            try:
                from openai import OpenAI
            except ImportError:
                return jsonify({"success": False, "error": "Librería 'openai' no instalada. Ejecuta: pip install openai"})

            base = url_base or "https://generativelanguage.googleapis.com/v1beta/openai/"
            client = OpenAI(api_key=api_key, base_url=base)
            respuesta = client.chat.completions.create(
                model=modelo,
                max_tokens=50,
                messages=[{"role": "user", "content": "Responde solo: OK"}],
                timeout=15.0
            )
            texto = (respuesta.choices[0].message.content or "(respuesta vacía)").strip()

        else:
            return jsonify({"success": False, "error": f"Tipo '{tipo}' no soportado"})

        return jsonify({
            "success": True,
            "nombre": nombre,
            "modelo": modelo,
            "proveedor_tipo": tipo,
            "respuesta": texto
        })

    except Exception as e:
        error_msg = str(e)
        _ia_logger.error(f"Error test IA (prov {prov_id}): {error_msg[:200]}")
        return jsonify({"success": False, "error": error_msg})
