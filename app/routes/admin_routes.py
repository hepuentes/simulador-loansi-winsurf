"""
ADMIN_ROUTES.PY - Rutas de administración
==========================================
CORREGIDO: 2026-01-18 - Agregadas rutas /admin/seguros y /admin/usuario/eliminar
"""

from flask import render_template, request, redirect, url_for, session, jsonify, flash
from functools import wraps
import json
import traceback

from . import admin_bp


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


def tiene_alguno_de(permisos_lista):
    """Verifica si el usuario tiene al menos uno de los permisos de la lista"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from permisos import tiene_permiso
    
    for permiso in permisos_lista:
        if tiene_permiso(permiso):
            return True
    return False


def requiere_rol(*roles_permitidos):
    """Decorador que requiere uno de los roles especificados"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("autorizado"):
                return redirect(url_for("auth.login"))
            
            rol_actual = session.get("rol", "asesor")
            if rol_actual not in roles_permitidos:
                flash("No tienes permiso para acceder a esta sección", "error")
                return redirect(url_for("main.dashboard"))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@admin_bp.route("")
@login_required
@requiere_permiso("admin_panel_acceso")
def admin_panel():
    """Panel principal de administración"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import cargar_configuracion, cargar_scoring, obtener_usuarios_completos
    from db_helpers_scoring_linea import obtener_lineas_credito_scoring

    config = cargar_configuracion()
    scoring = cargar_scoring()
    usuarios_lista = obtener_usuarios_completos()
    
    # Convertir lista a diccionario indexado por username (formato esperado por template)
    usuarios = {u['username']: u for u in usuarios_lista}

    # Cargar líneas de crédito y FILTRAR solo las válidas
    all_lineas_credito = config.get("LINEAS_CREDITO", {})
    
    # Filtrar líneas de crédito válidas (con campos requeridos)
    lineas_credito = {}
    for nombre, datos in all_lineas_credito.items():
        # Validar que sea un dict y tenga campos mínimos
        if isinstance(datos, dict) and datos.get("monto_min") is not None:
            lineas_credito[nombre] = datos
        else:
            # Log líneas inválidas para debugging
            print(f"⚠️ Línea de crédito '{nombre}' ignorada - datos incompletos o inválidos")
    
    costos_asociados = config.get("COSTOS_ASOCIADOS", {})
    parametros_capacidad = config.get("PARAMETROS_CAPACIDAD_PAGO", {})
    config_comite = config.get("COMITE_CREDITO", {})
    
    # Obtener configuración de seguros
    seguros_config = config.get("SEGUROS", {})
    seguro_vida = seguros_config.get("SEGURO_VIDA", [])

    # Obtener líneas con info de scoring
    lineas_scoring = obtener_lineas_credito_scoring()
    
    # Variables para el template admin.html
    scoring_criterios = scoring.get("criterios", {})
    scoring_secciones = scoring.get("secciones", [])
    
    # Preparar scoring_json para JavaScript
    scoring_json = {
        "criterios": scoring_criterios,
        "secciones": scoring_secciones,
        "niveles_riesgo": scoring.get("niveles_riesgo", []),
        "factores_rechazo_automatico": scoring.get("factores_rechazo_automatico", []),
        "puntaje_minimo_aprobacion": scoring.get("puntaje_minimo_aprobacion", 17),
        "dti_maximo": scoring.get("dti_maximo", 40),
        "umbral_mora_telcos_rechazo": scoring.get("umbral_mora_telcos_rechazo", 200000)
    }

    return render_template(
        "admin/admin.html",
        lineas_credito=lineas_credito,
        lineas_scoring=lineas_scoring,
        costos_asociados=costos_asociados,
        usuarios=usuarios,
        parametros_capacidad=parametros_capacidad,
        config_comite=config_comite,
        scoring=scoring,
        scoring_json=scoring_json,
        scoring_criterios=scoring_criterios,
        scoring_secciones=scoring_secciones,
        seguro_vida=seguro_vida
    )


# ============================================================================
# RUTAS DE USUARIOS
# ============================================================================

@admin_bp.route("/usuario/nuevo", methods=["POST"])
@login_required
@requiere_permiso("usr_crear")
def crear_usuario():
    """Crear nuevo usuario"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import crear_usuario as db_crear_usuario
    from werkzeug.security import generate_password_hash

    try:
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        rol = request.form.get("rol", "asesor")
        nombre_completo = request.form.get("nombre_completo", "").strip()

        if not username or not password:
            flash("Usuario y contraseña son requeridos", "error")
            return redirect(url_for("admin.admin_panel") + "#Usuarios")

        password_hash = generate_password_hash(password)

        if db_crear_usuario(username, password_hash, rol, nombre_completo):
            flash(f"Usuario '{username}' creado exitosamente", "success")
        else:
            flash(f"El usuario '{username}' ya existe", "error")

    except Exception as e:
        flash(f"Error al crear usuario: {str(e)}", "error")

    return redirect(url_for("admin.admin_panel") + "#Usuarios")


