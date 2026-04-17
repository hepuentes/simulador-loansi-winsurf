"""
ROUTES.PY - Rutas del módulo psicométrico
==========================================
Maneja el flujo del test: inicio, formulario, guardado parcial,
completado y consulta por cédula.
"""

import json
from datetime import datetime
from flask import (
    request, render_template, jsonify, redirect,
    url_for, abort, current_app
)

from db_helpers_psicometrico import (
    generar_token,
    guardar_respuesta_inicial,
    actualizar_respuestas,
    marcar_completado,
    obtener_por_token,
    obtener_por_cedula,
)
from .scoring_engine import calcular_scores
from . import psicometrico_bp

# Importar CSRFProtect para eximir rutas públicas
from app.extensions import csrf


# Todos los ítems requeridos para completar el test
ITEMS_REQUERIDOS = [
    'a1', 'a2', 'a3', 'a4', 'a5',
    'b1', 'b2', 'b3',
    'c1', 'c2', 'c3', 'c4',
    'd1', 'd2', 'd3', 'd4', 'd5',
    'e1', 'e2', 'e3',
    'atencion_1', 'atencion_2', 'atencion_3',
]

# Rangos válidos por ítem para validación
RANGOS_VALIDOS = {
    'c3': (1, 2),
    'd4': (0, 2),
}
# Por defecto todos los demás son escala Likert 1-5
RANGO_LIKERT = (1, 5)


@psicometrico_bp.route('/iniciar')
def iniciar():
    """
    GET /psicometrico/iniciar
    Genera token, crea registro inicial y redirige al formulario.
    Query params opcionales: cedula, nombre, telefono, canal
    """
    try:
        canal = request.args.get('canal', 'web')
        cedula = request.args.get('cedula')
        nombre = request.args.get('nombre')
        telefono = request.args.get('telefono')

        token = generar_token()
        guardar_respuesta_inicial(
            token=token,
            ip=request.remote_addr,
            user_agent=request.user_agent.string,
            canal=canal
        )

        # Si vienen datos personales, actualizarlos
        datos_extra = {}
        if cedula:
            datos_extra['cedula'] = cedula
        if nombre:
            datos_extra['nombre_completo'] = nombre
        if telefono:
            datos_extra['telefono'] = telefono

        if datos_extra:
            actualizar_respuestas(token, datos_extra, None)

        return redirect(url_for('psicometrico.formulario', token=token))
    except Exception as e:
        current_app.logger.error(f"Error al iniciar test psicométrico: {e}")
        import traceback
        traceback.print_exc()
        abort(500)


@psicometrico_bp.route('/<token>')
def formulario(token):
    """
    GET /psicometrico/<token>
    Muestra el formulario del test psicométrico.
    """
    try:
        registro = obtener_por_token(token)
        if registro is None:
            abort(404)

        if registro.get('completado') == 1:
            return redirect(url_for('psicometrico.gracias', token=token))

        return render_template(
            'psicometrico/formulario.html',
            token=token,
            datos=registro
        )
    except Exception as e:
        current_app.logger.error(f"Error al mostrar formulario (token={token}): {e}")
        import traceback
        traceback.print_exc()
        abort(500)


