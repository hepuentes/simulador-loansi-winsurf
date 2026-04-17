"""
VALIDACION_CRUZADA_SERVICE.PY - Validacion cruzada entre documentos
====================================================================

Compara datos extraidos de multiples fuentes para detectar inconsistencias
reales en ingresos, empleo, identidad y otros datos financieros.

NO usa IA — es pura logica de comparacion con tolerancias configurables.
"""

import logging

logger = logging.getLogger(__name__)

# Tolerancia porcentual para comparaciones de montos
TOLERANCIA_MONTO_PCT = 0.15  # 15% de diferencia es aceptable
TOLERANCIA_MONTO_ABS = 50_000  # Diferencia absoluta minima aceptable (50K COP)


def validar_cruzado(resultados_por_fuente):
    """
    Compara datos entre multiples fuentes para detectar inconsistencias.

    Args:
        resultados_por_fuente (dict): {fuente: {campo: valor, ...}, ...}

    Returns:
        dict: {
            "inconsistencias": [{"campo": str, "fuentes": dict, "severidad": str, "detalle": str}],
            "coincidencias": [{"campo": str, "valor": any, "fuentes": list}],
            "resumen": str,
            "nivel_riesgo": "bajo"|"medio"|"alto"
        }
    """
    inconsistencias = []
    coincidencias = []

    # Recopilar valores por campo de todas las fuentes (sin metadatos _)
    campos_por_fuente = {}
    for fuente, datos in resultados_por_fuente.items():
        if "_error" in datos:
            continue
        for campo, valor in datos.items():
            if campo.startswith("_") or valor is None:
                continue
            if campo not in campos_por_fuente:
                campos_por_fuente[campo] = {}
            campos_por_fuente[campo][fuente] = valor

    # ─────────────────────────────────────────────────
    # VALIDACION 1: Ingresos entre fuentes
    # ─────────────────────────────────────────────────
    _validar_ingresos(resultados_por_fuente, inconsistencias, coincidencias)

    # ─────────────────────────────────────────────────
    # VALIDACION 2: Empresa empleadora entre fuentes
    # ─────────────────────────────────────────────────
    _validar_empresa(resultados_por_fuente, inconsistencias, coincidencias)

    # ─────────────────────────────────────────────────
    # VALIDACION 3: IBC entre planilla PILA y nomina
    # ─────────────────────────────────────────────────
    _validar_ibc(resultados_por_fuente, inconsistencias, coincidencias)

    # ─────────────────────────────────────────────────
    # VALIDACION 4: Campos duplicados entre fuentes
    # ─────────────────────────────────────────────────
    for campo, fuentes_dict in campos_por_fuente.items():
        if len(fuentes_dict) < 2:
            continue
        # Comparar valores entre fuentes
        valores = list(fuentes_dict.values())
        fuentes_list = list(fuentes_dict.keys())

        todos_numericos = all(_es_numerico(v) for v in valores)
        if todos_numericos:
            nums = [_a_numero(v) for v in valores]
            if nums and max(nums) > 0:
                diferencia_pct = (max(nums) - min(nums)) / max(nums)
                diferencia_abs = max(nums) - min(nums)
                if diferencia_pct > TOLERANCIA_MONTO_PCT and diferencia_abs > TOLERANCIA_MONTO_ABS:
                    inconsistencias.append({
                        "campo": campo,
                        "fuentes": fuentes_dict,
                        "severidad": "media",
                        "detalle": (
                            f"'{campo}' difiere {diferencia_pct*100:.0f}% entre fuentes: "
                            + ", ".join(f"{f}={v}" for f, v in fuentes_dict.items())
                        )
                    })
                else:
                    coincidencias.append({
                        "campo": campo,
                        "valor": valores[0],
                        "fuentes": fuentes_list
                    })
        else:
            # Comparar como texto
            textos = [str(v).strip().lower() for v in valores]
            if len(set(textos)) > 1:
                # No reportar como inconsistencia campos de texto distintos
                # a menos que sean campos clave
                campos_clave = ["nombre", "cedula", "nit", "empresa"]
                es_clave = any(c in campo.lower() for c in campos_clave)
                if es_clave:
                    inconsistencias.append({
                        "campo": campo,
                        "fuentes": fuentes_dict,
                        "severidad": "alta" if "cedula" in campo.lower() else "media",
                        "detalle": (
                            f"'{campo}' no coincide entre fuentes: "
                            + ", ".join(f"{f}='{v}'" for f, v in fuentes_dict.items())
                        )
                    })
            else:
                coincidencias.append({
                    "campo": campo,
                    "valor": valores[0],
                    "fuentes": fuentes_list
                })

    # ─────────────────────────────────────────────────
    # DETERMINAR NIVEL DE RIESGO
    # ─────────────────────────────────────────────────
    altas = sum(1 for i in inconsistencias if i["severidad"] == "alta")
    medias = sum(1 for i in inconsistencias if i["severidad"] == "media")

    if altas >= 2:
        nivel_riesgo = "alto"
    elif altas >= 1 or medias >= 3:
        nivel_riesgo = "medio"
    else:
        nivel_riesgo = "bajo"

    if not inconsistencias:
        resumen = f"Sin inconsistencias detectadas. {len(coincidencias)} dato(s) coinciden entre fuentes."
    else:
        resumen = (
            f"{len(inconsistencias)} inconsistencia(s) detectada(s) "
            f"({altas} alta, {medias} media). "
            f"{len(coincidencias)} dato(s) coinciden."
        )

    resultado = {
        "inconsistencias": inconsistencias,
        "coincidencias": coincidencias,
        "resumen": resumen,
        "nivel_riesgo": nivel_riesgo
    }

    logger.info(
        f"Validacion cruzada: {len(inconsistencias)} inconsistencias, "
        f"{len(coincidencias)} coincidencias, riesgo={nivel_riesgo}"
    )

    return resultado