@admin_bp.route("/usuario/cambiar-password", methods=["POST"])
@login_required
@requiere_permiso("usr_password")
def cambiar_password():
    """Cambiar contraseña de usuario"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from database import conectar_db
    from werkzeug.security import generate_password_hash

    try:
        username = request.form.get("username")
        new_password = request.form.get("new_password")

        if not username or not new_password:
            flash("Usuario y nueva contraseña son requeridos", "error")
            return redirect(url_for("admin.admin_panel") + "#Usuarios")

        # Actualizar en SQLite
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE usuarios SET password_hash = ? WHERE username = ?",
            (generate_password_hash(new_password), username)
        )
        conn.commit()
        conn.close()

        flash(f"Contraseña de '{username}' actualizada", "success")

    except Exception as e:
        flash(f"Error al cambiar contraseña: {str(e)}", "error")

    return redirect(url_for("admin.admin_panel") + "#Usuarios")


@admin_bp.route("/usuario/eliminar", methods=["POST"])
@login_required
@requiere_permiso("usr_eliminar")
def eliminar_usuario():
    """Eliminar usuario (soft delete)"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import eliminar_usuario_db

    try:
        username = request.form.get("username")

        if not username:
            flash("Usuario no especificado", "error")
            return redirect(url_for("admin.admin_panel") + "#Usuarios")

        if username == "admin":
            flash("No se puede eliminar el usuario admin", "error")
            return redirect(url_for("admin.admin_panel") + "#Usuarios")

        if username == session.get("username"):
            flash("No puedes eliminarte a ti mismo", "error")
            return redirect(url_for("admin.admin_panel") + "#Usuarios")

        if eliminar_usuario_db(username):
            flash(f"Usuario '{username}' eliminado correctamente", "success")
        else:
            flash(f"Usuario '{username}' no encontrado o ya está inactivo", "warning")

    except Exception as e:
        traceback.print_exc()
        flash(f"Error al eliminar usuario: {str(e)}", "error")

    return redirect(url_for("admin.admin_panel") + "#Usuarios")


# ============================================================================
# RUTAS DE SEGUROS
# ============================================================================

@admin_bp.route("/seguros", methods=["POST"])
@login_required
def actualizar_seguros():
    """Actualizar configuración de seguros"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    # Verificar permisos
    if not tiene_alguno_de(["cfg_seguros_editar", "cfg_tasas_editar"]):
        flash("No tienes permiso para editar seguros", "warning")
        return redirect(url_for("admin.admin_panel"))
    
    from db_helpers import cargar_configuracion, guardar_configuracion
    
    try:
        # Obtener todos los rangos del formulario
        rangos_nuevos = []
        i = 0
        
        while True:
            edad_min = request.form.get(f"edad_min_{i}")
            edad_max = request.form.get(f"edad_max_{i}")
            costo = request.form.get(f"costo_{i}")
            descripcion = request.form.get(f"descripcion_{i}")
            
            if not edad_min:  # No hay más rangos
                break
            
            try:
                edad_min = int(edad_min)
                edad_max = int(edad_max)
                # Limpiar formato de moneda
                costo_str = costo.replace(".", "").replace(",", "").replace("$", "").strip()
                costo = int(float(costo_str)) if costo_str else 0
                
                if edad_min < 18 or edad_max > 120:
                    flash("Las edades deben estar entre 18 y 120 años", "error")
                    return redirect(url_for("admin.admin_panel") + "#Seguros")
                
                if edad_min >= edad_max:
                    flash("La edad mínima debe ser menor que la edad máxima", "error")
                    return redirect(url_for("admin.admin_panel") + "#Seguros")
                
                if costo < 0:
                    flash("El costo no puede ser negativo", "error")
                    return redirect(url_for("admin.admin_panel") + "#Seguros")
                
                rangos_nuevos.append({
                    "id": i + 1,
                    "edad_min": edad_min,
                    "edad_max": edad_max,
                    "costo": costo,
                    "descripcion": descripcion or f"{edad_min} a {edad_max} años"
                })
                
            except ValueError as ve:
                flash(f"Error en rango {i+1}: valores inválidos - {str(ve)}", "error")
                return redirect(url_for("admin.admin_panel") + "#Seguros")
            
            i += 1
        
        if not rangos_nuevos:
            flash("Debe haber al menos un rango de seguro", "error")
            return redirect(url_for("admin.admin_panel") + "#Seguros")
        
        # Ordenar por edad_min
        rangos_nuevos.sort(key=lambda x: x["edad_min"])
        
        # Validar que no haya solapamientos
        for j in range(len(rangos_nuevos) - 1):
            if rangos_nuevos[j]["edad_max"] >= rangos_nuevos[j + 1]["edad_min"]:
                flash("Los rangos de edad no pueden solaparse", "error")
                return redirect(url_for("admin.admin_panel") + "#Seguros")
        
        # Guardar en configuración
        config = cargar_configuracion()
        config["SEGUROS"] = {"SEGURO_VIDA": rangos_nuevos}
        guardar_configuracion(config)
        
        flash("Configuración de seguros actualizada correctamente", "success")
        
    except Exception as e:
        traceback.print_exc()
        flash(f"Error al actualizar seguros: {str(e)}", "error")
    
    return redirect(url_for("admin.admin_panel") + "#Seguros")


# ============================================================================
# RUTAS DE HISTORIAL DE EVALUACIONES
# ============================================================================

@admin_bp.route("/historial-evaluaciones")
@login_required
@requiere_permiso("sco_hist_todos")
def historial_evaluaciones():
    """Historial de todas las evaluaciones"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import cargar_evaluaciones

    evaluaciones = cargar_evaluaciones()

    # Obtener filtros de la URL
    filtros = {
        'asesor': request.args.get('asesor', ''),
        'desde': request.args.get('desde', ''),
        'hasta': request.args.get('hasta', ''),
        'resultado': request.args.get('resultado', '')
    }

    # Obtener lista de asesores únicos para el filtro
    asesores_disponibles = list(set(e.get('asesor', '') for e in evaluaciones if e.get('asesor')))
    asesores_disponibles.sort()
    
    # Calcular estadísticas para las tarjetas
    total = len(evaluaciones)
    aprobados = sum(1 for e in evaluaciones if e.get('resultado', {}).get('aprobado', False))
    rechazados = total - aprobados
    tasa_aprobacion = round((aprobados / total * 100) if total > 0 else 0)
    
    stats = {
        'total': total,
        'aprobados': aprobados,
        'rechazados': rechazados,
        'tasa_aprobacion': tasa_aprobacion
    }
    
    # Paginación
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages
    }

    return render_template(
        "admin/historial_evaluaciones.html",
        evaluaciones=evaluaciones,
        filtros=filtros,
        asesores=asesores_disponibles,
        asesores_disponibles=asesores_disponibles,
        stats=stats,
        pagination=pagination
    )


