"""
VALIDACION_NOMINA_SERVICE.PY - Verificacion matematica de comprobantes de nomina
=================================================================================

Valida coherencia aritmetica de los datos extraidos de un comprobante de nomina
colombiano. No usa IA — es pura matematica.

Los empleados pueden tener multiples deducciones ademas de salud y pension:
libranzas, fondo de empleados, cooperativas, embargos, sindicato, seguros, etc.
El neto = devengados - TODAS las deducciones.
"""

import logging

logger = logging.getLogger(__name__)


def _obtener_parametros_laborales():
    """Obtiene parametros laborales desde BD (parametros_sistema), con fallback a config.py."""
    try:
        from db_helpers import obtener_parametros_laborales
        params = obtener_parametros_laborales()
        if params and params.get("smlv"):
            return params
    except Exception as e:
        logger.warning(f"No se pudieron cargar parametros laborales desde BD: {e}")

    # Fallback a config.py
    try:
        from app.config import Config
        return Config.PARAMETROS_LABORALES
    except Exception as e2:
        logger.warning(f"No se pudieron cargar parametros laborales desde config: {e2}")
        # Fallback con valores por defecto 2026 (Decreto 1469/1470 del 29-dic-2025)
        return {
            "anio": 2026,
            "smlv": 1_750_905,
            "subsidio_transporte": 249_095,
            "pct_salud_empleado": 0.04,
            "pct_pension_empleado": 0.04,
            "pct_fsp_4_smlv": 0.01,
            "pct_retencion_umbral": 5_470_000,
        }


def _buscar_valor(datos, *claves):
    """Busca un valor numerico en datos usando multiples nombres posibles."""
    for clave in claves:
        valor = datos.get(clave)
        if valor is not None and isinstance(valor, (int, float)):
            return valor
        # Intentar convertir strings numericos
        if valor is not None and isinstance(valor, str):
            try:
                limpio = valor.replace(".", "").replace(",", ".").replace("$", "").replace(" ", "").strip()
                return float(limpio)
            except (ValueError, TypeError):
                continue
    return None


