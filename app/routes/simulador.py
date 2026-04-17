"""
SIMULADOR.PY - Rutas del simulador de crédito
==============================================
"""

from flask import render_template, request, redirect, url_for, session, jsonify, flash
from functools import wraps
import json
import math
from datetime import datetime

from . import simulador_bp
from ..utils.finance import (
    calcular_edad_desde_fecha,
    calcular_cuota,
    calcular_seguro_proporcional_fecha,
    obtener_aval_dinamico,
    obtener_tasa_por_nivel_riesgo,
    SEMANAS_POR_MES
)
from ..utils.formatting import formatear_con_miles
from db_helpers import cargar_configuracion, cargar_scoring


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

            # Importar función de permisos
            import sys
            from pathlib import Path
            BASE_DIR = Path(__file__).parent.parent.parent.resolve()
            if str(BASE_DIR) not in sys.path:
                sys.path.insert(0, str(BASE_DIR))

            from permisos import tiene_permiso

            if not tiene_permiso(permiso):
                flash("No tienes permiso para acceder a esta función", "error")
                return redirect(url_for("main.dashboard"))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


@simulador_bp.route("/simulador")
@login_required
@requiere_permiso("sim_usar")
def simulador_asesor():
    """Página del simulador de crédito para asesores"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import cargar_configuracion, cargar_scoring

    config = cargar_configuracion()
    scoring = cargar_scoring()

    lineas_credito = config.get("LINEAS_CREDITO", {})
    costos_asociados = config.get("COSTOS_ASOCIADOS", {})
    niveles_riesgo = scoring.get("niveles_riesgo", [])

    return render_template(
        "asesor/simulador.html",
        lineas=lineas_credito,
        lineas_credito=lineas_credito,
        costos_asociados=costos_asociados,
        niveles_riesgo=niveles_riesgo,
        config_json=json.dumps({
            "lineas_credito": lineas_credito,
            "costos_asociados": costos_asociados,
            "niveles_riesgo": niveles_riesgo
        })
    )


@simulador_bp.route("/capacidad_pago")
@login_required
@requiere_permiso("cap_usar")
def capacidad_pago():
    """Página de cálculo de capacidad de pago"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import cargar_configuracion

    config = cargar_configuracion()
    parametros = config.get("PARAMETROS_CAPACIDAD_PAGO", {})

    return render_template(
        "asesor/capacidad_pago.html",
        parametros=parametros
    )