# ─────────────────────────────────────────────────
# VALIDACIONES ESPECIFICAS
# ─────────────────────────────────────────────────

def _validar_ingresos(resultados, inconsistencias, coincidencias):
    """Compara ingresos entre nomina, extracto bancario y declaracion de renta."""
    campos_ingreso = [
        "salario_basico", "basico", "sueldo_basico", "salario_base",
        "neto_pagar", "neto", "total_neto",
        "ingreso_mensual", "ingresos_mensuales",
        "total_devengados", "devengados"
    ]

    ingresos_por_fuente = {}
    for fuente, datos in resultados.items():
        if "_error" in datos:
            continue
        for campo in campos_ingreso:
            valor = datos.get(campo)
            if valor is not None and _es_numerico(valor):
                num = _a_numero(valor)
                if num > 0:
                    ingresos_por_fuente[fuente] = {
                        "campo": campo,
                        "valor": num
                    }
                    break

    if len(ingresos_por_fuente) >= 2:
        valores = [v["valor"] for v in ingresos_por_fuente.values()]
        max_val = max(valores)
        min_val = min(valores)
        if max_val > 0:
            diferencia_pct = (max_val - min_val) / max_val
            if diferencia_pct > 0.30:  # Mas de 30% de diferencia en ingresos es sospechoso
                detalle_fuentes = {
                    f: f"${v['valor']:,.0f} ({v['campo']})"
                    for f, v in ingresos_por_fuente.items()
                }
                inconsistencias.append({
                    "campo": "ingreso_cruzado",
                    "fuentes": detalle_fuentes,
                    "severidad": "alta",
                    "detalle": (
                        f"Ingreso difiere {diferencia_pct*100:.0f}% entre fuentes: "
                        + ", ".join(f"{f}={d}" for f, d in detalle_fuentes.items())
                    )
                })
            else:
                coincidencias.append({
                    "campo": "ingreso_cruzado",
                    "valor": f"${min_val:,.0f} - ${max_val:,.0f}",
                    "fuentes": list(ingresos_por_fuente.keys())
                })


