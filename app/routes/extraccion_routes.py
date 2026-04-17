"""
EXTRACCION_ROUTES.PY - Rutas API para extracción automática de datos
=====================================================================

Blueprint: extraccion_bp, prefix='/api/extraccion'
Endpoints:
- POST /api/extraccion/analizar
- POST /api/extraccion/analizar-con-password
- GET  /api/extraccion/fuentes-requeridas/<linea_id>
"""

from flask import Blueprint, request, jsonify, session
from functools import wraps
import traceback
import logging
import re

logger = logging.getLogger(__name__)

extraccion_bp = Blueprint('extraccion', __name__, url_prefix='/api/extraccion')


def extraccion_login_required(f):
    """Decorador que requiere autenticación para endpoints de extracción."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("autorizado"):
            return jsonify({
                'error': 'No autorizado',
                'code': 'AUTH_REQUIRED'
            }), 401
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# POST /api/extraccion/analizar
# ============================================================================
@extraccion_bp.route("/analizar", methods=["POST"])
@extraccion_login_required
def analizar_documentos():
    """
    Recibe múltiples archivos y extrae datos de cada uno usando IA.

    Flujo con cédula como documento maestro:
    1. Si viene cedula_posterior → extraer datos de cédula primero
    2. Usar número de cédula extraído para desbloquear PDFs
    3. Procesar documentos restantes normalmente

    Form data esperado:
    - cedula (string, opcional si viene imagen de cédula)
    - Para cada archivo: campo con nombre = fuente
    """
    try:
        cedula_form = request.form.get("cedula", "").strip()
        ingreso_declarado = request.form.get("ingreso_declarado", "").strip()
        # Línea de crédito para auto-inyectar opciones correctas en el prompt IA
        linea_id_raw = request.form.get("linea_id", "").strip()
        linea_id = int(linea_id_raw) if linea_id_raw.isdigit() else None

        # Recopilar archivos por fuente
        archivos_dict = {}
        cedula_posterior_bytes = None
        cedula_posterior_mime = None
        cedula_frontal_bytes = None
        cedula_frontal_mime = None
        cedula_completa_bytes = None
        cedula_completa_mime = None
        # Archivos extra para multi-archivo (extracto_bancario_2, soporte_ingresos_3, etc.)
        archivos_extra = {}

        for campo, archivo in request.files.items():
            if campo == "cedula":
                continue
            if archivo and archivo.filename:
                archivo_bytes = archivo.read()
                mime_type = archivo.content_type or "application/octet-stream"

                if campo == "cedula_completa":
                    cedula_completa_bytes = archivo_bytes
                    cedula_completa_mime = mime_type
                elif campo == "cedula_posterior":
                    cedula_posterior_bytes = archivo_bytes
                    cedula_posterior_mime = mime_type
                elif campo == "cedula_frontal":
                    cedula_frontal_bytes = archivo_bytes
                    cedula_frontal_mime = mime_type
                else:
                    # Detectar archivos multi-archivo (extracto_bancario_2, soporte_ingresos_3)
                    match_multi = re.match(r'^(extracto_bancario|soporte_ingresos|certificado_seguridad_social)_(\d+)$', campo)
                    if match_multi:
                        base_fuente = match_multi.group(1)
                        if base_fuente not in archivos_extra:
                            archivos_extra[base_fuente] = []
                        archivos_extra[base_fuente].append((archivo_bytes, mime_type))
                    else:
                        archivos_dict[campo] = (archivo_bytes, mime_type)

        # Manejar cedula_completa: usar como ambas caras si no vinieron por separado
        if cedula_completa_bytes and not cedula_posterior_bytes and not cedula_frontal_bytes:
            cedula_posterior_bytes = cedula_completa_bytes
            cedula_posterior_mime = cedula_completa_mime
            cedula_frontal_bytes = cedula_completa_bytes
            cedula_frontal_mime = cedula_completa_mime
            logger.info("Usando cedula_completa como ambas caras (frontal + posterior)")

        tiene_cedula_imagen = cedula_posterior_bytes or cedula_frontal_bytes
        if not cedula_form and not tiene_cedula_imagen:
            return jsonify({
                "success": False,
                "error": "Se requiere cédula o imagen de cédula"
            }), 400

        if not archivos_dict and not tiene_cedula_imagen:
            return jsonify({
                "success": False,
                "error": "No se recibieron archivos para analizar"
            }), 400

        from app.services.extractor_service import ExtractorService
        servicio = ExtractorService()

        # PASO 1a: Extraer datos de cédula posterior (número, nombre, fecha, edad)
        datos_cedula = {}
        cedula_extraida = ""
        if cedula_posterior_bytes:
            logger.info("PASO 1a: Extrayendo datos de cédula desde imagen posterior")
            datos_cedula = servicio.extraer_datos_cedula(cedula_posterior_bytes, cedula_posterior_mime, lado="posterior")
            cedula_extraida = datos_cedula.get("_cedula_numero", "")
            if cedula_extraida:
                logger.info(f"Cédula extraída exitosamente: ***{cedula_extraida[-4:]}")

        # PASO 1b: Extraer nombre desde cédula frontal (prioridad sobre posterior)
        if cedula_frontal_bytes:
            logger.info("PASO 1b: Extrayendo nombre desde imagen frontal de cédula")
            datos_frontal = servicio.extraer_datos_cedula(cedula_frontal_bytes, cedula_frontal_mime, lado="frontal")
            nombre_frontal = datos_frontal.get("_nombre_cliente", "")
            if nombre_frontal:
                datos_cedula["_nombre_cliente"] = nombre_frontal
                logger.info(f"Nombre extraído de cédula frontal: {nombre_frontal}")

        # Determinar cédula final: priorizar la del formulario, fallback a la extraída
        cedula_final = cedula_form or cedula_extraida
        logger.info(f"Cédula final para desbloqueo: ***{cedula_final[-4:] if cedula_final else 'N/A'}")

        # PASO 1c: Combinar archivos extra multi-archivo con el principal
        # Si hay extracto_bancario_2, soporte_ingresos_2, etc., combinar PDFs
        for base_fuente, extras in archivos_extra.items():
            if base_fuente in archivos_dict:
                principal_bytes, principal_mime = archivos_dict[base_fuente]
                es_pdf_principal = "pdf" in (principal_mime or "").lower()
                # Solo combinar PDFs; para imágenes, mantener solo el principal
                if es_pdf_principal:
                    try:
                        import pikepdf
                        import io
                        pdf_combinado = pikepdf.Pdf.new()
                        # Agregar páginas del principal
                        pdf_principal = pikepdf.open(io.BytesIO(principal_bytes))
                        pdf_combinado.pages.extend(pdf_principal.pages)
                        # Agregar páginas de cada extra
                        for extra_bytes, extra_mime in extras:
                            if "pdf" in (extra_mime or "").lower():
                                pdf_extra = pikepdf.open(io.BytesIO(extra_bytes))
                                pdf_combinado.pages.extend(pdf_extra.pages)
                                pdf_extra.close()
                            # Imágenes extra se ignoran en combinación PDF
                        pdf_principal.close()
                        buffer = io.BytesIO()
                        pdf_combinado.save(buffer)
                        pdf_combinado.close()
                        buffer.seek(0)
                        archivos_dict[base_fuente] = (buffer.read(), "application/pdf")
                        logger.info(f"Combinados {1 + len(extras)} PDFs para {base_fuente}")
                    except Exception as e_pdf:
                        logger.warning(f"No se pudieron combinar PDFs para {base_fuente}: {e_pdf}")
                        # Mantener solo el principal si falla la combinación

        # PASO 2: Procesar documentos restantes (sin cedula_frontal/posterior)
        resultado = {}
        if archivos_dict:
            resultado = servicio.extraer_multiples(archivos_dict, cedula_final, ingreso_declarado=ingreso_declarado, linea_id=linea_id)
        else:
            # Solo vino imagen de cédula, sin otros documentos
            resultado = {
                "_fuentes_procesadas": [],
                "_fuentes_error": [],
                "_resumen": {}
            }

        # Incorporar datos de cédula al resultado
        if datos_cedula:
            for campo, valor in datos_cedula.items():
                if valor is not None:
                    resultado[campo] = valor

        # Verificar si algún PDF requiere contraseña
        for fuente in resultado.get("_fuentes_error", []):
            resumen_fuente = resultado.get("_resumen", {}).get(fuente, {})
            if resumen_fuente.get("error") == "PDF protegido - contraseña requerida":
                return jsonify({
                    "success": False,
                    "requiere_password": True,
                    "requiere_password_manual": True,
                    "fuente": fuente,
                    "mensaje": "No se pudo desbloquear el PDF automáticamente. Intenta con: últimos 4 dígitos de la cédula, fecha de nacimiento DDMMAAAA, o contacta al cliente.",
                    "resultado_parcial": resultado
                }), 200

        return jsonify({
            "success": True,
            "datos": resultado
        })

    except Exception as e:
        logger.error(f"Error en /analizar: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# POST /api/extraccion/analizar-con-password
# ============================================================================
@extraccion_bp.route("/analizar-con-password", methods=["POST"])
@extraccion_login_required
def analizar_con_password():
    """
    Reintenta extracción de un documento que falló por contraseña.

    Form data esperado:
    - cedula (string, requerido)
    - password_manual (string, requerido): contraseña del PDF
    - fuente (string, requerido): identificador de la fuente que falló
    - El archivo se envía con name igual al valor de fuente
    """
    try:
        cedula = request.form.get("cedula", "").strip()
        password_manual = request.form.get("password_manual", "").strip()
        fuente = request.form.get("fuente", "").strip()
        linea_id_raw = request.form.get("linea_id", "").strip()
        linea_id = int(linea_id_raw) if linea_id_raw.isdigit() else None

        if not cedula or not fuente:
            return jsonify({
                "success": False,
                "error": "Cédula y fuente son requeridos"
            }), 400

        if not password_manual:
            return jsonify({
                "success": False,
                "error": "Contraseña es requerida"
            }), 400

        # Obtener archivo
        archivo = request.files.get(fuente)
        if not archivo or not archivo.filename:
            return jsonify({
                "success": False,
                "error": f"No se recibió archivo para fuente '{fuente}'"
            }), 400

        archivo_bytes = archivo.read()
        mime_type = archivo.content_type or "application/pdf"

        # Intentar desbloquear con la contraseña manual
        try:
            import pikepdf
            import io
            pdf = pikepdf.open(io.BytesIO(archivo_bytes), password=password_manual)
            buffer = io.BytesIO()
            pdf.save(buffer)
            pdf.close()
            buffer.seek(0)
            archivo_desbloqueado = buffer.read()
        except ImportError:
            archivo_desbloqueado = archivo_bytes
        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"Contraseña incorrecta o PDF dañado: {str(e)}"
            }), 400

        # Ejecutar extracción con el PDF desbloqueado (sin pasar cédula para que no intente desbloquear de nuevo)
        from app.services.extractor_service import ExtractorService
        servicio = ExtractorService()
        resultado = servicio.extraer_desde_documento(
            archivo_bytes=archivo_desbloqueado,
            fuente=fuente,
            cedula=cedula,
            mime_type=mime_type,
            linea_id=linea_id
        )

        if "_error" in resultado:
            return jsonify({
                "success": False,
                "error": resultado["_error"],
                "detalle": resultado
            }), 200

        return jsonify({
            "success": True,
            "datos": resultado
        })

    except Exception as e:
        logger.error(f"Error en /analizar-con-password: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# GET /api/extraccion/fuentes-requeridas/<linea_id>
# ============================================================================
@extraccion_bp.route("/fuentes-requeridas/<int:linea_id>", methods=["GET"])
@extraccion_login_required
def fuentes_requeridas(linea_id):
    """
    Retorna qué fuentes de documentos necesita una línea de crédito.

    Consulta criterios activos de la línea y agrupa por fuente/tipo.
    Útil para mostrarle al analista qué documentos debe subir.
    """
    try:
        from app.services.extractor_service import conectar_db
        conn = conectar_db()
        cursor = conn.cursor()

        # Obtener fuentes únicas de criterios activos para esta línea
        cursor.execute("""
            SELECT DISTINCT csm.fuente_extraccion, csm.activo_extraccion
            FROM criterios_scoring_master csm
            INNER JOIN criterios_linea_credito clc 
                ON csm.id = clc.criterio_master_id
            WHERE clc.linea_credito_id = ?
              AND clc.activo = 1
              AND csm.fuente_extraccion IS NOT NULL
              AND csm.fuente_extraccion != ''
              AND csm.activo_extraccion = 1
        """, (linea_id,))

        filas = cursor.fetchall()
        conn.close()

        # Clasificar fuentes por tipo usando config_extraccion
        from app.config_extraccion import FUENTES_EXTRACCION

        documentos = []
        apis = []
        manuales = []

        for fila in filas:
            fuente_key = fila[0]
            config_fuente = FUENTES_EXTRACCION.get(fuente_key, {})
            tipo = config_fuente.get("tipo", "manual")

            if tipo == "documento":
                documentos.append(fuente_key)
            elif tipo == "api":
                apis.append(fuente_key)
            elif tipo == "manual":
                manuales.append(fuente_key)

        # Siempre incluir cedula_imagen al inicio (card de cédula en todas las líneas)
        if 'cedula_imagen' not in documentos:
            documentos.insert(0, 'cedula_imagen')

        return jsonify({
            "success": True,
            "linea_id": linea_id,
            "documentos": documentos,
            "apis": apis,
            "manuales": manuales,
            "total_fuentes": len(documentos) + len(apis) + len(manuales)
        })

    except Exception as e:
        logger.error(f"Error en /fuentes-requeridas/{linea_id}: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