# ============================================================================
# RUTAS DE ASIGNACIONES DE EQUIPO
# ============================================================================

@admin_bp.route("/asignaciones-equipo", methods=["GET", "POST"])
@login_required
@requiere_permiso("usr_asignaciones_equipo")
def asignaciones_equipo():
    """Gestión de asignaciones de equipo"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import (
        get_all_assignments, 
        add_assignment, 
        remove_assignment_by_id,
        get_managers_for_assignments,
        get_members_for_assignments
    )

    if request.method == "POST":
        action = request.form.get("accion")

        if action == "agregar":
            manager = request.form.get("manager_username")
            member = request.form.get("member_username")

            if manager and member:
                if add_assignment(manager, member):
                    flash(f"Asignación creada: {member} → {manager}", "success")
                else:
                    flash("Error al crear asignación", "error")

        elif action == "eliminar":
            assignment_id = request.form.get("assignment_id")
            print(f"DTO ELIMINAR: id={assignment_id}")
            if assignment_id:
                try:
                    aid = int(assignment_id)
                    if remove_assignment_by_id(aid):
                        flash("Asignación eliminada", "success")
                    else:
                        flash("Error al eliminar asignación", "error")
                except ValueError:
                     flash("ID de asignación inválido", "error")

        return redirect(url_for("admin.asignaciones_equipo"))

    # GET: mostrar página
    asignaciones = get_all_assignments()
    managers = get_managers_for_assignments()
    members = get_members_for_assignments()

    # Agrupar asignaciones por manager para el template
    assignments_by_manager = {}
    for a in asignaciones:
        mgr = a["manager_username"]
        if mgr not in assignments_by_manager:
            assignments_by_manager[mgr] = {
                "manager_rol": a.get("manager_rol", ""),
                "members": []
            }
        assignments_by_manager[mgr]["members"].append(a)

    # Ordenar por jerarquía de rol: gerente > supervisor > auditor
    jerarquia_roles = {"gerente": 1, "supervisor": 2, "auditor": 3}
    assignments_by_manager = dict(
        sorted(
            assignments_by_manager.items(),
            key=lambda x: jerarquia_roles.get(x[1].get("manager_rol", ""), 99)
        )
    )

    return render_template(
        "admin/asignaciones_equipo.html",
        asignaciones=asignaciones,
        assignments_by_manager=assignments_by_manager,
        managers=managers,
        members=members
    )


# ============================================================================
# RUTAS DE LÍNEAS DE CRÉDITO
# ============================================================================

@admin_bp.route("/lineas", methods=["POST"])
@login_required
def lineas_legacy():
    """
    Legacy route for /admin/lineas POST.
    This route handles inline edits from the admin panel line cards.
    It acts as a proxy to editar_linea_credito.
    """
    print("📝 [LEGACY] POST /admin/lineas called")
    # Delegate to the edit function - the form has tipo_credito as name
    return editar_linea_credito_legacy()


def editar_linea_credito_legacy():
    """Internal function to handle legacy /admin/lineas POST"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    if not tiene_alguno_de(["cfg_lin_editar", "cfg_tasas_editar"]):
        flash("No tienes permiso para editar líneas de crédito", "warning")
        return redirect(url_for("admin.admin_panel"))

    from db_helpers import cargar_configuracion, guardar_configuracion
    from ..utils.formatting import parse_currency_value

    try:
        # The legacy form uses 'tipo_credito' as the line name
        nombre = request.form.get("tipo_credito", "").strip()
        
        print(f"📝 [LEGACY] Editing line: {nombre}")

        if not nombre:
            flash("El nombre de la línea es requerido", "error")
            return redirect(url_for("admin.admin_panel") + "#TasasCredito")

        config = cargar_configuracion()
        lineas = config.get("LINEAS_CREDITO", {})

        if nombre not in lineas:
            flash(f"Línea '{nombre}' no encontrada", "error")
            return redirect(url_for("admin.admin_panel") + "#TasasCredito")

        # Update the line data from form
        linea_data = lineas[nombre]
        
        # Only update fields that are present in the form
        if request.form.get("descripcion"):
            linea_data["descripcion"] = request.form.get("descripcion")
        if request.form.get("monto_min"):
            linea_data["monto_min"] = parse_currency_value(request.form.get("monto_min"))
        if request.form.get("monto_max"):
            linea_data["monto_max"] = parse_currency_value(request.form.get("monto_max"))
        if request.form.get("plazo_min"):
            linea_data["plazo_min"] = int(request.form.get("plazo_min"))
        if request.form.get("plazo_max"):
            linea_data["plazo_max"] = int(request.form.get("plazo_max"))
        if request.form.get("tasa_mensual"):
            linea_data["tasa_mensual"] = float(request.form.get("tasa_mensual"))
        if request.form.get("tasa_anual"):
            linea_data["tasa_anual"] = float(request.form.get("tasa_anual"))
        if request.form.get("aval_porcentaje"):
            linea_data["aval_porcentaje"] = float(request.form.get("aval_porcentaje"))
        if request.form.get("plazo_tipo"):
            linea_data["plazo_tipo"] = request.form.get("plazo_tipo")
        linea_data["permite_desembolso_neto"] = request.form.get("permite_desembolso_neto") == "on"
        if request.form.get("desembolso_por_defecto"):
            linea_data["desembolso_por_defecto"] = request.form.get("desembolso_por_defecto")

        lineas[nombre] = linea_data
        config["LINEAS_CREDITO"] = lineas
        
        guardar_configuracion(config)
        print(f" [LEGACY] Line '{nombre}' updated successfully")
        flash(f"Línea '{nombre}' actualizada correctamente", "success")

        return redirect(url_for("admin.admin_panel") + "#TasasCredito")

    except Exception as e:
        import traceback as tb
        tb.print_exc()
        flash(f"Error al editar línea: {str(e)}", "error")
        return redirect(url_for("admin.admin_panel") + "#TasasCredito")


