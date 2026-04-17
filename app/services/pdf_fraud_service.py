"""
PDF_FRAUD_SERVICE.PY - Detector de fraude en metadatos de PDF
=============================================================

Analiza metadatos de PDFs (Creator, Producer, CreationDate, ModDate)
y marcadores %%EOF para detectar posible manipulacion o falsificacion.

Dependencias:
- pikepdf: ya instalado en el proyecto para desbloqueo de PDFs
"""

import io
import re
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────
# LISTAS DE PRODUCTORES / CREADORES
# ─────────────────────────────────────────────────

# Productores legitimos de bancos, empresas, ERPs
LISTA_BLANCA = [
    "itext", "jasperreports", "apache fop", "oracle", "sap crystal",
    "reportserver", "qt", "wkhtmltopdf", "tcpdf", "fpdf", "mpdf",
    "microsoft sql server reporting services", "finacle",
    "infosys", "temenos", "cobiscorp", "siigo", "helisa", "nominapp",
    "world office", "alegra", "bancolombia", "nequi", "nu colombia",
    "crystal reports", "stimulsoft", "devexpress", "telerik",
    "ssrs", "birt", "pentaho", "jasper", "reportlab",
    "pdfsharp", "itextsharp", "syncfusion", "aspose",
    "davivienda", "bbva", "scotiabank", "banco de bogota",
    "banco popular", "banco de occidente", "colpatria",
    "awt", "java", "jdk", "openreport",
]

# Editores de imagen/documento — riesgo alto
LISTA_NEGRA = [
    "adobe photoshop", "photoshop", "adobe illustrator", "illustrator",
    "canva", "gimp", "inkscape", "coreldraw", "corel draw",
    "paint", "paint.net", "pixlr",
    "smallpdf", "ilovepdf", "pdfelement", "nitro pro", "nitro pdf",
    "foxit editor", "foxit phantompdf", "foxit phantom",
    "pdf-xchange editor", "pdf xchange", "sejda",
    "wondershare", "pdfescape",
]

# Editores de texto — sospechoso pero no definitivo
LISTA_GRIS = [
    "microsoft word", "word", "ms word",
    "libreoffice", "libre office", "openoffice", "open office",
    "google docs", "google slides",
    "wps office", "wps writer",
    "microsoft powerpoint", "powerpoint",
    "preview", "apple preview",
    "microsoft excel", "excel",
    "pages", "keynote", "numbers",
]