@simulador_bp.route("/historial_simulaciones")
@login_required
def historial_simulaciones():
    """Historial de simulaciones del asesor"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import cargar_simulaciones, resolve_visible_usernames
    from permisos import obtener_permisos_usuario_actual

    username = session.get("username")
    permisos = obtener_permisos_usuario_actual()

    # Determinar qué simulaciones puede ver
    visibilidad = resolve_visible_usernames(username, permisos, contexto="simulaciones")

    # Cargar simulaciones según visibilidad
    todas_simulaciones = cargar_simulaciones()

    if visibilidad['scope'] == 'todos':
        simulaciones = todas_simulaciones
    elif visibilidad['scope'] == 'equipo':
        usernames_visibles = visibilidad['usernames_visibles'] or []
        simulaciones = [s for s in todas_simulaciones if s.get('asesor') in usernames_visibles]
    else:
        # Solo propias
        simulaciones = [s for s in todas_simulaciones if s.get('asesor') == username]

    return render_template(
        "asesor/historial_simulaciones.html",
        simulaciones=simulaciones,
        scope=visibilidad['scope']
    )


@simulador_bp.route("/guardar_simulacion", methods=["POST"])
@login_required
@requiere_permiso("sim_usar")
def guardar_simulacion_endpoint():
    """Guardar una nueva simulación"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import guardar_simulacion
    from ..utils.timezone import obtener_hora_colombia

    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No se recibieron datos"}), 400

        # Agregar metadata
        data["timestamp"] = obtener_hora_colombia().isoformat()
        data["asesor"] = session.get("username")

        # Guardar simulación
        guardar_simulacion(data)

        return jsonify({
            "success": True,
            "message": "Simulación guardada correctamente",
            "timestamp": data["timestamp"]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@simulador_bp.route("/calcular", methods=["POST"])
def calcular_cliente():
    """Cálculo de simulación para clientes (sin mostrar costos detalle)"""
    try:
        config = cargar_configuracion()
        lineas_credito = config.get("LINEAS_CREDITO", {})
        costos_asociados = config.get("COSTOS_ASOCIADOS", {})
        seguros_config = config.get("SEGUROS", {})

        # Capturar valores del formulario
        tipo_credito = request.form.get("tipo_credito", "")
        monto_str = request.form.get("monto", "")
        plazo_str = request.form.get("plazo", "")
        fecha_nacimiento = request.form.get("fecha_nacimiento", "")
        desembolso_completo = request.form.get("desembolso_completo", "")

        if not tipo_credito or tipo_credito not in lineas_credito:
            flash("Tipo de crédito inválido", "danger")
            return render_template(
                "cliente/formulario.html",
                lineas=lineas_credito,
                tipo_credito_sel=tipo_credito,
                monto_ingresado=monto_str,
                plazo_ingresado=plazo_str,
                fecha_nacimiento_ingresada=fecha_nacimiento
            )

        datos = lineas_credito[tipo_credito]

        # Validar monto
        monto_str_limpio = monto_str.replace(".", "")
        try:
            monto_solicitado = float(monto_str_limpio)
        except:
            flash("Monto inválido. Ingrese solo números.", "danger")
            return redirect(url_for("main.home"))

        if not (datos["monto_min"] <= monto_solicitado <= datos["monto_max"]):
            flash(f"El monto debe estar entre ${formatear_con_miles(datos['monto_min'])} y ${formatear_con_miles(datos['monto_max'])}", "warning")
            return redirect(url_for("main.home"))

        # Validar plazo
        try:
            plazo = int(plazo_str)
        except:
            flash("Plazo inválido", "danger")
            return redirect(url_for("main.home"))

        if not (datos["plazo_min"] <= plazo <= datos["plazo_max"]):
            flash(f"El plazo debe estar entre {datos['plazo_min']} y {datos['plazo_max']} {datos['plazo_tipo']}", "warning")
            return redirect(url_for("main.home"))

        # Validar edad
        try:
            edad_cliente = calcular_edad_desde_fecha(fecha_nacimiento)
            if edad_cliente < 18 or edad_cliente > 84:
                flash("Debes tener entre 18 y 84 años", "warning")
                return redirect(url_for("main.home"))
        except:
            flash("Fecha de nacimiento inválida", "danger")
            return redirect(url_for("main.home"))

        # Cálculos
        tasa_mensual_decimal = datos["tasa_mensual"] / 100
        plazo_en_meses = plazo if datos["plazo_tipo"] == "meses" else plazo / SEMANAS_POR_MES
        
        seguro_vida = calcular_seguro_proporcional_fecha(
            fecha_nacimiento, monto_solicitado, plazo_en_meses, seguros_config
        )
        
        aval = int(round(monto_solicitado * datos["aval_porcentaje"]))
        costos_actuales = costos_asociados.get(tipo_credito, {})
        
        total_costos = sum(costos_actuales.values()) + seguro_vida + aval

        desembolso_completo_bool = (desembolso_completo == "on")

        if desembolso_completo_bool:
            monto_total_financiar = monto_solicitado + total_costos
            monto_a_desembolsar = monto_solicitado
        else:
            monto_total_financiar = monto_solicitado
            monto_a_desembolsar = monto_solicitado - total_costos
            
            if monto_a_desembolsar <= 0:
                flash("Los costos superan el monto solicitado. Aumenta el monto.", "warning")
                return redirect(url_for("main.home"))

        cuota = calcular_cuota(monto_total_financiar, tasa_mensual_decimal, plazo_en_meses)
        
        tipo_cuota = "Cuota mensual fija"
        if datos["plazo_tipo"] == "semanas":
            cuota = int(round(cuota / SEMANAS_POR_MES))
            tipo_cuota = "Cuota semanal fija"

        return render_template(
            "cliente/resultado.html",
            tipo_credito=tipo_credito,
            monto_solicitado=formatear_con_miles(monto_solicitado),
            monto_original=formatear_con_miles(monto_solicitado),
            monto_a_desembolsar=formatear_con_miles(monto_a_desembolsar),
            desembolso_completo=desembolso_completo_bool,
            cuota=formatear_con_miles(cuota),
            tipo_cuota=tipo_cuota,
            plazo=plazo,
            plazo_tipo=datos["plazo_tipo"],
            tasa_efectiva_anual=datos["tasa_anual"],
            tasa_mensual=datos["tasa_mensual"]
        )

    except Exception as e:
        print(f"Error en calcular_cliente: {e}")
        flash("Error al calcular", "danger")
        return redirect(url_for("main.home"))

@simulador_bp.route("/calcular_asesor", methods=["POST"])
@login_required
@requiere_permiso("sim_usar")
def calcular_asesor():
    """Cálculo de simulación para asesores (con costos detallados y TEA)"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
        
    from db_helpers_scoring_linea import cargar_scoring_por_linea
    from db_helpers import cargar_evaluaciones, guardar_simulacion

    config = cargar_configuracion()
    lineas_credito = config.get("LINEAS_CREDITO", {})
    costos_asociados = config.get("COSTOS_ASOCIADOS", {})
    seguros_config = config.get("SEGUROS", {})
    scoring_config = cargar_scoring()

    # Capturar valores
    tipo_credito = request.form.get("tipo_credito", "")
    monto_str_original = request.form.get("monto", "")
    plazo_str = request.form.get("plazo", "")
    fecha_nacimiento = request.form.get("fecha_nacimiento", "")
    modalidad_desembolso = request.form.get("modalidad_desembolso", "completo")
    
    # Render helper in case of error
    def render_error(msg, category="warning"):
        flash(msg, category)
        return render_template(
            "asesor/simulador.html",
            lineas=lineas_credito,
            tipo_credito_sel=tipo_credito,
            monto_ingresado=monto_str_original,
            plazo_ingresado=plazo_str,
            fecha_nacimiento_ingresada=fecha_nacimiento,
            modalidad_sel=modalidad_desembolso,
        )

    if not tipo_credito or tipo_credito not in lineas_credito:
        return render_error("Tipo de crédito inválido", "danger")

    datos = lineas_credito[tipo_credito]
    monto_str = monto_str_original.replace(".", "").replace(",", "")

    # Validaciones
    try:
        monto_solicitado = float(monto_str)
    except:
        return render_error("Monto inválido", "danger")

    if not (datos["monto_min"] <= monto_solicitado <= datos["monto_max"]):
        return render_error(f"El monto debe estar entre ${formatear_con_miles(datos['monto_min'])} y ${formatear_con_miles(datos['monto_max'])}")

    try:
        plazo = int(plazo_str)
    except:
        return render_error("Plazo inválido")

    if not (datos["plazo_min"] <= plazo <= datos["plazo_max"]):
        return render_error(f"El plazo debe estar entre {datos['plazo_min']} y {datos['plazo_max']} {datos['plazo_tipo']}")

    try:
        if not fecha_nacimiento:
            return render_error("Fecha de nacimiento requerida")
        edad_cliente = calcular_edad_desde_fecha(fecha_nacimiento)
        if edad_cliente < 18 or edad_cliente > 84:
            return render_error("El cliente debe tener entre 18 y 84 años")
    except:
        return render_error("Fecha de nacimiento inválida")

    # Obtener tasas (dinámicas o fijas)
    timestamp_caso = request.form.get("timestamp_caso")
    tasas_aplicadas = None
    nivel_usado = None
    
    if timestamp_caso:
        try:
            evaluaciones = cargar_evaluaciones()
            caso = next((ev for ev in evaluaciones if ev.get("timestamp") == timestamp_caso), None)
            if caso:
                if caso.get("decision_admin", {}).get("nivel_riesgo_ajustado"):
                    nivel_usado = caso["decision_admin"]["nivel_riesgo_ajustado"]
                elif caso.get("nivel_riesgo"):
                    nivel_usado = caso["nivel_riesgo"]
                elif caso.get("resultado", {}).get("nivel"):
                    nivel_usado = caso["resultado"]["nivel"]
                
                if nivel_usado:
                    # Cargar scoring por línea para pasar a la función
                    scoring_linea_data = cargar_scoring_por_linea(tipo_credito)
                    tasas_aplicadas = obtener_tasa_por_nivel_riesgo(
                        nivel_usado, tipo_credito, scoring_config, scoring_linea_data
                    )
        except Exception as e:
            print(f"Error obteniendo tasas dinámicas: {e}")

    if tasas_aplicadas:
        tasa_mensual_decimal = tasas_aplicadas["tasa_mensual"] / 100
        tasa_mensual_mostrar = tasas_aplicadas["tasa_mensual"]
        tasa_efectiva_anual = tasas_aplicadas["tasa_anual"]
    else:
        tasa_mensual_decimal = datos["tasa_mensual"] / 100
        tasa_mensual_mostrar = datos["tasa_mensual"]
        tasa_efectiva_anual = datos["tasa_anual"]

    plazo_en_meses = plazo if datos["plazo_tipo"] == "meses" else plazo / SEMANAS_POR_MES
    
    seguro_vida = calcular_seguro_proporcional_fecha(
        fecha_nacimiento, monto_solicitado, plazo_en_meses, seguros_config
    )

    # Aval dinámico
    scoring_valido = None
    scoring_guardado = session.get("ultimo_scoring")
    if scoring_guardado and scoring_guardado.get("tipo_credito") == tipo_credito:
        scoring_valido = scoring_guardado
    
    aval = obtener_aval_dinamico(
        monto_solicitado, tipo_credito, datos, scoring_valido, scoring_config
    )

    costos_actuales = costos_asociados.get(tipo_credito, {}).copy()
    costos_actuales["Aval"] = aval
    costos_actuales["Seguro de Vida"] = seguro_vida

    total_costos = sum(costos_actuales.values())
    desembolso_completo = (modalidad_desembolso == "completo")

    if desembolso_completo:
        monto_total_financiar = monto_solicitado + total_costos
        monto_a_desembolsar = monto_solicitado
    else:
        monto_total_financiar = monto_solicitado
        monto_a_desembolsar = monto_solicitado - total_costos
        if monto_a_desembolsar <= 0:
            return render_error(f"Costos superan el monto. Aumenta el monto.", "danger")

    cuota = calcular_cuota(monto_total_financiar, tasa_mensual_decimal, plazo_en_meses)
    tipo_cuota = "Cuota mensual"
    
    if datos["plazo_tipo"] == "semanas":
        cuota = int(round(cuota / SEMANAS_POR_MES))
        tipo_cuota = "Cuota semanal"

    # TEA Calculation logic for display
    tasa_efectiva_real = tasa_efectiva_anual # Placeholder, logic in Flask app was detailed but mainly for logging/checking

    # Guardar en historial si viene de caso
    nombre_cliente = request.form.get("nombre_cliente")
    cedula_cliente = request.form.get("cedula_cliente")

    if timestamp_caso and nombre_cliente and cedula_cliente:
        try:
            simulacion = {
                "timestamp": datetime.now().isoformat(),
                "asesor": session.get("username", "unknown"),
                "cliente": nombre_cliente,
                "cedula": cedula_cliente,
                "monto": int(monto_solicitado),
                "plazo": plazo,
                "linea_credito": tipo_credito,
                "tasa_ea": tasa_efectiva_anual,
                "tasa_mensual": tasa_mensual_mostrar,
                "cuota_mensual": int(cuota),
                "nivel_riesgo": nivel_usado,
                "aval": costos_actuales.get("Aval", 0),
                "seguro": costos_actuales.get("Seguro de Vida", 0),
                "plataforma": costos_actuales.get("plataforma", 0),
                "total_financiar": int(monto_total_financiar),
                "caso_origen": timestamp_caso,
                "modalidad_desembolso": modalidad_desembolso
            }
            guardar_simulacion(simulacion)
        except Exception as e:
            print(f"Error guardando simulación: {e}")

    costos_formateados = {k: formatear_con_miles(v) for k, v in costos_actuales.items()}

    return render_template(
        "asesor/resultado.html",
        tipo_credito=tipo_credito,
        monto_solicitado=formatear_con_miles(monto_solicitado),
        monto_a_desembolsar=formatear_con_miles(monto_a_desembolsar),
        monto_total_financiar=formatear_con_miles(monto_total_financiar),
        cuota=formatear_con_miles(cuota),
        tipo_cuota=tipo_cuota,
        plazo=plazo,
        plazo_tipo=datos["plazo_tipo"],
        tasa_efectiva_anual=tasa_efectiva_anual,
        tasa_mensual=tasa_mensual_mostrar,
        costos=costos_formateados,
        total_costos=formatear_con_miles(total_costos),
        desembolso_completo=desembolso_completo,
        es_simulacion_guardada=bool(timestamp_caso)
    )


@simulador_bp.route("/api/simulaciones_cliente/<cedula>")
@login_required
def api_simulaciones_cliente(cedula):
    """
    API para obtener simulaciones de un cliente específico.
    Usado en el modal de detalle de cliente.
    Respeta el scope del usuario.
    """
    try:
        import sys
        from pathlib import Path
        BASE_DIR = Path(__file__).parent.parent.parent.resolve()
        if str(BASE_DIR) not in sys.path:
            sys.path.insert(0, str(BASE_DIR))
            
        from db_helpers import resolve_visible_usernames, obtener_simulaciones_cliente
        from permisos import obtener_permisos_usuario_actual

        username = session.get("username")
        permisos = obtener_permisos_usuario_actual()

        # Resolver scope
        scope_info = resolve_visible_usernames(username, permisos, "simulaciones")
        usernames_visibles = scope_info.get("usernames_visibles")

        # Obtener simulaciones del cliente
        simulaciones = obtener_simulaciones_cliente(cedula)

        # Filtrar si no tiene acceso a todos
        if usernames_visibles is not None:
            simulaciones = [
                s for s in simulaciones if s.get("asesor") in usernames_visibles
            ]

        return jsonify({"simulaciones": simulaciones, "total": len(simulaciones)}), 200
    except Exception as e:
        print(f"❌ Error en api_simulaciones_cliente: {str(e)}")
        return jsonify({"error": str(e)}), 500
