"""
EXTRACTOR_SERVICE.PY - Servicio de extracción automática de datos desde documentos
==================================================================================

Dado un tipo de documento y su contenido, consulta la BD para saber qué criterios
extraer, llama la IA (Anthropic Claude), y retorna los valores mapeados.

Dependencias:
- pikepdf: para desbloquear PDFs protegidos con contraseña
- anthropic: para llamar la API de Claude
- Ambas se manejan con import condicional (no crashea si faltan)
"""

import os
import io
import json
import base64
import logging
import sqlite3
import time
from datetime import datetime

from PIL import Image
from app.services.pdf_fraud_service import analizar_metadatos_pdf
from app.services.validacion_nomina_service import validar_coherencia_nomina
from app.services.validacion_cruzada_service import validar_cruzado

logger = logging.getLogger(__name__)


def comprimir_imagen_si_necesario(archivo_bytes, content_type, max_bytes=3_500_000):
    """Comprime imágenes que excedan el límite de la API (3.5MB raw ~ 4.6MB base64)."""
    print(f"📸 comprimir_imagen_si_necesario: tamaño={len(archivo_bytes):,}, tipo={content_type}")
    if not content_type or 'image' not in content_type:
        return archivo_bytes, content_type

    if len(archivo_bytes) <= max_bytes:
        return archivo_bytes, content_type

    try:
        img = Image.open(io.BytesIO(archivo_bytes))

        # Redimensionar si es muy grande
        max_dimension = 1800
        if max(img.size) > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

        # Comprimir como JPEG
        buffer = io.BytesIO()
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        img.save(buffer, format='JPEG', quality=75, optimize=True)

        resultado = buffer.getvalue()
        print(f"📸 Imagen comprimida: {len(archivo_bytes):,} → {len(resultado):,} bytes")
        return resultado, 'image/jpeg'
    except Exception as e:
        print(f"⚠️ Error comprimiendo imagen: {e}")
        return archivo_bytes, content_type

# Ruta a la base de datos (siguiendo patrón de interpolation_service.py)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "loansi.db")

# Niveles de confianza válidos para priorización
NIVELES_CONFIANZA = {"alta": 3, "media": 2, "baja": 1}


def conectar_db():
    """Conecta a la base de datos SQLite."""
    return sqlite3.connect(DB_PATH)