@admin_bp.route("/lineas/guardar-tasas-todas", methods=["POST"])
@login_required
def guardar_tasas_todas():
    """Guardar tasas de todas las líneas de crédito a la vez"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    if not tiene_alguno_de(["cfg_lin_editar", "cfg_tasas_editar"]):
        return jsonify({"success": False, "error": "Sin permiso"}), 403

    from db_helpers import cargar_configuracion, guardar_configuracion

    try:
        data = request.get_json()
        if not data or "lineas" not in data:
            return jsonify({"success": False, "error": "Datos inválidos"}), 400

        config = cargar_configuracion()
        lineas = config.get("LINEAS_CREDITO", {})
        
        actualizadas = 0
        for item in data["lineas"]:
            nombre = item.get("tipo_credito", "")
            tasa_anual = item.get("tasa_anual")
            if nombre in lineas and tasa_anual is not None:
                tasa_anual_f = float(tasa_anual)
                tasa_mensual = round(((1 + tasa_anual_f / 100) ** (1/12) - 1) * 100, 6)
                lineas[nombre]["tasa_anual"] = tasa_anual_f
                lineas[nombre]["tasa_mensual"] = tasa_mensual
                actualizadas += 1
                print(f"   {nombre}: TEA={tasa_anual_f}% → Mensual={tasa_mensual}%")
        
        config["LINEAS_CREDITO"] = lineas
        guardar_configuracion(config)
        
        print(f" [TASAS] {actualizadas} líneas actualizadas en lote")
        return jsonify({
            "success": True, 
            "message": f"{actualizadas} línea(s) actualizada(s)",
            "actualizadas": actualizadas
        })

    except Exception as e:
        import traceback as tb
        tb.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/lineas/nueva", methods=["POST"])
@login_required
def crear_linea_credito():
    """Crear nueva línea de crédito"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    if not tiene_alguno_de(["cfg_lin_editar", "cfg_tasas_editar"]):
        flash("No tienes permiso para crear líneas de crédito", "warning")
        return redirect(url_for("admin.admin_panel"))

    from db_helpers import cargar_configuracion, guardar_configuracion
    from db_helpers_scoring_linea import crear_config_scoring_linea_defecto
    from ..utils.formatting import parse_currency_value

    try:
        # Accept both 'nombre' and 'nombre_linea' for frontend compatibility
        nombre = request.form.get("nombre") or request.form.get("nombre_linea", "").strip()
        
        print(f"📝 [CREAR] nombre={nombre}")

        if not nombre:
            flash("El nombre de la línea es requerido", "error")
            return redirect(url_for("admin.admin_panel") + "#TasasCredito")

        config = cargar_configuracion()
        lineas = config.get("LINEAS_CREDITO", {})

        if nombre in lineas:
            flash(f"La línea '{nombre}' ya existe", "error")
            return redirect(url_for("admin.admin_panel") + "#TasasCredito")

        # Crear nueva línea
        tasa_anual = float(request.form.get("tasa_anual", 25))
        aval_raw = float(request.form.get("aval_porcentaje", 10))
        aval_normalizado = aval_raw / 100 if aval_raw > 1 else aval_raw

        lineas[nombre] = {
            "descripcion": request.form.get("descripcion", ""),
            "monto_min": parse_currency_value(request.form.get("monto_min", 500000)),
            "monto_max": parse_currency_value(request.form.get("monto_max", 10000000)),
            "plazo_min": int(request.form.get("plazo_min", 1)),
            "plazo_max": int(request.form.get("plazo_max", 36)),
            "tasa_mensual": float(request.form.get("tasa_mensual", 2.0)),
            "tasa_anual": tasa_anual,
            "aval_porcentaje": aval_normalizado,
            "plazo_tipo": request.form.get("plazo_tipo", "meses"),
            "permite_desembolso_neto": request.form.get("permite_desembolso_neto") in ("on", "true"),
            "desembolso_por_defecto": request.form.get("desembolso_por_defecto", "completo")
        }

        # Crear costos asociados iniciales
        costos_iniciales = {}
        costo_pagare = request.form.get("costo_pagare")
        if costo_pagare:
            costos_iniciales["Pagaré Digital"] = parse_currency_value(costo_pagare)
        
        costo_carta = request.form.get("costo_carta")
        if costo_carta:
            costos_iniciales["Carta de Instrucción"] = parse_currency_value(costo_carta)
        
        costo_datacredito = request.form.get("costo_datacredito")
        if costo_datacredito:
            costos_iniciales["Consulta Datacrédito"] = parse_currency_value(costo_datacredito)
        
        costo_custodia = request.form.get("costo_custodia")
        if costo_custodia:
            costos_iniciales["Custodia TVE"] = parse_currency_value(costo_custodia)

        # Guardar costos asociados para la nueva línea
        if costos_iniciales:
            costos_asociados = config.get("COSTOS_ASOCIADOS", {})
            costos_asociados[nombre] = costos_iniciales
            config["COSTOS_ASOCIADOS"] = costos_asociados

        config["LINEAS_CREDITO"] = lineas
        guardar_configuracion(config)

        # Crear configuración de scoring por defecto para la nueva línea
        from database import conectar_db
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM lineas_credito WHERE nombre = ?", (nombre,))
        row = cursor.fetchone()
        conn.close()

        if row:
            linea_id = row[0]
            crear_config_scoring_linea_defecto(linea_id, tasa_anual)

        flash(f"Línea '{nombre}' creada exitosamente", "success")

    except Exception as e:
        traceback.print_exc()
        flash(f"Error al crear línea: {str(e)}", "error")

    return redirect(url_for("admin.admin_panel") + "#TasasCredito")


