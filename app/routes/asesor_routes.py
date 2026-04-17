"""
ASESOR_ROUTES.PY - Rutas específicas para asesores
===================================================
"""

from flask import render_template, request, redirect, url_for, session, jsonify, flash
from functools import wraps
import json
import traceback

from . import asesor_bp


def login_required(f):
    """Decorador que requiere autenticación"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("autorizado"):
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function


@asesor_bp.route("/mis-casos-comite")
@login_required
def mis_casos_comite():
    """Ver casos enviados al comité por el asesor"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import obtener_casos_comite

    username = session.get("username")

    # Obtener casos del asesor
    casos_pendientes = obtener_casos_comite({
        "estado_comite": "pending",
        "asesor": username
    })

    casos_aprobados = obtener_casos_comite({
        "estado_comite": "approved",
        "asesor": username,
        "limite": 50
    })

    casos_rechazados = obtener_casos_comite({
        "estado_comite": "rejected",
        "asesor": username,
        "limite": 50
    })

    # Calcular estadísticas para el template
    total_casos = len(casos_pendientes) + len(casos_aprobados) + len(casos_rechazados)
    nuevos_sin_revisar = sum(1 for c in casos_pendientes if not c.get('visto_por_asesor'))

    # Calcular tasa de aprobación
    casos_resueltos = len(casos_aprobados) + len(casos_rechazados)
    tasa_aprobacion = round((len(casos_aprobados) / casos_resueltos * 100) if casos_resueltos > 0 else 0)

    stats = {
        'total_casos': total_casos,
        'pendientes': len(casos_pendientes),
        'aprobados': len(casos_aprobados),
        'rechazados': len(casos_rechazados),
        'nuevos_sin_revisar': nuevos_sin_revisar,
        'tasa_aprobacion': tasa_aprobacion,
        'tiempo_promedio': 'N/A'
    }

    return render_template(
        "asesor/mis_casos_comite.html",
        casos_pendientes=casos_pendientes,
        casos_aprobados=casos_aprobados,
        casos_rechazados=casos_rechazados,
        stats=stats
    )


@asesor_bp.route("/api/casos-comite/cambios")
@login_required
def verificar_cambios_casos():
    """API para verificar si hay cambios en casos del asesor"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import contar_casos_nuevos_asesor

    username = session.get("username")

    casos_nuevos = contar_casos_nuevos_asesor(username)

    return jsonify({
        "casos_nuevos": casos_nuevos,
        "hay_cambios": casos_nuevos > 0
    })


@asesor_bp.route("/marcar-caso-visto/<timestamp>", methods=["POST"])
@login_required
def marcar_caso_visto(timestamp):
    """Marcar un caso como visto por el asesor"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import obtener_evaluacion_por_timestamp, actualizar_evaluacion
    from ..utils.timezone import obtener_hora_colombia

    try:
        # Verificar que el caso pertenece al asesor
        evaluacion = obtener_evaluacion_por_timestamp(timestamp)

        if not evaluacion:
            return jsonify({"error": "Evaluación no encontrada"}), 404

        if evaluacion.get("asesor") != session.get("username"):
            return jsonify({"error": "No autorizado"}), 403

        # Marcar como visto
        actualizar_evaluacion(timestamp, {
            "visto_por_asesor": True,
            "fecha_visto_asesor": obtener_hora_colombia().isoformat()
        })

        return jsonify({
            "success": True,
            "message": "Caso marcado como visto"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@asesor_bp.route("/detalle-evaluacion/<path:timestamp>")
@login_required
def detalle_evaluacion_asesor(timestamp):
    """Ver detalle de una evaluación del asesor"""
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from db_helpers import obtener_evaluacion_por_timestamp

    evaluacion = obtener_evaluacion_por_timestamp(timestamp)

    if not evaluacion:
        flash("Evaluación no encontrada", "error")
        return redirect(url_for("asesor.mis_casos_comite"))

    # Verificar que el caso pertenece al asesor (o es admin)
    if evaluacion.get("asesor") != session.get("username"):
        if session.get("rol") not in ["admin", "admin_tecnico", "comite_credito"]:
            flash("No tienes permiso para ver esta evaluación", "error")
            return redirect(url_for("asesor.mis_casos_comite"))

    return render_template(
        "asesor/resultado.html",
        evaluacion=evaluacion,
        resultado=evaluacion.get("resultado", {}),
        modo="detalle"
    )