class ExtractorService:
    """Servicio principal de extracción de datos desde documentos usando IA."""

    def __init__(self):
        """
        Inicializa el servicio.
        Lee el proveedor activo + proveedores de respaldo para failover.
        """
        self.proveedores_disponibles = self._obtener_proveedores_ordenados()
        prov = self.proveedores_disponibles[0] if self.proveedores_disponibles else {}
        self.ia_proveedor_tipo = prov.get("proveedor_tipo", "anthropic")
        self.ia_modelo = prov.get("modelo", "claude-haiku-4-5-20251001")
        self.ia_api_key = prov.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
        self.ia_url_base = prov.get("url_base", "")
        self.ia_activo = prov.get("activo", False)
        # Compatibilidad con código existente
        self.anthropic_key = self.ia_api_key
        if len(self.proveedores_disponibles) > 1:
            nombres = [p["nombre"] for p in self.proveedores_disponibles]
            logger.info(f"Failover configurado: {' → '.join(nombres)}")

    def _obtener_proveedores_ordenados(self):
        """Lee todos los proveedores con API key, ordenados por prioridad (activo primero)."""
        try:
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, nombre, proveedor_tipo, modelo, api_key, url_base, activo
                FROM ia_proveedores
                WHERE api_key IS NOT NULL AND api_key != ''
                ORDER BY activo DESC, prioridad ASC, id ASC
            """)
            rows = cursor.fetchall()
            conn.close()
            proveedores = []
            for row in rows:
                proveedores.append({
                    "id": row[0],
                    "nombre": row[1],
                    "proveedor_tipo": row[2],
                    "modelo": row[3],
                    "api_key": row[4] or "",
                    "url_base": row[5] or "",
                    "activo": bool(row[6])
                })
            return proveedores
        except Exception as e:
            logger.warning(f"No se pudo leer proveedores IA desde BD: {e}")
            return []

    def _obtener_proveedor_activo(self):
        """Retorna el proveedor activo (compatibilidad)."""
        if self.proveedores_disponibles:
            return self.proveedores_disponibles[0]
        return {}

    # ─────────────────────────────────────────────────
    # MÉTODO 1: obtener_criterios_activos
    # ─────────────────────────────────────────────────
    def obtener_criterios_activos(self, fuente, linea_id=None):
        """
        Obtiene los criterios de scoring que tienen extracción activa para una fuente.
        Para criterios tipo select/composite, enriquece con las opciones exactas
        del formulario leídas desde criterios_linea_credito.rangos_json.

        Args:
            fuente (str): Identificador de fuente, ej: "midecisor_pdf"
            linea_id (int|None): ID de la línea de crédito para filtrar opciones

        Returns:
            list[dict]: Lista de criterios con codigo, nombre, tipo, instruccion, opciones_texto
        """
        try:
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, codigo, nombre, tipo_campo, instruccion_extraccion
                FROM criterios_scoring_master
                WHERE fuente_extraccion = ?
                  AND activo_extraccion = 1
                  AND instruccion_extraccion IS NOT NULL
                  AND instruccion_extraccion != ''
            """, (fuente,))

            resultados = []
            for row in cursor.fetchall():
                criterio = {
                    "codigo": row[1],
                    "nombre": row[2],
                    "tipo": row[3],
                    "instruccion": row[4],
                    "opciones_texto": []
                }

                # Enriquecer select/composite con opciones exactas del formulario
                if criterio["tipo"] in ("select", "composite", "compuesto"):
                    if linea_id:
                        # Filtrar por línea específica
                        cursor.execute("""
                            SELECT rangos_json 
                            FROM criterios_linea_credito 
                            WHERE criterio_master_id = ?
                              AND linea_credito_id = ?
                              AND activo = 1
                        """, (row[0], linea_id))
                    else:
                        # Fallback: tomar primera línea activa
                        cursor.execute("""
                            SELECT rangos_json 
                            FROM criterios_linea_credito 
                            WHERE criterio_master_id = ?
                              AND activo = 1
                            LIMIT 1
                        """, (row[0],))
                    rangos_row = cursor.fetchone()
                    if rangos_row and rangos_row[0]:
                        try:
                            rangos = json.loads(rangos_row[0])
                            criterio["opciones_texto"] = [
                                r.get("descripcion", "")
                                for r in rangos
                                if r.get("descripcion")
                            ]
                        except (json.JSONDecodeError, TypeError):
                            pass

                resultados.append(criterio)

            conn.close()

            logger.info(f"Criterios activos para '{fuente}' (linea={linea_id}): {len(resultados)}")
            return resultados

        except Exception as e:
            logger.error(f"Error obteniendo criterios activos para '{fuente}': {e}")
            return []

    # ─────────────────────────────────────────────────
    # MÉTODO 2: desbloquear_pdf
    # ─────────────────────────────────────────────────
    def desbloquear_pdf(self, pdf_bytes, cedula):
        """
        Intenta abrir un PDF protegido con múltiples contraseñas comunes
        usadas por bancos colombianos.

        Orden de intentos:
        1. Sin contraseña (PDF no protegido)
        2. Cédula completa: "1094883403" (Bancolombia, Nequi, Nu)
        3. Últimos 4 dígitos: "3403" (Falabella, algunos otros)
        4. Primeros 4 dígitos: "1094" (poco común)
        5. Cero + últimos 4: "03403" (variante con cero adelante)
        6. Cédula con puntos: "1.094.883.403"

        Args:
            pdf_bytes (bytes): Contenido del PDF
            cedula (str): Número de cédula del cliente

        Returns:
            tuple: (pdf_bytes_desbloqueado, password_usada) o (None, None)
        """
        try:
            import pikepdf
        except ImportError:
            logger.warning("pikepdf no instalado - retornando PDF sin procesar")
            return (pdf_bytes, "")

        import io

        cedula_limpia = str(cedula).replace(".", "").replace(",", "").replace(" ", "").strip()
        cedula_con_puntos = self._formatear_cedula_con_puntos(cedula_limpia)

        passwords_a_intentar = [
            ("sin_password", None),
            ("cedula_completa", cedula_limpia),
            ("ultimos_4", cedula_limpia[-4:] if len(cedula_limpia) >= 4 else None),
            ("primeros_4", cedula_limpia[:4] if len(cedula_limpia) >= 4 else None),
            ("cero_ultimos_4", f"0{cedula_limpia[-4:]}" if len(cedula_limpia) >= 4 else None),
            ("cedula_con_puntos", cedula_con_puntos),
        ]

        for nombre, password in passwords_a_intentar:
            if password is None and nombre != "sin_password":
                continue
            try:
                if password is not None:
                    pdf = pikepdf.open(io.BytesIO(pdf_bytes), password=str(password))
                else:
                    pdf = pikepdf.open(io.BytesIO(pdf_bytes))

                # Guardar PDF desbloqueado en bytes
                buffer = io.BytesIO()
                pdf.save(buffer)
                pdf.close()
                buffer.seek(0)
                pdf_desbloqueado = buffer.read()

                if password:
                    logger.info(f"PDF desbloqueado con '{nombre}' (***{cedula_limpia[-4:]})")
                else:
                    logger.info("PDF abierto sin contraseña")

                return (pdf_desbloqueado, password or "")

            except pikepdf.PasswordError:
                continue
            except Exception as e:
                logger.warning(f"Error intentando abrir PDF con '{nombre}': {e}")
                continue

        logger.warning(f"No se pudo desbloquear PDF con ninguna contraseña para cédula ***{cedula_limpia[-4:]}")
        return (None, None)

    # ─────────────────────────────────────────────────
    # MÉTODO 3: construir_prompt
    # ─────────────────────────────────────────────────
    def construir_prompt(self, criterios, fuente=None):
        """
        Construye el prompt completo para la IA a partir de los criterios a extraer.

        Args:
            criterios (list[dict]): Lista de criterios del método obtener_criterios_activos

        Returns:
            str: Prompt completo para enviar a la IA
        """
        # Construir el bloque de campos a extraer
        campos_json_lines = []
        for c in criterios:
            instruccion_base = c.get("instruccion", "")
            tipo = c.get("tipo", "")
            opciones = c.get("opciones_texto", [])

            if tipo in ("select", "composite", "compuesto") and opciones:
                # Auto-inyectar opciones exactas del formulario
                opciones_lista = " | ".join(opciones)
                instruccion_final = (
                    f"{instruccion_base}. "
                    f"IMPORTANTE: Retornar EXACTAMENTE uno de estos valores "
                    f"tal cual están escritos, sin modificar: {opciones_lista}"
                )
            elif tipo in ("number", "numeric", "numerico", "currency"):
                instruccion_final = (
                    f"{instruccion_base}. "
                    f"Retornar SOLO el número entero sin puntos, comas, "
                    f"ni signos de moneda (ej: 1423500)"
                )
            else:
                instruccion_final = instruccion_base

            campos_json_lines.append(
                f'  "{c["codigo"]}": null  // EXTRAER: {instruccion_final}'
            )

        # Campos adicionales de validacion interna para soporte_ingresos
        if fuente == 'soporte_ingresos':
            campos_validacion = [
                ('"_salario_basico": null', 'Salario basico mensual en pesos (numero entero sin puntos). Ej: 2500000'),
                ('"_deduccion_salud": null', 'Deduccion por salud/EPS del empleado en pesos (numero entero)'),
                ('"_deduccion_pension": null', 'Deduccion por pension del empleado en pesos (numero entero)'),
                ('"_total_devengados": null', 'Total devengados/ingresos brutos en pesos (numero entero)'),
                ('"_total_deducciones": null', 'Total deducciones/descuentos en pesos (numero entero)'),
                ('"_neto_pagar": null', 'Neto a pagar al empleado en pesos (numero entero)'),
                ('"_subsidio_transporte": null', 'Auxilio/subsidio de transporte en pesos o null si no aplica'),
                ('"_fondo_solidaridad": null', 'Fondo de solidaridad pensional en pesos o null si no aplica'),
            ]
            for campo, instruccion in campos_validacion:
                campos_json_lines.append(f'  {campo}  // EXTRAER: {instruccion}')

        # Campos de metadatos siempre incluidos
        campos_json_lines.append('  "_documento_detectado": null  // EXTRAER: nombre del tipo de documento identificado')
        campos_json_lines.append('  "_alertas": []  // EXTRAER: lista de alertas o inconsistencias encontradas')
        campos_json_lines.append('  "_confianza": null  // EXTRAER: alta|media|baja según claridad del documento')

        # DEBUG TEMPORAL — ver auto-inyección de opciones
        for line in campos_json_lines:
            if "EXACTAMENTE" in line:
                print(f"  📝 Auto-inyección: {line[:150]}...")
        # FIN DEBUG

        campos_json = ",\n".join(campos_json_lines)

        # Construir bloque de tipos esperados
        tipos_lineas = []
        for c in criterios:
            tipo = c.get("tipo", "number")
            descripcion_tipo = self._descripcion_tipo(tipo)
            tipos_lineas.append(f"  {c['codigo']} → {descripcion_tipo}")

        tipos_texto = "\n".join(tipos_lineas)

        prompt = f"""Eres un analista de riesgo crediticio. Analiza el documento y extrae los datos solicitados.

REGLAS ESTRICTAS DE FORMATO:
- Retorna ÚNICAMENTE JSON válido, sin markdown, sin texto adicional, sin explicaciones.
- NO incluyas campos con valor null — omítelos del JSON.
- Usa valores compactos: números sin formato, strings cortos.
- NO agregues campos adicionales que no se pidieron.

Campos a extraer:
{{
{campos_json}
}}

Tipos esperados:
{tipos_texto}"""

        return prompt

    # ─────────────────────────────────────────────────
    # MÉTODO 4: extraer_desde_documento
    # ─────────────────────────────────────────────────
    def extraer_desde_documento(self, archivo_bytes, fuente, cedula=None, mime_type=None, ingreso_declarado=None, linea_id=None):
        """
        Extrae datos de un documento usando IA.

        Args:
            archivo_bytes (bytes): Contenido del archivo
            fuente (str): Tipo de fuente (ej: "midecisor_pdf")
            cedula (str): Cédula del cliente (para desbloquear PDFs)
            mime_type (str): Tipo MIME del archivo
            ingreso_declarado (str): Ingreso declarado por el solicitante (contexto)
            linea_id (int|None): ID de la línea de crédito para opciones correctas

        Returns:
            dict: Valores extraídos + metadatos, nunca propaga excepciones
        """
        timestamp_inicio = datetime.now()

        try:
            # Paso 1: Obtener criterios activos (con opciones de la línea correcta)
            criterios = self.obtener_criterios_activos(fuente, linea_id=linea_id)

            if not criterios:
                return {
                    "_error": "No hay criterios activos para esta fuente",
                    "_criterios_encontrados": 0,
                    "_fuente": fuente
                }

            # Paso 2: Si es PDF, intentar desbloquear
            es_pdf = (mime_type and "pdf" in mime_type.lower()) or fuente.endswith("_pdf")

            if es_pdf and cedula:
                archivo_bytes, password_usada = self.desbloquear_pdf(archivo_bytes, cedula)
                if archivo_bytes is None:
                    return {
                        "_error": "PDF protegido - contraseña requerida",
                        "_requiere_password": True,
                        "_fuente": fuente
                    }

            # Paso 2.5: Analizar metadatos del PDF para detección de fraude
            fraude_metadatos = None
            if es_pdf:
                try:
                    fraude_metadatos = analizar_metadatos_pdf(archivo_bytes)
                    if fraude_metadatos and fraude_metadatos.get("riesgo") == "alto":
                        logger.warning(
                            f"⚠️ ALERTA FRAUDE: {fuente} - {fraude_metadatos.get('alertas', [])}"
                        )
                    elif fraude_metadatos and fraude_metadatos.get("riesgo") == "medio":
                        logger.info(
                            f"⚠️ Metadatos sospechosos: {fuente} - {fraude_metadatos.get('alertas', [])}"
                        )
                except Exception as e_fraude:
                    logger.warning(f"Error en análisis de metadatos de {fuente}: {e_fraude}")
                    fraude_metadatos = {
                        "riesgo": "medio",
                        "alertas": ["Error al analizar metadatos del PDF"],
                        "detalle": f"No se pudieron leer metadatos: {str(e_fraude)[:100]}"
                    }

            # Paso 3: Verificar que hay proveedor activo y configurado
            if not self.ia_activo:
                return {
                    "_error": "No hay proveedor de IA activo. Configura uno en Admin > Integraciones.",
                    "_fuente": fuente,
                    "_criterios_encontrados": len(criterios)
                }

            if not self.ia_api_key and self.ia_proveedor_tipo != "openai_compatible":
                return {
                    "_error": "API key no configurada en el proveedor activo",
                    "_fuente": fuente,
                    "_criterios_encontrados": len(criterios)
                }

            # Paso 4: Construir prompt
            prompt = self.construir_prompt(criterios, fuente=fuente)

            # Agregar contexto de ingreso declarado para fuentes que lo necesitan
            if ingreso_declarado and fuente in ('soporte_ingresos', 'extracto_bancario'):
                prompt += f"\n\nCONTEXTO ADICIONAL: El solicitante declaró un ingreso mensual de ${ingreso_declarado} COP. Compara con lo que dice el documento."

            # Paso 4.5: Comprimir imagen si supera 3.5MB (base64 +33% no debe pasar 5MB)
            if not es_pdf:
                archivo_bytes, mime_type = comprimir_imagen_si_necesario(archivo_bytes, mime_type)

            # Paso 5: Convertir archivo a base64
            archivo_b64 = base64.standard_b64encode(archivo_bytes).decode("utf-8")

            modelo = self.ia_modelo or "claude-haiku-4-5-20251001"
            key_parcial = self.ia_api_key[-6:] if self.ia_api_key else 'N/A'
            logger.info(f"Llamando IA: tipo={self.ia_proveedor_tipo}, modelo={modelo}, key=***{key_parcial}")

            # Paso 6-7: Llamar API según tipo de proveedor
            texto_respuesta = self._llamar_ia(
                archivo_bytes=archivo_bytes,
                archivo_b64=archivo_b64,
                es_pdf=es_pdf,
                mime_type=mime_type,
                prompt=prompt,
                modelo=modelo
            )

            logger.info(f"[EXTRACTOR DEBUG] Respuesta cruda IA:\n{texto_respuesta[:2000]}")
            datos = self._parsear_json_respuesta(texto_respuesta)

            if datos is None:
                return {
                    "_error": "respuesta_invalida",
                    "_respuesta_raw": texto_respuesta[:500],
                    "_fuente": fuente
                }

            # Paso 9: Validar campos retornados
            codigos_validos = {c["codigo"] for c in criterios}
            campos_meta = {"_documento_detectado", "_alertas", "_confianza"}
            # Campos de validacion interna de nomina (no se pre-llenan, solo validacion matematica)
            campos_validacion_nomina = set()
            if fuente == 'soporte_ingresos':
                campos_validacion_nomina = {
                    "_salario_basico", "_deduccion_salud", "_deduccion_pension",
                    "_total_devengados", "_total_deducciones", "_neto_pagar",
                    "_subsidio_transporte", "_fondo_solidaridad"
                }
            codigos_permitidos = codigos_validos | campos_meta | campos_validacion_nomina

            datos_filtrados = {
                k: v for k, v in datos.items()
                if k in codigos_permitidos
            }

            # Fallback: extraer nombre del titular desde MiDecisor si no vino
            if fuente == 'midecisor_pdf' and '_nombre_cliente' not in datos_filtrados:
                prompt_nombre = """En el encabezado o datos personales de este reporte MiDecisor/DataCrédito, busca el nombre completo del titular.
Puede aparecer como:
- "Nombre completo: PUENTES GONZALEZ HECTOR FABIO"
- "Titular: PUENTES GONZALEZ HECTOR FABIO"
- Un nombre en mayúsculas en la parte superior del reporte

Retorna SOLO el nombre completo en mayúsculas.
Formato: APELLIDO1 APELLIDO2 NOMBRE1 NOMBRE2
Ejemplo: PUENTES GONZALEZ HECTOR FABIO
Solo el nombre, sin JSON, sin explicación.
Si no lo encuentras retorna cadena vacía."""
                try:
                    respuesta_nombre = self._llamar_ia(
                        archivo_bytes=archivo_bytes,
                        archivo_b64=archivo_b64,
                        es_pdf=es_pdf,
                        mime_type=mime_type,
                        prompt=prompt_nombre,
                        modelo=modelo
                    )
                    nombre_extraido = (respuesta_nombre or "").strip()
                    if nombre_extraido:
                        datos_filtrados['_nombre_cliente'] = nombre_extraido
                        logger.info(f"[MIDECISOR] Nombre extraído por fallback: {nombre_extraido}")
                except Exception as e_nombre:
                    logger.warning(f"[MIDECISOR] No se pudo extraer nombre: {e_nombre}")

            # Agregar resultado de análisis de fraude en metadatos PDF
            if fraude_metadatos:
                datos_filtrados[f"_fraude_metadatos_{fuente}"] = fraude_metadatos

            # Agregar metadatos de la extracción
            duracion = (datetime.now() - timestamp_inicio).total_seconds()
            datos_filtrados["_fuente"] = fuente
            datos_filtrados["_criterios_solicitados"] = len(criterios)
            datos_filtrados["_criterios_extraidos"] = len([
                k for k in datos_filtrados
                if not k.startswith("_") and datos_filtrados[k] is not None
            ])
            datos_filtrados["_duracion_segundos"] = round(duracion, 2)

            # Paso 10: Log
            confianza = datos_filtrados.get("_confianza", "desconocida")
            cedula_parcial = f"***{cedula[-4:]}" if cedula and len(cedula) >= 4 else "N/A"
            logger.info(
                f"Extracción completada: fuente={fuente}, cedula={cedula_parcial}, "
                f"criterios={datos_filtrados['_criterios_extraidos']}/{len(criterios)}, "
                f"confianza={confianza}, duracion={duracion:.1f}s"
            )

            return datos_filtrados

        except Exception as e:
            # Detectar timeout
            error_str = str(e).lower()
            if "timeout" in error_str or "timed out" in error_str:
                logger.error(f"Timeout en extracción desde '{fuente}': {e}")
                return {
                    "_error": "timeout",
                    "_fuente": fuente,
                    "_detalle": "La API tardó más de 30 segundos en responder"
                }

            logger.error(f"Error en extracción desde '{fuente}': {e}")
            return {
                "_error": str(e),
                "_fuente": fuente
            }

    # ─────────────────────────────────────────────────
    # MÉTODO 5: extraer_multiples
    # ─────────────────────────────────────────────────
    def extraer_multiples(self, archivos_dict, cedula, ingreso_declarado=None, linea_id=None):
        """
        Extrae datos de múltiples documentos y combina los resultados.

        Si el mismo código aparece en múltiples documentos, prevalece
        el del documento con mayor _confianza.

        Args:
            archivos_dict (dict): {"midecisor_pdf": (bytes, mime_type), ...}
            cedula (str): Cédula del cliente
            ingreso_declarado (str): Ingreso declarado por el solicitante (contexto)
            linea_id (int|None): ID de la línea de crédito para opciones correctas

        Returns:
            dict: Valores combinados + metadatos de todas las fuentes
        """
        resultados_por_fuente = {}
        fuentes_procesadas = []
        fuentes_error = []
        resumen = {}

        for fuente, archivo_info in archivos_dict.items():
            # Aceptar tanto bytes directos como tupla (bytes, mime_type)
            if isinstance(archivo_info, tuple):
                archivo_bytes, mime_type = archivo_info
            else:
                archivo_bytes = archivo_info
                mime_type = None

            resultado = self.extraer_desde_documento(
                archivo_bytes=archivo_bytes,
                fuente=fuente,
                cedula=cedula,
                mime_type=mime_type,
                ingreso_declarado=ingreso_declarado,
                linea_id=linea_id
            )

            if "_error" in resultado:
                fuentes_error.append(fuente)
                resumen[fuente] = {
                    "error": resultado["_error"],
                    "criterios": 0,
                    "confianza": None
                }
            else:
                fuentes_procesadas.append(fuente)
                resumen[fuente] = {
                    "criterios": resultado.get("_criterios_extraidos", 0),
                    "confianza": resultado.get("_confianza", "desconocida")
                }

            resultados_por_fuente[fuente] = resultado

        # Combinar valores: prevalece el de mayor confianza
        valores_combinados = {}

        for fuente, resultado in resultados_por_fuente.items():
            if "_error" in resultado:
                continue

            confianza_fuente = NIVELES_CONFIANZA.get(
                resultado.get("_confianza", "baja"), 1
            )

            for campo, valor in resultado.items():
                if campo.startswith("_"):
                    continue
                if valor is None:
                    continue

                # Si el campo ya existe, comparar confianza
                if campo in valores_combinados:
                    confianza_existente = valores_combinados[campo]["_confianza_nivel"]
                    if confianza_fuente > confianza_existente:
                        valores_combinados[campo] = {
                            "valor": valor,
                            "_confianza_nivel": confianza_fuente,
                            "_fuente_origen": fuente
                        }
                else:
                    valores_combinados[campo] = {
                        "valor": valor,
                        "_confianza_nivel": confianza_fuente,
                        "_fuente_origen": fuente
                    }

        # Aplanar resultado final
        resultado_final = {}
        for campo, info in valores_combinados.items():
            resultado_final[campo] = info["valor"]

        # Agregar metadatos globales
        resultado_final["_fuentes_procesadas"] = fuentes_procesadas
        resultado_final["_fuentes_error"] = fuentes_error
        resultado_final["_resumen"] = resumen

        # Propagar datos de fraude de metadatos PDF al resultado final
        for fuente, resultado in resultados_por_fuente.items():
            for clave, valor in resultado.items():
                if clave.startswith("_fraude_metadatos_"):
                    resultado_final[clave] = valor

        # Validación matemática de nómina si se procesó soporte_ingresos
        if "soporte_ingresos" in resultados_por_fuente and "_error" not in resultados_por_fuente["soporte_ingresos"]:
            try:
                datos_nomina = resultados_por_fuente["soporte_ingresos"]
                # Incluir campos de validacion interna (_salario_basico, etc.) y criterios normales
                datos_para_validar = {k: v for k, v in datos_nomina.items()
                                      if not k.startswith("_") or k in (
                                          "_salario_basico", "_deduccion_salud", "_deduccion_pension",
                                          "_total_devengados", "_total_deducciones", "_neto_pagar",
                                          "_subsidio_transporte", "_fondo_solidaridad"
                                      )}
                validacion = validar_coherencia_nomina(datos_para_validar)
                resultado_final["_validacion_nomina"] = validacion
                if validacion.get("coherencia") == "baja":
                    logger.warning(f"⚠️ Nómina con coherencia BAJA: {validacion.get('alertas', [])}")

                # ============================================
                # EXPONER INGRESO VERIFICADO para pre-llenado
                # ============================================
                # Usa datos_nomina del servicio de validacion (salario_basico es el recurrente)
                # Prioridad: salario_basico > neto_pagar > total_devengados
                if validacion.get("validaciones_pasadas", 0) >= 3:
                    datos_val_nomina = validacion.get("datos_nomina", {})
                    
                    if datos_val_nomina:
                        # PRIORIDAD 1: Salario basico — ingreso mensual recurrente
                        # NO incluye prima, cesantias, ni pagos extraordinarios
                        salario_base = datos_val_nomina.get("salario_basico", 0)
                        neto_pagar = datos_val_nomina.get("neto_pagar", 0)
                        total_dev = datos_val_nomina.get("total_devengados", 0)
                        
                        ingreso_final = 0
                        etiqueta = ""
                        
                        if salario_base and float(salario_base) > 100000:
                            ingreso_final = float(salario_base)
                            etiqueta = "salario_basico"
                        elif neto_pagar and float(neto_pagar) > 100000:
                            ingreso_final = float(neto_pagar)
                            etiqueta = "neto_pagar (puede incluir prima/cesantias)"
                        elif total_dev and float(total_dev) > 100000:
                            ingreso_final = float(total_dev)
                            etiqueta = "total_devengados (incluye todos los conceptos)"
                        
                        if ingreso_final > 0:
                            resultado_final["_ingreso_verificado"] = ingreso_final
                            resultado_final["_fuente_verificacion"] = "Nómina"
                            logger.info(f"💰 Ingreso verificado ({etiqueta}): ${ingreso_final:,.0f}")
                        else:
                            logger.info(f"⚠️ datos_nomina sin valores validos: {datos_val_nomina}")
                    else:
                        # Fallback: datos_nomina no disponible, buscar en datos crudos de IA
                        for key in ["_salario_basico", "_neto_pagar", "_total_devengados"]:
                            raw_val = datos_nomina.get(key)
                            if raw_val:
                                try:
                                    valor = float(str(raw_val).replace(".", "").replace(",", ".").replace("$", "").strip())
                                    if valor > 100000:
                                        resultado_final["_ingreso_verificado"] = valor
                                        resultado_final["_fuente_verificacion"] = "Nómina"
                                        logger.info(f"💰 Ingreso verificado (fallback {key}): ${valor:,.0f}")
                                        break
                                except (ValueError, TypeError):
                                    pass
                    
                    # Siempre marcar la fuente si hubo nomina
                    if "_fuente_verificacion" not in resultado_final:
                        resultado_final["_fuente_verificacion"] = "Nómina"
            except Exception as e_val:
                logger.warning(f"Error en validación de nómina: {e_val}")

        # Validación cruzada entre documentos (si hay 2+ fuentes exitosas)
        if len(fuentes_procesadas) >= 2:
            try:
                validacion_cruzada = validar_cruzado(resultados_por_fuente)
                resultado_final["_validacion_cruzada"] = validacion_cruzada
                if validacion_cruzada.get("nivel_riesgo") == "alto":
                    logger.warning(
                        f"⚠️ Validación cruzada RIESGO ALTO: "
                        f"{validacion_cruzada.get('resumen', '')}"
                    )
            except Exception as e_cruzada:
                logger.warning(f"Error en validación cruzada: {e_cruzada}")

        # Alertas IA de nómina (libranzas, prima, etc.)
        # _validacion_nomina ya está en resultado_final como dict
        _val_nomina = resultado_final.get('_validacion_nomina')
        if _val_nomina:
            datos_nomina = _val_nomina.get('datos_nomina', {})
            alertas_ia_nomina = datos_nomina.get('alertas_ia', []) or []
        else:
            alertas_ia_nomina = []
        resultado_final['_alertas_nomina_ia'] = alertas_ia_nomina
        if alertas_ia_nomina:
            print(f"  🔍 Alertas IA nómina: {alertas_ia_nomina}")

        logger.info(
            f"Extracción múltiple completada: "
            f"{len(fuentes_procesadas)} OK, {len(fuentes_error)} errores, "
            f"{len(resultado_final) - 3} campos extraídos"
        )

        return resultado_final

    # ─────────────────────────────────────────────────
    # MÉTODO 6: extraer_datos_cedula
    # ─────────────────────────────────────────────────
    def extraer_datos_cedula(self, imagen_bytes, mime_type=None, lado="posterior"):
        """
        Extrae datos de una imagen de cédula colombiana.

        lado='posterior': extrae número, nombre, fecha nacimiento, edad
        lado='frontal': extrae solo nombre del titular

        Args:
            imagen_bytes (bytes): Contenido de la imagen
            mime_type (str): Tipo MIME
            lado (str): 'posterior' o 'frontal'

        Returns:
            dict con los campos extraídos o dict vacío si falla
        """
        if not self.ia_activo or not self.ia_api_key:
            logger.warning("No hay proveedor IA activo para extraer datos de cédula")
            return {}

        if lado == "frontal":
            prompt = """Lee esta cédula de ciudadanía colombiana (parte delantera).
Colombia tiene DOS formatos de cédula:

FORMATO NUEVO (fondo azul/verde con mariposa):
- Busca campo "Apellidos:" → valor debajo o al lado
- Busca campo "Nombres:" → valor debajo o al lado

FORMATO ANTIGUO (fondo amarillo):
- Busca el texto en mayúsculas sobre la palabra "APELLIDOS"
- Busca el texto en mayúsculas sobre la palabra "NOMBRES"

En AMBOS formatos retorna SOLO este JSON:
{
  "_nombre_cliente": "APELLIDO1 APELLIDO2 NOMBRE1 NOMBRE2"
}
Ejemplo: {"_nombre_cliente": "PUENTES GONZALEZ HECTOR FABIO"}
Solo el JSON, nada más."""
        else:
            prompt = """Analiza esta imagen de cédula de ciudadanía colombiana (parte trasera, donde están los datos personales).

Extrae EXACTAMENTE estos datos y responde SOLO con JSON válido, sin markdown:

{
  "_cedula_numero": null,
  "_nombre_cliente": null,
  "_fecha_nacimiento": null,
  "_edad_solicitante": null,
  "_sexo_cedula": null
}

Instrucciones por campo:
- _cedula_numero: Extrae el número de cédula. Puede aparecer como "C.C. 1.094.883.403" o "1094883403". Retorna SOLO dígitos sin puntos, comas ni espacios. Ejemplo: "1094883403"
- _nombre_cliente: Extrae apellidos y nombres completos. Formato: APELLIDO1 APELLIDO2 NOMBRE1 NOMBRE2. Ejemplo: "PUENTES GARCIA HECTOR ANDRES"
- _fecha_nacimiento: Extrae la fecha de nacimiento. Retorna en formato YYYY-MM-DD. Ejemplo: "1990-05-23"
- _edad_solicitante: Calcula la edad en años completos desde la fecha de nacimiento hasta hoy (marzo 2026). Retorna solo el número entero.
- _sexo_cedula: Busca el campo "SEXO" en la cédula. En la cédula amarilla está en el reverso junto al código de barras. En la cédula digital está en el frente junto a la foto. Valores posibles: "F" (femenino), "M" (masculino). Retorna SOLO la letra: F o M. Si no se puede leer, retorna null.

Responde ÚNICAMENTE con el JSON, nada más."""

        try:
            es_pdf = mime_type and "pdf" in mime_type.lower()

            # Comprimir imagen si supera 3.5MB (base64 +33% no debe pasar 5MB)
            if not es_pdf:
                imagen_bytes, mime_type = comprimir_imagen_si_necesario(imagen_bytes, mime_type or "image/jpeg")

            archivo_b64 = base64.standard_b64encode(imagen_bytes).decode("utf-8")
            modelo = self.ia_modelo or "claude-haiku-4-5-20251001"

            logger.info(f"Extrayendo datos de cédula ({lado}) con {self.ia_proveedor_tipo}, modelo={modelo}")

            texto_respuesta = self._llamar_ia(
                archivo_bytes=imagen_bytes,
                archivo_b64=archivo_b64,
                es_pdf=es_pdf,
                mime_type=mime_type or "image/jpeg",
                prompt=prompt,
                modelo=modelo
            )

            logger.info(f"[CEDULA] Respuesta cruda:\n{texto_respuesta[:500]}")
            datos = self._parsear_json_respuesta(texto_respuesta)

            if not datos:
                logger.warning("No se pudo parsear respuesta de extracción de cédula")
                return {}

            # Limpiar número de cédula (solo dígitos)
            if datos.get("_cedula_numero"):
                cedula_limpia = "".join(c for c in str(datos["_cedula_numero"]) if c.isdigit())
                datos["_cedula_numero"] = cedula_limpia

            # Validar edad como entero
            if datos.get("_edad_solicitante"):
                try:
                    datos["_edad_solicitante"] = int(datos["_edad_solicitante"])
                except (ValueError, TypeError):
                    datos["_edad_solicitante"] = None

            logger.info(f"[CEDULA] Datos extraídos: numero=***{str(datos.get('_cedula_numero', ''))[-4:]}, nombre={datos.get('_nombre_cliente', 'N/A')}")
            return datos

        except Exception as e:
            logger.error(f"Error extrayendo datos de cédula: {e}")
            return {}

    # ─────────────────────────────────────────────────
    # Métodos auxiliares privados
    # ─────────────────────────────────────────────────
    def _formatear_cedula_con_puntos(self, cedula_limpia):
        """Formatea cédula con puntos de miles: 1094883403 → 1.094.883.403"""
        try:
            numero = int(cedula_limpia)
            return f"{numero:,}".replace(",", ".")
        except (ValueError, TypeError):
            return cedula_limpia

    def _descripcion_tipo(self, tipo_campo):
        """Retorna descripción del tipo de valor esperado para el prompt."""
        descripciones = {
            "number": "número entero o decimal, nunca string",
            "currency": "número entero en pesos colombianos, sin puntos ni símbolos",
            "percentage": "número decimal 0-100, sin el símbolo %",
            "select": "el valor de texto exacto según las opciones descritas",
            "composite": "el valor de texto exacto según las opciones descritas",
            "boolean": "true o false",
            "text": "texto libre"
        }
        return descripciones.get(tipo_campo, "número entero o decimal, nunca string")

    def _llamar_ia(self, archivo_bytes, archivo_b64, es_pdf, mime_type, prompt, modelo):
        """
        Llama a la API de IA con failover automático.
        Si el proveedor principal falla por error de API (529, timeout, etc.),
        intenta con los proveedores de respaldo en orden de prioridad.
        Retorna el texto de respuesta crudo.
        """
        # Intentar con proveedor principal primero
        tipo = self.ia_proveedor_tipo
        try:
            return self._llamar_ia_con_proveedor(tipo, self.ia_api_key, self.ia_url_base, archivo_b64, es_pdf, mime_type, prompt, modelo)
        except Exception as e_principal:
            error_str = str(e_principal).lower()
            es_error_api = any(x in error_str for x in ['529', 'overloaded', 'timeout', 'rate_limit', '503', '502', 'capacity', 'too many requests'])

            if not es_error_api or len(self.proveedores_disponibles) <= 1:
                raise  # No es error de API o no hay respaldos

            prov_principal = self.proveedores_disponibles[0].get("nombre", "?")
            logger.warning(f"⚠️ Proveedor principal '{prov_principal}' falló: {str(e_principal)[:150]}. Intentando respaldo...")

            # Intentar con proveedores de respaldo
            for i, prov_backup in enumerate(self.proveedores_disponibles[1:], start=2):
                try:
                    logger.info(f"🔄 Failover → proveedor #{i}: {prov_backup['nombre']} ({prov_backup['proveedor_tipo']}/{prov_backup['modelo']})")
                    resultado = self._llamar_ia_con_proveedor(
                        prov_backup["proveedor_tipo"],
                        prov_backup["api_key"],
                        prov_backup.get("url_base", ""),
                        archivo_b64, es_pdf, mime_type, prompt,
                        prov_backup["modelo"]
                    )
                    logger.info(f"✅ Failover exitoso con '{prov_backup['nombre']}'")
                    return resultado
                except Exception as e_backup:
                    logger.warning(f"❌ Respaldo '{prov_backup['nombre']}' también falló: {str(e_backup)[:100]}")
                    continue

            # Todos los proveedores fallaron
            raise Exception(f"Todos los proveedores fallaron. Principal: {str(e_principal)[:100]}")

    def _llamar_ia_con_proveedor(self, tipo, api_key, url_base, archivo_b64, es_pdf, mime_type, prompt, modelo):
        """Llama a un proveedor específico de IA."""
        if tipo == "anthropic":
            return self._llamar_anthropic(archivo_b64, es_pdf, mime_type, prompt, modelo, api_key=api_key)
        elif tipo in ("openai", "openai_compatible", "gemini"):
            return self._llamar_openai_compatible(archivo_b64, es_pdf, mime_type, prompt, modelo, api_key=api_key, url_base=url_base, tipo_override=tipo)
        else:
            raise ValueError(f"Tipo de proveedor no soportado: {tipo}")

    def _llamar_anthropic(self, archivo_b64, es_pdf, mime_type, prompt, modelo, api_key=None, **kwargs):
        """Llamada a la API de Anthropic Claude."""
        try:
            import anthropic
        except ImportError:
            raise ImportError("Librería anthropic no instalada. Ejecuta: pip install anthropic")

        # Construir content block según tipo de archivo
        if es_pdf:
            content_block = {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": archivo_b64}
            }
        else:
            media = mime_type or "image/jpeg"
            content_block = {
                "type": "image",
                "source": {"type": "base64", "media_type": media, "data": archivo_b64}
            }

        key_usar = api_key or self.ia_api_key
        client = anthropic.Anthropic(api_key=key_usar)

        # Reintentos automáticos para API sobrecargada
        MAX_REINTENTOS = 3
        for intento in range(MAX_REINTENTOS):
            try:
                respuesta = client.messages.create(
                    model=modelo,
                    max_tokens=8192,
                    messages=[{
                        "role": "user",
                        "content": [content_block, {"type": "text", "text": prompt}]
                    }],
                    timeout=60.0
                )
                return respuesta.content[0].text.strip()
            except Exception as e:
                if '529' in str(e) or 'overloaded' in str(e).lower():
                    if intento < MAX_REINTENTOS - 1:
                        logger.warning(f"API sobrecargada, reintento {intento+1}/{MAX_REINTENTOS}...")
                        time.sleep(5 * (intento + 1))
                        continue
                raise

    def _llamar_openai_compatible(self, archivo_b64, es_pdf, mime_type, prompt, modelo, api_key=None, url_base=None, tipo_override=None, **kwargs):
        """Llamada a API compatible con OpenAI (OpenAI, Gemini, Ollama, Groq, Together, etc.)."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("Librería openai no instalada. Ejecuta: pip install openai")

        # Configurar cliente con URL base personalizada si existe
        key_usar = api_key or self.ia_api_key or "not-needed"
        url_usar = url_base or self.ia_url_base
        tipo_usar = tipo_override or self.ia_proveedor_tipo
        client_kwargs = {"api_key": key_usar}
        if url_usar:
            client_kwargs["base_url"] = url_usar
        elif tipo_usar == "gemini":
            client_kwargs["base_url"] = "https://generativelanguage.googleapis.com/v1beta/openai/"

        client = OpenAI(**client_kwargs)

        # Construir mensaje con imagen/PDF como data URL
        if es_pdf:
            data_url = f"data:application/pdf;base64,{archivo_b64}"
        else:
            media = mime_type or "image/jpeg"
            data_url = f"data:{media};base64,{archivo_b64}"

        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": prompt}
            ]
        }]

        # Reintentos automáticos
        MAX_REINTENTOS = 3
        for intento in range(MAX_REINTENTOS):
            try:
                respuesta = client.chat.completions.create(
                    model=modelo,
                    max_tokens=8192,
                    messages=messages,
                    timeout=60.0
                )
                finish = respuesta.choices[0].finish_reason
                contenido = respuesta.choices[0].message.content
                logger.info(f"Respuesta {self.ia_proveedor_tipo}: finish_reason={finish}, len={len(contenido) if contenido else 0}")
                if not contenido:
                    logger.warning(f"Respuesta vacía de {self.ia_proveedor_tipo}, finish_reason={finish}")
                    return "{}"
                if finish == "length":
                    logger.warning(f"Respuesta truncada por max_tokens en {self.ia_proveedor_tipo}")
                return contenido.strip()
            except Exception as e:
                if '529' in str(e) or 'overloaded' in str(e).lower() or '503' in str(e):
                    if intento < MAX_REINTENTOS - 1:
                        logger.warning(f"API sobrecargada, reintento {intento+1}/{MAX_REINTENTOS}...")
                        time.sleep(5 * (intento + 1))
                        continue
                raise

    def _parsear_json_respuesta(self, texto):
        """
        Parsea la respuesta de la IA como JSON, limpiando markdown si aparece.
        Si el JSON está truncado, intenta repararlo cerrando estructuras abiertas.

        Args:
            texto (str): Texto de respuesta de la IA

        Returns:
            dict o None si no se pudo parsear
        """
        # Limpiar bloques markdown ```json ... ```
        texto_limpio = texto.strip()
        if texto_limpio.startswith("```"):
            # Remover primera línea (```json) y última (```)
            lineas = texto_limpio.split("\n")
            lineas = [l for l in lineas if not l.strip().startswith("```")]
            texto_limpio = "\n".join(lineas)

        try:
            return json.loads(texto_limpio)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON directo falló: {e}")
            logger.warning(f"Respuesta (primeros 500 chars): {texto_limpio[:500]}")

            # Intentar reparar JSON truncado
            reparado = self._reparar_json_truncado(texto_limpio)
            if reparado is not None:
                n_campos = len([k for k in reparado if not k.startswith("_")])
                logger.info(f"JSON reparado exitosamente: {n_campos} campos recuperados")
                return reparado

            logger.error(f"No se pudo reparar JSON truncado")
            return None

    def _reparar_json_truncado(self, texto):
        """
        Intenta reparar JSON truncado cerrando estructuras abiertas.
        Recupera datos parciales que son mejor que 0 datos.

        Args:
            texto (str): Texto JSON posiblemente truncado

        Returns:
            dict o None si no se pudo reparar
        """
        texto = texto.strip()
        if not texto or not texto.startswith("{"):
            return None

        # Intento 1: Cerrar estructuras abiertas progresivamente
        reparado = texto

        # Contar comillas — si hay número impar, cerrar la última
        comillas_abiertas = reparado.count('"') % 2
        if comillas_abiertas:
            reparado += '"'

        # Limpiar trailing: coma, dos puntos, o key incompleta
        reparado_stripped = reparado.rstrip()
        # Si termina en coma, quitarla
        if reparado_stripped.endswith(','):
            reparado = reparado_stripped[:-1]
        # Si termina en dos puntos (key sin value), agregar null
        elif reparado_stripped.endswith(':'):
            reparado += ' null'
        # Si termina en comilla seguida de nada útil (key sin :value)
        elif reparado_stripped.endswith('"') and not reparado_stripped.endswith('""'):
            # Verificar si es una key sin valor (último : antes de la comilla)
            ultimo_dos_puntos = reparado_stripped.rfind(':')
            ultima_coma = reparado_stripped.rfind(',')
            ultima_llave = reparado_stripped.rfind('{')
            # Si la última coma o llave está después del último :, es una key incompleta
            if max(ultima_coma, ultima_llave) > ultimo_dos_puntos:
                # Truncar desde la última coma o llave
                pos_corte = max(ultima_coma, ultima_llave)
                if reparado_stripped[pos_corte] == ',':
                    reparado = reparado_stripped[:pos_corte]
                # Si es {, dejarlo como está

        # Cerrar corchetes y llaves abiertos
        abiertas_corchetes = reparado.count('[') - reparado.count(']')
        abiertas_llaves = reparado.count('{') - reparado.count('}')

        for _ in range(max(0, abiertas_corchetes)):
            reparado += ']'
        for _ in range(max(0, abiertas_llaves)):
            reparado += '}'

        try:
            resultado = json.loads(reparado)
            if isinstance(resultado, dict):
                return resultado
        except json.JSONDecodeError:
            pass

        # Intento 2: Buscar el último } o ] completo y truncar ahí
        ultimo_cierre = texto.rfind('}')
        if ultimo_cierre > 0:
            fragmento = texto[:ultimo_cierre + 1]
            # Cerrar llaves/corchetes faltantes
            abiertas_c = fragmento.count('[') - fragmento.count(']')
            abiertas_l = fragmento.count('{') - fragmento.count('}')
            for _ in range(max(0, abiertas_c)):
                fragmento += ']'
            for _ in range(max(0, abiertas_l)):
                fragmento += '}'
            try:
                resultado = json.loads(fragmento)
                if isinstance(resultado, dict):
                    logger.info(f"JSON reparado por truncamiento en último cierre")
                    return resultado
            except json.JSONDecodeError:
                pass

        # Intento 3: Recorrer hacia atrás buscando un punto de corte válido
        for i in range(len(texto) - 1, 0, -1):
            if texto[i] in (',', '}', ']'):
                fragmento = texto[:i]
                if texto[i] == ',':
                    fragmento = fragmento  # quitar la coma trailing
                else:
                    fragmento = texto[:i + 1]

                # Cerrar estructuras abiertas
                abiertas_c = fragmento.count('[') - fragmento.count(']')
                abiertas_l = fragmento.count('{') - fragmento.count('}')
                abiertas_q = fragmento.count('"') % 2

                if abiertas_q:
                    fragmento += '"'

                for _ in range(max(0, abiertas_c)):
                    fragmento += ']'
                for _ in range(max(0, abiertas_l)):
                    fragmento += '}'

                try:
                    resultado = json.loads(fragmento)
                    if isinstance(resultado, dict):
                        logger.info(f"JSON reparado por búsqueda reversa (pos {i})")
                        return resultado
                except json.JSONDecodeError:
                    continue

        return None