@admin_bp.route("/lineas/editar", methods=["POST"])
@login_required
def editar_linea_credito():
    """Editar línea de crédito existente"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    if not tiene_alguno_de(["cfg_lin_editar", "cfg_tasas_editar"]):
        flash("No tienes permiso para editar líneas de crédito", "warning")
        return redirect(url_for("admin.admin_panel"))

    from db_helpers import cargar_configuracion, guardar_configuracion
    from ..utils.formatting import parse_currency_value

    try:
        # El nombre original viene en un campo oculto o es el mismo nombre si no se permite cambiar
        nombre_original = request.form.get("nombre_original")
        # Accept both 'nombre' and 'nombre_linea' for frontend compatibility
        nombre = request.form.get("nombre") or request.form.get("nombre_linea", "").strip()
        
        print(f" [EDITAR] nombre_original='{nombre_original}', nombre='{nombre}'")
        print(f" [EDITAR] Form keys: {list(request.form.keys())}")
        print(f" [EDITAR] Nombre cambió: {nombre_original != nombre}")

        if not nombre:
            flash("El nombre de la línea es requerido", "error")
            return redirect(url_for("admin.admin_panel") + "#TasasCredito")

        config = cargar_configuracion()
        lineas = config.get("LINEAS_CREDITO", {})

        # Si el nombre cambió, verificar que no exista ya
        if nombre_original and nombre != nombre_original and nombre in lineas:
            flash(f"La línea '{nombre}' ya existe", "error")
            return redirect(url_for("admin.admin_panel") + "#TasasCredito")

        # Recuperar datos existentes o crear nuevos
        linea_data = lineas.get(nombre_original, {}) if nombre_original else {}
        if not linea_data and nombre in lineas:
             linea_data = lineas[nombre]

        # Actualizar solo los campos que vienen en el formulario
        # (el modal no envía tasa_mensual, tasa_anual ni aval_porcentaje)
        if request.form.get("descripcion") is not None:
            linea_data["descripcion"] = request.form.get("descripcion", "")
        if request.form.get("monto_min"):
            linea_data["monto_min"] = parse_currency_value(request.form.get("monto_min"))
        if request.form.get("monto_max"):
            linea_data["monto_max"] = parse_currency_value(request.form.get("monto_max"))
        if request.form.get("plazo_min"):
            linea_data["plazo_min"] = int(request.form.get("plazo_min"))
        if request.form.get("plazo_max"):
            linea_data["plazo_max"] = int(request.form.get("plazo_max"))
        if request.form.get("plazo_tipo"):
            linea_data["plazo_tipo"] = request.form.get("plazo_tipo")
        if request.form.get("permite_desembolso_neto") is not None:
            linea_data["permite_desembolso_neto"] = request.form.get("permite_desembolso_neto") in ("on", "true")
        if request.form.get("desembolso_por_defecto"):
            linea_data["desembolso_por_defecto"] = request.form.get("desembolso_por_defecto")
        
        # Solo actualizar tasas y aval si vienen en el form (evita sobrescribir con defaults)
        if request.form.get("tasa_mensual"):
            linea_data["tasa_mensual"] = float(request.form.get("tasa_mensual"))
        if request.form.get("tasa_anual"):
            linea_data["tasa_anual"] = float(request.form.get("tasa_anual"))
        if request.form.get("aval_porcentaje"):
            aval_raw = float(request.form.get("aval_porcentaje"))
            linea_data["aval_porcentaje"] = aval_raw / 100 if aval_raw > 1 else aval_raw
        
        # Si hubo cambio de nombre, RENOMBRAR en vez de eliminar+crear
        # Esto preserva el ID y todas las FK (scoring, comité, costos, etc.)
        nombre_final = nombre  # nombre que usaremos para guardar
        if nombre_original and nombre != nombre_original:
            from db_helpers import renombrar_linea_credito_db
            print(f" [EDITAR] Intentando renombrar: '{nombre_original}' → '{nombre}'")
            renombrado_ok = renombrar_linea_credito_db(nombre_original, nombre)
            print(f" [EDITAR] Resultado rename: {renombrado_ok}")
            
            if not renombrado_ok:
                # Rename falló, pero guardamos los demás cambios con el nombre original
                print(f" [EDITAR] RENAME FALLÓ - guardando valores con nombre original")
                flash(f"No se pudo renombrar '{nombre_original}', pero los demás cambios se guardaron", "warning")
                nombre_final = nombre_original
                lineas[nombre_final] = linea_data
            else:
                # Migrar COSTOS_ASOCIADOS (clave es el nombre de la línea)
                costos = config.get("COSTOS_ASOCIADOS", {})
                if nombre_original in costos:
                    costos[nombre] = costos.pop(nombre_original)
                    config["COSTOS_ASOCIADOS"] = costos
                    print(f"   [EDITAR] Costos asociados migrados: '{nombre_original}' → '{nombre}'")
                
                # Preservar orden en el diccionario (no mover al final)
                new_lineas = {}
                for key, value in lineas.items():
                    if key == nombre_original:
                        new_lineas[nombre] = linea_data
                    else:
                        new_lineas[key] = value
                lineas = new_lineas
        else:
            lineas[nombre_final] = linea_data
        
        config["LINEAS_CREDITO"] = lineas
        
        print(f" [EDITAR] Guardando config con líneas: {list(config.get('LINEAS_CREDITO', {}).keys())}")
        guardar_configuracion(config)
        print(f" [EDITAR] Línea '{nombre_final}' guardada exitosamente")
        if nombre_final == nombre:
            flash(f"Línea '{nombre}' actualizada correctamente", "success")

    except Exception as e:
        print(f" [EDITAR] EXCEPCIÓN: {str(e)}")
        traceback.print_exc()
        flash(f"Error al editar línea: {str(e)}", "error")

    return redirect(url_for("admin.admin_panel") + "#TasasCredito")
@admin_bp.route("/lineas/eliminar", methods=["POST"])
@login_required
def eliminar_linea_credito():
    """Eliminar línea de crédito (soft delete)"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    if not tiene_alguno_de(["cfg_lin_editar", "cfg_tasas_editar"]):
        flash("No tienes permiso para eliminar líneas de crédito", "warning")
        return redirect(url_for("admin.admin_panel"))

    from db_helpers import eliminar_linea_credito_db

    try:
        # Accept both 'nombre' and 'nombre_linea' for backward compatibility
        nombre = request.form.get("nombre") or request.form.get("nombre_linea")

        if not nombre:
            flash("Nombre de línea no especificado", "error")
            return redirect(url_for("admin.admin_panel") + "#TasasCredito")

        if eliminar_linea_credito_db(nombre):
            flash(f"Línea '{nombre}' eliminada", "success")
        else:
            flash(f"Error al eliminar línea '{nombre}'", "error")

    except Exception as e:
        flash(f"Error al eliminar línea: {str(e)}", "error")

    return redirect(url_for("admin.admin_panel") + "#TasasCredito")