def _validar_empresa(resultados, inconsistencias, coincidencias):
    """Compara nombre de empresa entre nomina y certificado seguridad social."""
    campos_empresa = ["empresa_empleadora", "empleador", "razon_social", "empresa", "aportante_pila"]

    empresas_por_fuente = {}
    for fuente, datos in resultados.items():
        if "_error" in datos:
            continue
        for campo in campos_empresa:
            valor = datos.get(campo)
            if valor and isinstance(valor, str) and len(valor.strip()) > 2:
                empresas_por_fuente[fuente] = valor.strip()
                break

    if len(empresas_por_fuente) >= 2:
        nombres = [v.lower() for v in empresas_por_fuente.values()]
        # Comparacion flexible: si alguna contiene a la otra
        todos_similares = True
        nombres_list = list(nombres)
        for i in range(len(nombres_list)):
            for j in range(i+1, len(nombres_list)):
                if (nombres_list[i] not in nombres_list[j] and
                    nombres_list[j] not in nombres_list[i]):
                    todos_similares = False
                    break

        if not todos_similares:
            inconsistencias.append({
                "campo": "empresa_cruzada",
                "fuentes": empresas_por_fuente,
                "severidad": "alta",
                "detalle": (
                    "Empresa empleadora no coincide entre fuentes: "
                    + ", ".join(f"{f}='{v}'" for f, v in empresas_por_fuente.items())
                )
            })
        else:
            coincidencias.append({
                "campo": "empresa_cruzada",
                "valor": list(empresas_por_fuente.values())[0],
                "fuentes": list(empresas_por_fuente.keys())
            })


def _validar_ibc(resultados, inconsistencias, coincidencias):
    """Compara IBC entre planilla PILA y nomina."""
    campos_ibc = ["ibc_pila", "ibc_seguridad_social"]
    campos_salario = ["salario_basico", "basico", "sueldo_basico", "salario_base"]

    ibc = None
    ibc_fuente = None
    salario = None
    salario_fuente = None

    for fuente, datos in resultados.items():
        if "_error" in datos:
            continue
        for campo in campos_ibc:
            valor = datos.get(campo)
            if valor is not None and _es_numerico(valor):
                ibc = _a_numero(valor)
                ibc_fuente = fuente
                break
        for campo in campos_salario:
            valor = datos.get(campo)
            if valor is not None and _es_numerico(valor):
                salario = _a_numero(valor)
                salario_fuente = fuente
                break

    if ibc and salario and ibc > 0 and salario > 0:
        diferencia_pct = abs(ibc - salario) / max(ibc, salario)
        if diferencia_pct > 0.10:  # Mas de 10% de diferencia
            inconsistencias.append({
                "campo": "ibc_vs_salario",
                "fuentes": {
                    ibc_fuente: f"IBC=${ibc:,.0f}",
                    salario_fuente: f"Salario=${salario:,.0f}"
                },
                "severidad": "alta" if diferencia_pct > 0.30 else "media",
                "detalle": (
                    f"IBC (${ibc:,.0f}) difiere {diferencia_pct*100:.0f}% "
                    f"del salario basico (${salario:,.0f})"
                )
            })
        else:
            coincidencias.append({
                "campo": "ibc_vs_salario",
                "valor": f"IBC=${ibc:,.0f} ~ Salario=${salario:,.0f}",
                "fuentes": [ibc_fuente, salario_fuente]
            })


# ─────────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────────

def _es_numerico(valor):
    """Verifica si un valor es numerico o convertible a numero."""
    if isinstance(valor, (int, float)):
        return True
    if isinstance(valor, str):
        try:
            limpio = valor.replace(".", "").replace(",", ".").replace("$", "").replace(" ", "").strip()
            float(limpio)
            return True
        except (ValueError, TypeError):
            return False
    return False


def _a_numero(valor):
    """Convierte un valor a numero float."""
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        limpio = valor.replace(".", "").replace(",", ".").replace("$", "").replace(" ", "").strip()
        return float(limpio)
    return 0.0