def validar_coherencia_nomina(datos_extraidos, params=None):
    """
    Valida coherencia matematica de un comprobante de nomina colombiano.

    IMPORTANTE: Los empleados tienen multiples deducciones ademas de
    salud y pension (libranzas, fondo empleados, cooperativas, embargos,
    sindicato, seguros). El neto = devengados - TODAS las deducciones.

    Args:
        datos_extraidos (dict): Datos extraidos por la IA del comprobante
        params (dict|None): Parametros laborales. Si None, usa Config.

    Returns:
        dict: Resultado con validaciones_pasadas, validaciones_fallidas,
              validaciones_total, alertas, coherencia, detalle,
              parametros_usados
    """
    if params is None:
        params = _obtener_parametros_laborales()

    alertas = []
    validaciones_ok = 0
    validaciones_total = 0

    smlv = params["smlv"]

    # Buscar salario basico con multiples nombres posibles
    basico = _buscar_valor(
        datos_extraidos,
        "_salario_basico", "salario_basico", "basico", "sueldo_basico",
        "salario_base", "sueldo_base", "asignacion_basica"
    )

    # Si no hay salario basico, no podemos validar
    if not basico:
        return {
            "validaciones_pasadas": 0,
            "validaciones_fallidas": 0,
            "validaciones_total": 0,
            "alertas": ["No se encontro salario basico en el comprobante"],
            "coherencia": "media",
            "detalle": "Sin datos suficientes para validacion matematica",
            "parametros_usados": {"smlv": smlv, "anio": params["anio"]}
        }

    # ─────────────────────────────────────────────────
    # VALIDACION 1: Salud = 4% del IBC
    # ─────────────────────────────────────────────────
    salud = _buscar_valor(
        datos_extraidos,
        "_deduccion_salud", "deduccion_salud", "salud_empleado", "salud",
        "aporte_salud", "eps"
    )
    if salud is not None:
        validaciones_total += 1
        esperado = basico * params["pct_salud_empleado"]
        if abs(salud - esperado) <= 1000:
            validaciones_ok += 1
        else:
            alertas.append(
                f"Salud: ${salud:,.0f} vs esperado ${esperado:,.0f} "
                f"(4% de ${basico:,.0f})"
            )

    # ─────────────────────────────────────────────────
    # VALIDACION 2: Pension = 4% del IBC
    # ─────────────────────────────────────────────────
    pension = _buscar_valor(
        datos_extraidos,
        "_deduccion_pension", "deduccion_pension", "pension_empleado", "pension",
        "aporte_pension", "fondo_pension"
    )
    if pension is not None:
        validaciones_total += 1
        esperado = basico * params["pct_pension_empleado"]
        if abs(pension - esperado) <= 1000:
            validaciones_ok += 1
        else:
            alertas.append(
                f"Pension: ${pension:,.0f} vs esperado ${esperado:,.0f} "
                f"(4% de ${basico:,.0f})"
            )

    # ─────────────────────────────────────────────────
    # VALIDACION 3: Neto = Devengados - TOTAL deducciones
    # ─────────────────────────────────────────────────
    neto = _buscar_valor(
        datos_extraidos,
        "_neto_pagar", "neto_pagar", "neto", "total_neto",
        "neto_a_pagar", "total_a_pagar"
    )
    total_devengados = _buscar_valor(
        datos_extraidos,
        "_total_devengados", "total_devengados", "devengados",
        "total_devengado", "devengado"
    )
    total_deducciones = _buscar_valor(
        datos_extraidos,
        "_total_deducciones", "total_deducciones", "deducciones",
        "total_deduccion", "total_descuentos", "descuentos"
    )

    if neto is not None and total_devengados is not None and total_deducciones is not None:
        validaciones_total += 1
        esperado = total_devengados - total_deducciones
        if abs(neto - esperado) <= 2000:
            validaciones_ok += 1
        else:
            alertas.append(
                f"Neto: ${neto:,.0f} vs esperado ${esperado:,.0f} "
                f"(devengados ${total_devengados:,.0f} - "
                f"deducciones ${total_deducciones:,.0f})"
            )

    # ─────────────────────────────────────────────────
    # VALIDACION 4: Subsidio de transporte
    # ─────────────────────────────────────────────────
    subsidio = _buscar_valor(
        datos_extraidos,
        "_subsidio_transporte", "subsidio_transporte", "auxilio_transporte",
        "aux_transporte", "subsidio_transp"
    )
    if basico <= 2 * smlv:
        # Deberia tener subsidio
        if subsidio is not None:
            validaciones_total += 1
            esperado = params["subsidio_transporte"]
            if abs(subsidio - esperado) <= 15000:
                validaciones_ok += 1
            else:
                alertas.append(
                    f"Subsidio transporte: ${subsidio:,.0f} vs "
                    f"esperado ${esperado:,.0f}"
                )
    elif basico > 2 * smlv and subsidio is not None and subsidio > 0:
        # No deberia tener subsidio
        validaciones_total += 1
        alertas.append(
            f"Tiene subsidio de transporte (${subsidio:,.0f}) "
            f"pero su salario (${basico:,.0f}) supera 2 SMLV"
        )

    # ─────────────────────────────────────────────────
    # VALIDACION 5: FSP si >4 SMLV
    # ─────────────────────────────────────────────────
    if basico > 4 * smlv:
        fsp = _buscar_valor(
            datos_extraidos,
            "_fondo_solidaridad", "fondo_solidaridad", "fsp",
            "fondo_solidaridad_pensional", "solidaridad"
        )
        validaciones_total += 1
        if fsp is not None and fsp > 0:
            validaciones_ok += 1
        elif fsp is None:
            alertas.append(
                f"Salario (${basico:,.0f}) supera 4 SMLV pero "
                f"no se detecto deduccion de Fondo de Solidaridad"
            )

    # ─────────────────────────────────────────────────
    # DETERMINAR COHERENCIA
    # ─────────────────────────────────────────────────
    if validaciones_total == 0:
        coherencia = "media"
        detalle = "Sin datos suficientes para validacion completa"
    elif len(alertas) == 0:
        coherencia = "alta"
        detalle = f"Todas las {validaciones_ok} validaciones pasaron"
    elif len(alertas) <= 1:
        coherencia = "media"
        detalle = f"{validaciones_ok}/{validaciones_total} validaciones OK"
    else:
        coherencia = "baja"
        detalle = f"Multiples inconsistencias ({len(alertas)} alertas)"

    resultado = {
        "validaciones_pasadas": validaciones_ok,
        "validaciones_fallidas": len(alertas),
        "validaciones_total": validaciones_total,
        "alertas": alertas,
        "coherencia": coherencia,
        "detalle": detalle,
        "parametros_usados": {
            "smlv": smlv,
            "anio": params["anio"]
        }
    }

    # Exponer datos de nomina para que extractor_service use salario_basico
    resultado["datos_nomina"] = {
        "salario_basico": basico,
        "neto_pagar": neto,
        "total_devengados": total_devengados,
        "total_deducciones": total_deducciones,
        "deduccion_salud": salud,
        "deduccion_pension": pension,
        "subsidio_transporte": subsidio,
        "alertas_ia": datos_extraidos.get('_alertas', []) or []
    }

    logger.info(
        f"Validacion nomina: {validaciones_ok}/{validaciones_total} OK, "
        f"coherencia={coherencia}, alertas={len(alertas)}"
    )

    return resultado


# ============================================================================
# WRAPPER: validar_nomina (alias para compatibilidad con prompt v4.9)
# ============================================================================

def validar_nomina(datos_extraidos: dict, anio: int = 2026) -> dict:
    """
    Wrapper sobre validar_coherencia_nomina que normaliza el resultado al
    formato esperado por el prompt v4.9 (total fijo=4, params_usados con transp).

    Mantiene compatibilidad con extractor_service.py que llama a
    validar_coherencia_nomina directamente.
    """
    params = _obtener_parametros_laborales()
    resultado = validar_coherencia_nomina(datos_extraidos, params=params)

    # Normalizar total a 4 (prompt v4.9 espera 4 validaciones fijas)
    pasadas = resultado.get("validaciones_pasadas", 0)
    total_original = resultado.get("validaciones_total", 0)

    # Si el total real es menor a 4, mantener las pasadas pero ajustar total
    # para que la UI muestre "x/4" de forma consistente
    total_normalizado = 4
    pasadas_normalizadas = min(pasadas, total_normalizado)
    fallidas_normalizadas = total_normalizado - pasadas_normalizadas

    # Enriquecer params_usados con subsidio_transporte para el prompt
    params_usados = resultado.get("parametros_usados", {})
    params_usados.setdefault("subsidio_transporte", params.get("subsidio_transporte"))

    resultado["validaciones_pasadas"] = pasadas_normalizadas
    resultado["validaciones_fallidas"] = fallidas_normalizadas
    resultado["validaciones_total"] = total_normalizado
    resultado["validaciones_total_real"] = total_original  # Para debug
    resultado["parametros_usados"] = params_usados
    resultado["datos_nomina"] = resultado.get("datos_nomina", {})

    return resultado