@admin_bp.route("/lineas/reordenar", methods=["POST"])
@login_required
@requiere_permiso("cfg_lin_editar")
def reordenar_lineas_credito():
    """Reordenar líneas de crédito según nuevo orden del drag & drop"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    import sqlite3
    from database import DB_PATH
    
    try:
        data = request.get_json()
        nuevo_orden = data.get("orden", [])
        
        if not nuevo_orden:
            return jsonify({"success": False, "error": "No se proporcionó orden"}), 400
        
        # Actualizar columna orden en la base de datos
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        for i, nombre in enumerate(nuevo_orden, 1):
            cursor.execute(
                "UPDATE lineas_credito SET orden = ? WHERE nombre = ? AND activo = 1",
                (i, nombre)
            )
        
        conn.commit()
        conn.close()
        
        print(f"✅ Orden de líneas actualizado en BD: {nuevo_orden}")
        return jsonify({"success": True, "mensaje": "Orden actualizado correctamente"})
        
    except Exception as e:
        print(f"❌ Error al reordenar líneas: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/costos", methods=["POST"])
@login_required
@requiere_permiso("cfg_costos_editar")
def guardar_costo():
    """Guardar o actualizar un costo asociado"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import cargar_configuracion, guardar_configuracion
    from ..utils.formatting import parse_currency_value

    try:
        linea_nombre = request.form.get("linea")
        nombre_costo = request.form.get("nombre_costo")
        valor = request.form.get("valor")

        if not linea_nombre or not nombre_costo or valor is None:
            flash("Todos los campos son requeridos", "error")
            return redirect(url_for("admin.admin_panel") + "#CostosAsociados")

        config = cargar_configuracion()
        costos = config.get("COSTOS_ASOCIADOS", {})
        
        if linea_nombre not in costos:
            costos[linea_nombre] = {}
        
        costos[linea_nombre][nombre_costo] = parse_currency_value(str(valor))
        config["COSTOS_ASOCIADOS"] = costos
        
        guardar_configuracion(config)
        flash(f"Costo '{nombre_costo}' guardado correctamente", "success")

    except Exception as e:
        traceback.print_exc()
        flash(f"Error al guardar costo: {str(e)}", "error")

    return redirect(url_for("admin.admin_panel") + "#CostosAsociados")