def analizar_metadatos_pdf(archivo_bytes):
    """
    Analiza metadatos de un PDF para detectar posible manipulacion.

    Args:
        archivo_bytes (bytes): Contenido del PDF en bytes

    Returns:
        dict: Resultado del analisis con claves:
            - creator (str|None)
            - producer (str|None)
            - creation_date (str|None)
            - mod_date (str|None)
            - eof_count (int)
            - riesgo ("bajo"|"medio"|"alto")
            - alertas (list[str])
            - detalle (str)
    """
    resultado = {
        "creator": None,
        "producer": None,
        "creation_date": None,
        "mod_date": None,
        "eof_count": 0,
        "riesgo": "bajo",
        "alertas": [],
        "detalle": ""
    }

    # Contar marcadores %%EOF en los bytes crudos
    try:
        resultado["eof_count"] = archivo_bytes.count(b"%%EOF")
    except Exception:
        resultado["eof_count"] = 0

    # Extraer metadatos con pikepdf
    try:
        import pikepdf
        pdf = pikepdf.open(io.BytesIO(archivo_bytes))
        docinfo = pdf.docinfo if hasattr(pdf, 'docinfo') else {}

        resultado["creator"] = _extraer_texto_meta(docinfo, "/Creator")
        resultado["producer"] = _extraer_texto_meta(docinfo, "/Producer")
        resultado["creation_date"] = _extraer_texto_meta(docinfo, "/CreationDate")
        resultado["mod_date"] = _extraer_texto_meta(docinfo, "/ModDate")

        pdf.close()
    except ImportError:
        resultado["alertas"].append("pikepdf no disponible para leer metadatos")
        resultado["riesgo"] = "medio"
        resultado["detalle"] = "No se pudieron leer metadatos (pikepdf no instalado)"
        return resultado
    except Exception as e:
        resultado["alertas"].append(f"No se pudieron leer metadatos: {str(e)[:100]}")
        resultado["riesgo"] = "medio"
        resultado["detalle"] = "No se pudieron leer metadatos del PDF"
        return resultado

    # ─────────────────────────────────────────────────
    # EVALUACION DE RIESGO
    # ─────────────────────────────────────────────────
    nivel_riesgo = 0  # 0=bajo, 1=medio, 2=alto

    creator_lower = (resultado["creator"] or "").lower().strip()
    producer_lower = (resultado["producer"] or "").lower().strip()

    # Verificar LISTA NEGRA (editores de imagen)
    for patron in LISTA_NEGRA:
        if patron in creator_lower or patron in producer_lower:
            nivel_riesgo = max(nivel_riesgo, 2)
            herramienta = resultado["creator"] or resultado["producer"]
            resultado["alertas"].append(
                f"Creado/producido con editor de imagen: {herramienta}"
            )
            break

    # Verificar LISTA GRIS (editores de texto)
    if nivel_riesgo < 2:
        for patron in LISTA_GRIS:
            if patron in creator_lower or patron in producer_lower:
                nivel_riesgo = max(nivel_riesgo, 1)
                herramienta = resultado["creator"] or resultado["producer"]
                resultado["alertas"].append(
                    f"Creado/producido con editor de texto: {herramienta}"
                )
                break

    # Verificar LISTA BLANCA
    en_lista_blanca = False
    for patron in LISTA_BLANCA:
        if patron in creator_lower or patron in producer_lower:
            en_lista_blanca = True
            break

    # Sin metadatos (posible escaneo)
    if not resultado["creator"] and not resultado["producer"]:
        nivel_riesgo = max(nivel_riesgo, 1)
        resultado["alertas"].append(
            "Sin metadatos de Creator/Producer (posible documento escaneado)"
        )

    # Verificar %%EOF multiples (modificaciones incrementales)
    eof_count = resultado["eof_count"]
    if eof_count > 2:
        nivel_riesgo = min(nivel_riesgo + 1, 2)
        resultado["alertas"].append(
            f"PDF con {eof_count} marcadores %%EOF (indica {eof_count - 1} modificaciones incrementales)"
        )
    elif eof_count == 2:
        resultado["alertas"].append(
            "PDF con 2 marcadores %%EOF (1 modificacion incremental — puede ser normal en firmas digitales)"
        )

    # Verificar diferencia entre CreationDate y ModDate
    if resultado["creation_date"] and resultado["mod_date"]:
        try:
            fecha_creacion = _parsear_fecha_pdf(resultado["creation_date"])
            fecha_mod = _parsear_fecha_pdf(resultado["mod_date"])
            if fecha_creacion and fecha_mod:
                diferencia = abs((fecha_mod - fecha_creacion).total_seconds())
                if diferencia > 86400:  # mas de 24 horas
                    dias = int(diferencia / 86400)
                    nivel_riesgo = max(nivel_riesgo, 1)
                    resultado["alertas"].append(
                        f"Modificado {dias} dia(s) despues de su creacion"
                    )
        except Exception:
            pass

    # Si esta en lista blanca y no hay otras alertas graves, mantener bajo
    if en_lista_blanca and nivel_riesgo == 0:
        nivel_riesgo = 0

    # Mapear nivel numerico a texto
    riesgo_map = {0: "bajo", 1: "medio", 2: "alto"}
    resultado["riesgo"] = riesgo_map.get(min(nivel_riesgo, 2), "medio")

    # Construir detalle legible
    if resultado["alertas"]:
        resultado["detalle"] = "; ".join(resultado["alertas"])
    elif en_lista_blanca:
        productor = resultado["producer"] or resultado["creator"] or "desconocido"
        resultado["detalle"] = f"Documento generado por sistema legitimo ({productor})"
    else:
        resultado["detalle"] = "Sin alertas detectadas en metadatos"

    return resultado


# ─────────────────────────────────────────────────
# FUNCIONES AUXILIARES
# ─────────────────────────────────────────────────

def _extraer_texto_meta(docinfo, clave):
    """Extrae texto de un campo de metadatos de pikepdf (puede ser pikepdf.String o str)."""
    try:
        valor = docinfo.get(clave)
        if valor is None:
            return None
        texto = str(valor)
        # Limpiar prefijo pikepdf si existe
        if texto.startswith("/"):
            texto = texto[1:]
        return texto.strip() if texto.strip() else None
    except Exception:
        return None


def _parsear_fecha_pdf(fecha_str):
    """
    Parsea fecha PDF en formato D:YYYYMMDDHHmmSS o similar.
    Retorna datetime o None.
    """
    if not fecha_str:
        return None
    try:
        # Limpiar prefijo D: si existe
        limpio = fecha_str.replace("D:", "").strip()
        # Remover timezone info (+00'00', -05'00', Z, etc.)
        limpio = re.sub(r"[+-]\d{2}'\d{2}'?$", "", limpio)
        limpio = re.sub(r"[+-]\d{2}:\d{2}$", "", limpio)
        limpio = limpio.rstrip("Z")

        # Intentar parsear con diferentes longitudes
        if len(limpio) >= 14:
            return datetime.strptime(limpio[:14], "%Y%m%d%H%M%S")
        elif len(limpio) >= 8:
            return datetime.strptime(limpio[:8], "%Y%m%d")
        return None
    except (ValueError, TypeError):
        return None