@psicometrico_bp.route('/<token>/guardar-parcial', methods=['POST'])
@csrf.exempt
def guardar_parcial(token):
    """
    POST /psicometrico/<token>/guardar-parcial
    Guarda respuestas parciales vía AJAX.
    JSON body: {respuestas: {a1: 3, ...}, latencias: {a1: 2100, ...}}
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'ok': False, 'error': 'JSON inválido'}), 400

        respuestas = data.get('respuestas', {})
        latencias = data.get('latencias', {})

        # Validar cada respuesta
        respuestas_validas = {}
        for campo, valor in respuestas.items():
            if campo not in ITEMS_REQUERIDOS and campo not in ('cedula', 'nombre_completo', 'telefono'):
                continue
            if campo in ITEMS_REQUERIDOS:
                try:
                    valor_int = int(valor)
                except (ValueError, TypeError):
                    continue
                min_val, max_val = RANGOS_VALIDOS.get(campo, RANGO_LIKERT)
                if min_val <= valor_int <= max_val:
                    respuestas_validas[campo] = valor_int
            else:
                respuestas_validas[campo] = valor

        latencias_json = json.dumps(latencias) if latencias else None
        actualizar_respuestas(token, respuestas_validas, latencias_json)

        return jsonify({'ok': True})
    except Exception as e:
        current_app.logger.error(f"Error al guardar parcial (token={token}): {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@psicometrico_bp.route('/<token>/completar', methods=['POST'])
@csrf.exempt
def completar(token):
    """
    POST /psicometrico/<token>/completar
    Valida completitud, calcula scores y marca como completado.
    """
    try:
        registro = obtener_por_token(token)
        if registro is None:
            return jsonify({'ok': False, 'error': 'Token no encontrado'}), 404

        if registro.get('completado') == 1:
            return jsonify({
                'ok': True,
                'redirect': url_for('psicometrico.gracias', token=token)
            })

        # Validar que TODAS las preguntas requeridas estén respondidas
        faltantes = [
            item for item in ITEMS_REQUERIDOS
            if registro.get(item) is None
        ]

        if faltantes:
            return jsonify({
                'ok': False,
                'faltantes': faltantes
            }), 400

        # Calcular scores
        resultados = calcular_scores(registro)

        # Actualizar scores y flags en la BD
        actualizar_respuestas(token, {}, None)  # no hay respuestas nuevas
        # Usamos una actualización directa para los campos de scoring
        from db_helpers_psicometrico import conectar_db
        conn = None
        try:
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE psicometrico_respuestas SET
                    score_bloque_a = ?,
                    score_bloque_b = ?,
                    score_bloque_c = ?,
                    score_bloque_d = ?,
                    score_bloque_e = ?,
                    score_total = ?,
                    fallos_atencion = ?,
                    flag_straight_lining = ?,
                    flag_inconsistencia = ?,
                    flag_integridad_baja = ?,
                    estado_validacion = ?,
                    updated_at = ?
                WHERE token = ?
            """, (
                resultados['score_bloque_a'],
                resultados['score_bloque_b'],
                resultados['score_bloque_c'],
                resultados['score_bloque_d'],
                resultados['score_bloque_e'],
                resultados['score_total'],
                resultados['fallos_atencion'],
                resultados['flag_straight_lining'],
                resultados['flag_inconsistencia'],
                resultados['flag_integridad_baja'],
                resultados['estado_validacion'],
                datetime.now().isoformat(),
                token
            ))
            conn.commit()
        except Exception as db_err:
            if conn:
                conn.rollback()
            raise db_err
        finally:
            if conn:
                conn.close()

        # Marcar completado
        marcar_completado(token)

        return jsonify({
            'ok': True,
            'redirect': url_for('psicometrico.gracias', token=token)
        })
    except Exception as e:
        current_app.logger.error(f"Error al completar test (token={token}): {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@psicometrico_bp.route('/<token>/gracias')
def gracias(token):
    """
    GET /psicometrico/<token>/gracias
    Muestra la página de agradecimiento.
    """
    try:
        registro = obtener_por_token(token)
        nombre = registro.get('nombre_completo', '') if registro else ''
        return render_template('psicometrico/gracias.html', nombre=nombre, token=token)
    except Exception as e:
        current_app.logger.error(f"Error al mostrar gracias (token={token}): {e}")
        return render_template('psicometrico/gracias.html', nombre='', token=token)


@psicometrico_bp.route('/api/por-cedula/<cedula>')
def api_por_cedula(cedula):
    """
    GET /psicometrico/api/por-cedula/<cedula>
    Uso interno del sistema de scoring.
    Devuelve JSON con token, scores por bloque, estado, y array de flags activos.
    """
    try:
        registro = obtener_por_cedula(cedula)
        if registro is None:
            return jsonify({'encontrado': False})

        # Construir array de flags activos
        flags = []
        if registro.get('flag_straight_lining'):
            flags.append('straight_lining')
        if registro.get('flag_inconsistencia'):
            flags.append('inconsistencia')
        if registro.get('flag_integridad_baja'):
            flags.append('integridad_baja')
        fallos = registro.get('fallos_atencion') or 0
        if fallos >= 1:
            flags.append(f"atencion_{fallos}_fallos")

        return jsonify({
            'encontrado': True,
            'token': registro.get('token'),
            'score_total': registro.get('score_total'),
            'score_bloque_a': registro.get('score_bloque_a'),
            'score_bloque_b': registro.get('score_bloque_b'),
            'score_bloque_c': registro.get('score_bloque_c'),
            'score_bloque_d': registro.get('score_bloque_d'),
            'score_bloque_e': registro.get('score_bloque_e'),
            'estado_validacion': registro.get('estado_validacion'),
            'fecha_fin': registro.get('fecha_fin'),
            'flags': flags,
        })
    except Exception as e:
        current_app.logger.error(f"Error API por cédula ({cedula}): {e}")
        return jsonify({'encontrado': False, 'error': str(e)}), 500


# =============================================
# Rutas de administración
# =============================================

def _login_required():
    """Verifica que el usuario esté autenticado (mismo patrón del admin)."""
    from flask import session
    if not session.get("autorizado"):
        return redirect(url_for("auth.login"))
    return None


# Mapa de preguntas para el detalle
PREGUNTAS_TEXTO = [
    (1, 'a1', 'Antes de comprar algo caro, pienso primero si me va a alcanzar la plata para el resto del mes.'),
    (2, 'a2', 'Suelo pagar mis cuentas antes de la fecha de vencimiento, no el mismo día.'),
    (3, 'b1', 'Lo que me pasa en la vida depende principalmente de mí.'),
    (4, 'c1', 'Cuando recibo un ingreso extra, lo primero que pienso es en ahorrarlo, no en gastarlo.'),
    (5, 'a3', 'Soy de las personas que arranca proyectos y no los termina.'),
    (6, 'atencion_1', 'Pregunta de atención (esperado: 2)'),
    (7, 'd1', 'Si un cajero me devuelve $50.000 de más sin darse cuenta, se los devuelvo.'),
    (8, 'b2', 'Así uno trabaje duro, si no tiene suerte o palancas, no sale adelante.'),
    (9, 'a4', 'Cumplo con lo que prometo, aunque me toque trasnochar.'),
    (10, 'c2', 'Soy capaz de aguantarme las ganas de comprar algo que me gusta si sé que más adelante podré comprar algo mejor.'),
    (11, 'e1', 'En el último mes, ¿qué tan seguido te preocupaste porque la plata no te alcanzara?'),
    (12, 'd2', 'A veces es necesario decir mentirillas para que un negocio salga bien.'),
    (13, 'a5', 'Llevo algún registro de mis ingresos y gastos.'),
    (14, 'atencion_2', 'Pregunta de atención (esperado: 4)'),
    (15, 'b3', 'Yo soy quien manda en mi plata, no las circunstancias.'),
    (16, 'c3', 'Si tuvieras que elegir: $100.000 HOY vs $130.000 EN UN MES'),
    (17, 'd3', 'Si en mi trabajo me dicen que haga algo incorrecto para cumplir una meta, prefiero no hacerlo.'),
    (18, 'c4', 'Tengo una meta clara de dónde quiero estar con mi plata dentro de un año.'),
    (19, 'e2', 'Si mañana me saliera un gasto imprevisto de $500.000, podría cubrirlo sin pedir prestado.'),
    (20, 'atencion_3', 'Pregunta de atención (esperado: 3)'),
    (21, 'd4', 'Te encuentras $200.000 en la calle sin nadie cerca. ¿Qué haces?'),
    (22, 'e3', 'Estoy tranquilo/a la mayor parte del tiempo.'),
    (23, 'd5', 'Un primo te pide prestados $500.000 y probablemente no te los va a pagar. ¿Se los prestas?'),
]


@psicometrico_bp.route('/admin')
def admin_listado():
    """
    GET /psicometrico/admin
    Lista de tests completados con filtros y paginación.
    """
    redir = _login_required()
    if redir:
        return redir

    try:
        from flask import session
        from database import conectar_db

        estado = request.args.get('estado', 'todos')
        q = request.args.get('q', '').strip()
        page = max(1, int(request.args.get('page', 1)))
        limit = 50
        offset = (page - 1) * limit

        conn = conectar_db()
        cursor = conn.cursor()

        # Construir query con filtros
        where_parts = ['completado = 1']
        params = []

        if estado and estado != 'todos':
            where_parts.append('estado_validacion = ?')
            params.append(estado)

        if q:
            where_parts.append('(cedula LIKE ? OR nombre_completo LIKE ?)')
            params.extend([f'%{q}%', f'%{q}%'])

        where_clause = ' AND '.join(where_parts)

        # Total para paginación
        cursor.execute(f"SELECT COUNT(*) FROM psicometrico_respuestas WHERE {where_clause}", params)
        total = cursor.fetchone()[0]

        # Registros
        cursor.execute(
            f"SELECT * FROM psicometrico_respuestas WHERE {where_clause} ORDER BY fecha_fin DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        )
        registros = cursor.fetchall()
        conn.close()

        return render_template(
            'psicometrico/admin_listado.html',
            registros=registros,
            total=total,
            page=page,
            estado_filtro=estado,
            q=q,
        )
    except Exception as e:
        current_app.logger.error(f"Error en admin listado psicométrico: {e}")
        import traceback
        traceback.print_exc()
        abort(500)


@psicometrico_bp.route('/admin/detalle/<token>')
def admin_detalle(token):
    """
    GET /psicometrico/admin/detalle/<token>
    Detalle completo de un test psicométrico.
    """
    redir = _login_required()
    if redir:
        return redir

    try:
        registro = obtener_por_token(token)
        if registro is None:
            abort(404)

        # Construir lista de flags activos
        flags = []
        if registro.get('flag_straight_lining'):
            flags.append('straight_lining')
        if registro.get('flag_inconsistencia'):
            flags.append('inconsistencia')
        if registro.get('flag_integridad_baja'):
            flags.append('integridad_baja')
        fallos = registro.get('fallos_atencion') or 0
        if fallos >= 1:
            flags.append(f"atencion_{fallos}_fallos")

        # Calcular duración
        duracion = '-'
        if registro.get('fecha_inicio') and registro.get('fecha_fin'):
            try:
                fi = datetime.fromisoformat(registro['fecha_inicio'])
                ff = datetime.fromisoformat(registro['fecha_fin'])
                delta = ff - fi
                mins = int(delta.total_seconds() // 60)
                segs = int(delta.total_seconds() % 60)
                duracion = f"{mins}m {segs}s"
            except Exception:
                duracion = '-'

        # Calcular latencia promedio
        latencia_promedio = '-'
        if registro.get('latencias_json'):
            try:
                lats = json.loads(registro['latencias_json'])
                if lats:
                    vals = [v for v in lats.values() if isinstance(v, (int, float))]
                    if vals:
                        promedio_ms = sum(vals) / len(vals)
                        latencia_promedio = f"{promedio_ms / 1000:.1f}s"
            except Exception:
                latencia_promedio = '-'

        # Construir lista de preguntas con respuestas
        preguntas = []
        for num, campo, texto in PREGUNTAS_TEXTO:
            preguntas.append({
                'num': num,
                'campo': campo,
                'texto': texto,
                'valor': registro.get(campo),
            })

        return render_template(
            'psicometrico/admin_detalle.html',
            r=registro,
            flags=flags,
            duracion=duracion,
            latencia_promedio=latencia_promedio,
            preguntas=preguntas,
        )
    except Exception as e:
        current_app.logger.error(f"Error en admin detalle ({token}): {e}")
        import traceback
        traceback.print_exc()
        abort(500)