@admin_bp.route("/costos/guardar-todos", methods=["POST"])
@login_required
@requiere_permiso("cfg_costos_editar")
def guardar_todos_costos():
    """Guardar todos los costos de una línea de crédito de una vez"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import cargar_configuracion, guardar_configuracion
    from ..utils.formatting import parse_currency_value

    try:
        linea_nombre = request.form.get("tipo_credito")
        
        if not linea_nombre:
            flash("Línea no especificada", "error")
            return redirect(url_for("admin.admin_panel") + "#CostosAsociados")

        print(f"📝 [COSTOS] Guardando costos para línea: {linea_nombre}")

        config = cargar_configuracion()
        costos = config.get("COSTOS_ASOCIADOS", {})
        lineas = config.get("LINEAS_CREDITO", {})
        
        # Reconstruir costos desde el formulario dinámicamente
        nuevos_costos = {}
        i = 0
        while True:
            nombre = request.form.get(f"nombre_costo_{i}")
            valor = request.form.get(f"valor_costo_{i}")
            if nombre is None:
                break
            if nombre.strip() and valor:
                nuevos_costos[nombre.strip()] = parse_currency_value(valor)
                print(f"   ✅ Costo: {nombre.strip()} = {parse_currency_value(valor)}")
            i += 1
        
        costos[linea_nombre] = nuevos_costos
        config["COSTOS_ASOCIADOS"] = costos
        
        # Actualizar aval si está presente
        aval = request.form.get("aval_porcentaje")
        if aval and linea_nombre in lineas:
            try:
                aval_valor = float(aval.replace(",", ".").replace("%", "").strip())
                # Normalizar: si es mayor a 1, dividir por 100
                aval_normalizado = aval_valor / 100 if aval_valor > 1 else aval_valor
                lineas[linea_nombre]["aval_porcentaje"] = aval_normalizado
                config["LINEAS_CREDITO"] = lineas
                print(f"   ✅ Aval actualizado: {aval_valor}% -> {aval_normalizado}")
            except ValueError:
                print(f"   ⚠️ Error parseando aval: {aval}")
        
        guardar_configuracion(config)
        flash(f"Costos de '{linea_nombre}' guardados correctamente ({len(nuevos_costos)} costos)", "success")

    except Exception as e:
        traceback.print_exc()
        flash(f"Error al guardar costos: {str(e)}", "error")

    return redirect(url_for("admin.admin_panel") + "#CostosAsociados")


@admin_bp.route("/costos/guardar-todos-ajax", methods=["POST"])
@login_required
@requiere_permiso("cfg_costos_editar")
def guardar_todos_costos_ajax():
    """Guardar costos de todas las líneas a la vez (AJAX)"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import cargar_configuracion, guardar_configuracion
    from ..utils.formatting import parse_currency_value

    try:
        data = request.get_json()
        if not data or "lineas" not in data:
            return jsonify({"success": False, "error": "Datos inválidos"}), 400

        config = cargar_configuracion()
        costos_config = config.get("COSTOS_ASOCIADOS", {})
        lineas_config = config.get("LINEAS_CREDITO", {})

        actualizadas = 0
        for item in data["lineas"]:
            nombre = item.get("tipo_credito", "")
            costos_linea = item.get("costos", {})
            aval = item.get("aval_porcentaje")

            if not nombre:
                continue

            # Parsear valores de costos
            nuevos_costos = {}
            for costo_nombre, costo_valor in costos_linea.items():
                if costo_nombre.strip() and costo_valor is not None:
                    nuevos_costos[costo_nombre.strip()] = parse_currency_value(str(costo_valor))

            costos_config[nombre] = nuevos_costos
            print(f"   ✅ Costos de '{nombre}': {len(nuevos_costos)} costos")

            # Actualizar aval
            if aval is not None and nombre in lineas_config:
                try:
                    aval_valor = float(str(aval).replace(",", ".").replace("%", "").strip())
                    aval_normalizado = aval_valor / 100 if aval_valor > 1 else aval_valor
                    lineas_config[nombre]["aval_porcentaje"] = aval_normalizado
                except ValueError:
                    pass

            actualizadas += 1

        config["COSTOS_ASOCIADOS"] = costos_config
        config["LINEAS_CREDITO"] = lineas_config
        guardar_configuracion(config)

        print(f" [COSTOS-AJAX] {actualizadas} líneas actualizadas en lote")
        return jsonify({
            "success": True,
            "message": f"{actualizadas} línea(s) actualizada(s)",
            "actualizadas": actualizadas
        })

    except Exception as e:
        import traceback as tb
        tb.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/costos/eliminar", methods=["POST"])
@login_required
@requiere_permiso("cfg_costos_editar")
def eliminar_costo():
    """Eliminar un costo asociado"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import cargar_configuracion, guardar_configuracion

    try:
        linea_nombre = request.form.get("linea")
        nombre_costo = request.form.get("nombre_costo")

        if not linea_nombre or not nombre_costo:
            flash("Datos incompletos para eliminar costo", "error")
            return redirect(url_for("admin.admin_panel") + "#CostosAsociados")

        config = cargar_configuracion()
        costos = config.get("COSTOS_ASOCIADOS", {})
        
        if linea_nombre in costos and nombre_costo in costos[linea_nombre]:
            del costos[linea_nombre][nombre_costo]
            # Si la línea queda sin costos, se puede dejar la llave vacía o eliminarla
            # Dejémosla para consistencia
            
            config["COSTOS_ASOCIADOS"] = costos
            guardar_configuracion(config)
            flash(f"Costo '{nombre_costo}' eliminado", "success")
        else:
            flash("Costo no encontrado", "warning")

    except Exception as e:
        traceback.print_exc()
        flash(f"Error al eliminar costo: {str(e)}", "error")

    return redirect(url_for("admin.admin_panel") + "#CostosAsociados")


@admin_bp.route("/capacidad/guardar", methods=["POST"])
@login_required
@requiere_permiso("cfg_capacidad_editar")
def guardar_capacidad():
    """Guardar parámetros de capacidad de pago"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import cargar_configuracion, guardar_configuracion

    try:
        data = request.form
        # Si viene como JSON (fetch)
        if request.is_json:
            data = request.get_json()
        
        # Validar datos recibidos
        try:
            limite_conservador = int(data.get("limite_conservador", 30))
            limite_maximo = int(data.get("limite_maximo", 35))
            limite_absoluto = int(data.get("limite_absoluto", 40))
        except ValueError:
             if request.is_json:
                 return jsonify({"success": False, "error": "Los límites deben ser números enteros"}), 400
             flash("Los límites deben ser números enteros", "error")
             return redirect(url_for("admin.admin_panel") + "#CapacidadPago")

        # Validar rangos
        if not (10 <= limite_conservador <= 50):
             msg = "Límite conservador debe estar entre 10% y 50%"
             if request.is_json:
                 return jsonify({"success": False, "error": msg}), 400
             flash(msg, "error")
             return redirect(url_for("admin.admin_panel") + "#CapacidadPago")

        if not (limite_conservador < limite_maximo < limite_absoluto):
             msg = "Los límites deben seguir el orden: Conservador < Máximo < Absoluto"
             if request.is_json:
                 return jsonify({"success": False, "error": msg}), 400
             flash(msg, "error")
             return redirect(url_for("admin.admin_panel") + "#CapacidadPago")

        if limite_absoluto > 90:
             msg = "El límite absoluto no puede exceder el 90%"
             if request.is_json:
                 return jsonify({"success": False, "error": msg}), 400
             flash(msg, "error")
             return redirect(url_for("admin.admin_panel") + "#CapacidadPago")

        config = cargar_configuracion()
        params = config.get("PARAMETROS_CAPACIDAD_PAGO", {})
        
        # Actualizar valores
        params["limite_conservador"] = limite_conservador
        params["limite_maximo"] = limite_maximo
        params["limite_absoluto"] = limite_absoluto
        
        config["PARAMETROS_CAPACIDAD_PAGO"] = params
        guardar_configuracion(config)
        
        if request.is_json:
            return jsonify({"success": True, "message": "Parámetros guardados correctamente"})
        
        flash("Parámetros de capacidad guardados correctamente", "success")

    except Exception as e:
        traceback.print_exc()
        if request.is_json:
            return jsonify({"success": False, "error": str(e)}), 500
        flash(f"Error al guardar capacidad: {str(e)}", "error")

    return redirect(url_for("admin.admin_panel") + "#CapacidadPago")


# ============================================================================
# RUTAS DE SCORING
# ============================================================================

@admin_bp.route("/scoring/guardar", methods=["POST"])
@login_required
@requiere_permiso("cfg_sco_editar")
def guardar_scoring():
    """Guardar configuración de scoring"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import guardar_scoring as db_guardar_scoring

    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No se recibieron datos"}), 400

        db_guardar_scoring(data)

        return jsonify({
            "success": True,
            "message": "Configuración de scoring guardada"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/actualizar_umbral_mora_telcos", methods=["POST"])
@login_required
@requiere_permiso("cfg_sco_editar")
def actualizar_umbral_mora_telcos():
    """Actualizar umbral de mora de telecomunicaciones"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import cargar_scoring, guardar_scoring

    try:
        data = request.get_json()
        umbral = data.get("umbral")

        if umbral is None:
            return jsonify({"success": False, "error": "Umbral no especificado"}), 400

        print(f"📝 [ADMIN] Actualizando umbral_mora_telcos a: {umbral}")

        scoring = cargar_scoring()
        scoring["umbral_mora_telcos_rechazo"] = float(umbral)
        guardar_scoring(scoring)

        return jsonify({"success": True, "message": "Umbral actualizado correctamente"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# PARAMETROS DEL SISTEMA
# ============================================================================

@admin_bp.route("/parametros-sistema")
@login_required
@requiere_permiso("cfg_params_sistema")
def parametros_sistema_page():
    """Pagina de administracion de parametros del sistema."""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import obtener_parametros_sistema

    parametros = obtener_parametros_sistema()
    return render_template("parametros_sistema.html", parametros=parametros)


@admin_bp.route("/api/parametros-sistema", methods=["GET"])
@login_required
@requiere_permiso("cfg_params_sistema")
def api_obtener_parametros():
    """API: Obtener todos los parametros del sistema."""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import obtener_parametros_sistema

    parametros = obtener_parametros_sistema()
    return jsonify({"success": True, "parametros": parametros})


@admin_bp.route("/api/parametros-sistema", methods=["POST"])
@login_required
@requiere_permiso("cfg_params_sistema")
def api_guardar_parametros():
    """API: Guardar parametros del sistema."""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import guardar_parametro

    try:
        data = request.get_json()
        parametros = data.get("parametros", [])

        if not parametros:
            return jsonify({"success": False, "error": "No se recibieron parametros"}), 400

        errores = []
        guardados = 0
        for param in parametros:
            clave = param.get("clave", "").strip()
            valor = param.get("valor", "").strip()
            descripcion = param.get("descripcion")

            if not clave or not valor:
                errores.append(f"Parametro '{clave}' sin valor")
                continue

            # Validar que el valor sea numerico
            try:
                float(valor)
            except ValueError:
                errores.append(f"'{clave}': valor '{valor}' no es numerico")
                continue

            ok = guardar_parametro(clave, valor, descripcion)
            if ok:
                guardados += 1
            else:
                errores.append(f"Error guardando '{clave}'")

        if errores:
            return jsonify({
                "success": guardados > 0,
                "guardados": guardados,
                "errores": errores
            })

        return jsonify({
            "success": True,
            "guardados": guardados,
            "message": f"{guardados} parametro(s) actualizado(s)"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500