"""
FINANCE.PY - Funciones de cálculo financiero
============================================
"""

import math
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from .formatting import formatear_con_miles

SEMANAS_POR_MES = 52.0 / 12.0

def calcular_edad_desde_fecha(fecha_nacimiento_str, fecha_referencia=None):
    """
    Calcula edad exacta desde fecha de nacimiento.

    Args:
        fecha_nacimiento_str: String en formato 'YYYY-MM-DD'
        fecha_referencia: datetime o None (usa fecha actual)

    Returns:
        int: Edad en años completos
    """
    try:
        if isinstance(fecha_nacimiento_str, str):
            fecha_nac = datetime.strptime(fecha_nacimiento_str, "%Y-%m-%d")
        else:
            fecha_nac = fecha_nacimiento_str

        if fecha_referencia is None:
            fecha_ref = datetime.now()
        elif isinstance(fecha_referencia, str):
            fecha_ref = datetime.strptime(fecha_referencia, "%Y-%m-%d")
        else:
            fecha_ref = fecha_referencia

        edad = fecha_ref.year - fecha_nac.year

        # Ajustar si aún no ha cumplido años este año
        if (fecha_ref.month, fecha_ref.day) < (fecha_nac.month, fecha_nac.day):
            edad -= 1

        return edad
    except Exception as e:
        print(f"❌ Error calculando edad: {e}")
        return 0


def meses_entre_fechas(fecha_inicio, fecha_fin):
    """
    Calcula meses completos entre dos fechas (puede incluir decimales)

    Returns:
        float: Meses exactos entre fechas
    """
    if isinstance(fecha_inicio, str):
        fecha_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
    if isinstance(fecha_fin, str):
        fecha_fin = datetime.strptime(fecha_fin, "%Y-%m-%d")

    años = fecha_fin.year - fecha_inicio.year
    meses = fecha_fin.month - fecha_inicio.month
    dias = fecha_fin.day - fecha_inicio.day

    total_meses = años * 12 + meses + (dias / 30.0)  # Aproximación
    return max(0, total_meses)


def calcular_cuota(monto_total, tasa_mensual, plazo_meses):
    """
    Calcula la cuota mensual de un préstamo usando amortización francesa.
    Sistema de cuota fija mensual (SIN decimales).

    Args:
        monto_total: Monto total a financiar (float)
        tasa_mensual: Tasa mensual en DECIMAL (float, ej: 0.017992)
        plazo_meses: Plazo en meses (int o float)

    Returns:
        int: Cuota mensual ENTERA (sin decimales), redondeada
    """
    if tasa_mensual == 0:
        return int(round(monto_total / plazo_meses))

    # Fórmula de amortización francesa
    cuota = (monto_total * tasa_mensual) / (1 - (1 + tasa_mensual) ** -plazo_meses)

    return int(round(cuota))


def calcular_seguro_anual(edad_cliente, monto_solicitado, plazo_meses, seguros_config):
    """
    Calcula seguro anual basado en rangos de edad.
    """
    millones = monto_solicitado / 1_000_000
    rangos = seguros_config.get("SEGURO_VIDA", [])

    def obtener_tarifa_por_edad(edad):
        if not isinstance(rangos, list):
            # Compatibilidad con estructura antigua
            if edad <= 45: return 900
            elif edad <= 59: return 1100
            else: return 1250
        else:
            for rango in rangos:
                if rango["edad_min"] <= edad <= rango["edad_max"]:
                    return rango["costo"]
            return 900  # Default

    años_credito = math.ceil(plazo_meses / 12)
    edad_final = edad_cliente + años_credito
    
    tarifa_inicial = obtener_tarifa_por_edad(edad_cliente)
    tarifa_final = obtener_tarifa_por_edad(edad_final)
    tarifa_mensual = max(tarifa_inicial, tarifa_final)

    años_exactos = plazo_meses / 12
    seguro_calculado = tarifa_mensual * millones * 12 * años_exactos
    return int(round(seguro_calculado))


def calcular_seguro_proporcional_fecha(fecha_nacimiento_str, monto_solicitado, plazo_meses, seguros_config, fecha_inicio_credito=None):
    """
    Calcula seguro con distribución proporcional según fecha de nacimiento exacta.
    """
    try:
        # Parsear fecha de nacimiento
        if isinstance(fecha_nacimiento_str, str):
            fecha_nac = datetime.strptime(fecha_nacimiento_str, "%Y-%m-%d")
        else:
            fecha_nac = fecha_nacimiento_str

        # Fecha de inicio del crédito
        if fecha_inicio_credito is None:
            fecha_inicio = datetime.now()
        elif isinstance(fecha_inicio_credito, str):
            fecha_inicio = datetime.strptime(fecha_inicio_credito, "%Y-%m-%d")
        else:
            fecha_inicio = fecha_inicio_credito

        meses_enteros = int(plazo_meses)
        dias_fraccion = int((plazo_meses - meses_enteros) * 30.44)

        fecha_fin = fecha_inicio + relativedelta(months=meses_enteros) + timedelta(days=dias_fraccion)
        edad_inicial = calcular_edad_desde_fecha(fecha_nac, fecha_inicio)

        def obtener_tarifa_por_edad(edad):
            rangos = seguros_config.get("SEGURO_VIDA", [])
            if not isinstance(rangos, list):
                if edad <= 45: return 900
                elif edad <= 59: return 1100
                else: return 1250

            for rango in rangos:
                if rango["edad_min"] <= edad <= rango["edad_max"]:
                    return rango["costo"]
            return 900

        cumpleaños_durante = []
        for i in range(1, 15):
            fecha_cumple = datetime(year=fecha_inicio.year + i, month=fecha_nac.month, day=fecha_nac.day)
            if fecha_cumple <= fecha_inicio: continue
            if fecha_cumple > fecha_fin: break
            cumpleaños_durante.append({"fecha": fecha_cumple, "edad_nueva": edad_inicial + i})

        periodos = []
        fecha_actual = fecha_inicio
        edad_actual = edad_inicial

        for cumple in cumpleaños_durante:
            meses_periodo = meses_entre_fechas(fecha_actual, cumple["fecha"])
            tarifa = obtener_tarifa_por_edad(edad_actual)
            periodos.append({"meses": meses_periodo, "edad": edad_actual, "tarifa": tarifa})
            fecha_actual = cumple["fecha"]
            edad_actual = cumple["edad_nueva"]

        meses_final = meses_entre_fechas(fecha_actual, fecha_fin)
        tarifa_final = obtener_tarifa_por_edad(edad_actual)
        periodos.append({"meses": meses_final, "edad": edad_actual, "tarifa": tarifa_final})

        millones = monto_solicitado / 1_000_000
        seguro_total = 0

        for periodo in periodos:
            seguro_periodo = periodo["tarifa"] * millones * periodo["meses"]
            seguro_total += seguro_periodo

        return int(round(seguro_total))

    except Exception as e:
        print(f"❌ Error en cálculo proporcional de seguro: {e}")
        return 0


def obtener_aval_dinamico(monto_solicitado, tipo_credito, datos_linea, scoring_result, scoring_config):
    """
    Calcula el aval dinámico basado en el nivel de riesgo del scoring.
    """
    try:
        # 1. Aval dinámico directo en scoring_result
        if scoring_result and isinstance(scoring_result, dict) and "aval_dinamico" in scoring_result:
            if scoring_result["aval_dinamico"]:
                aval_porcentaje = scoring_result["aval_dinamico"]["porcentaje"]
                return int(round(monto_solicitado * aval_porcentaje))

        # 2. Calcular basado en score normalizado
        puntaje_scoring = None
        if scoring_result and isinstance(scoring_result, dict) and "score_normalizado" in scoring_result:
            puntaje_scoring = scoring_result["score_normalizado"]
        
        if puntaje_scoring is None:
            return int(round(monto_solicitado * datos_linea["aval_porcentaje"]))

        # 3. Buscar nivel en scoring_config
        nivel_riesgo = None
        for nivel in scoring_config.get("niveles_riesgo", []):
            if nivel["min"] <= puntaje_scoring <= nivel["max"]:
                nivel_riesgo = nivel
                break

        if nivel_riesgo and "aval_por_producto" in nivel_riesgo and tipo_credito in nivel_riesgo["aval_por_producto"]:
            aval_porcentaje = nivel_riesgo["aval_por_producto"][tipo_credito]
            return int(round(monto_solicitado * aval_porcentaje))

        return int(round(monto_solicitado * datos_linea["aval_porcentaje"]))

    except Exception as e:
        print(f"ERROR en obtener_aval_dinamico: {str(e)}")
        return int(round(monto_solicitado * datos_linea.get("aval_porcentaje", 0.10)))


def obtener_tasa_por_nivel_riesgo(nivel_riesgo, linea_credito, scoring_config, scoring_linea_data=None):
    """
    Obtiene las tasas de interés según el nivel de riesgo y línea de crédito.
    """
    try:
        if not nivel_riesgo or not linea_credito:
            return None

        nivel_norm = nivel_riesgo.lower().strip()

        # PASO 1: Scoring multi-línea
        if scoring_linea_data and scoring_linea_data.get("niveles_riesgo"):
            niveles = scoring_linea_data["niveles_riesgo"]
            for nivel in niveles:
                nombre_nivel = nivel.get("nombre", "").lower().strip()
                if (nombre_nivel == nivel_norm or
                    ("alto" in nombre_nivel and "alto" in nivel_norm) or
                    ("moderado" in nombre_nivel and "moderado" in nivel_norm) or
                    ("bajo" in nombre_nivel and "bajo" in nivel_norm) or
                    ("rescate" in nombre_nivel and "rescate" in nivel_norm)):
                    
                    return {
                        "tasa_anual": nivel.get("tasa_ea", 25),
                        "tasa_mensual": nivel.get("tasa_nominal_mensual", 1.88),
                        "color": nivel.get("color", "#999999"),
                        "aval_porcentaje": nivel.get("aval_porcentaje", 0.10),
                    }

        # PASO 2: Fallback scoring general
        niveles_riesgo_list = scoring_config.get("niveles_riesgo", [])
        for nivel in niveles_riesgo_list:
            nombre_nivel = nivel.get("nombre", "").lower().strip()
            if (nombre_nivel == nivel_norm or
                ("alto" in nombre_nivel and "alto" in nivel_norm) or
                ("moderado" in nombre_nivel and "moderado" in nivel_norm) or
                ("bajo" in nombre_nivel and "bajo" in nivel_norm)):
                
                tasas_por_producto = nivel.get("tasas_por_producto", {})
                if linea_credito in tasas_por_producto:
                    tasas = tasas_por_producto[linea_credito]
                    return {
                        "tasa_anual": tasas["tasa_anual"],
                        "tasa_mensual": tasas["tasa_mensual"],
                        "color": nivel.get("color", "#999999"),
                    }

        return None
    except Exception as e:
        print(f"Error en obtener_tasa_por_nivel_riesgo: {e}")
        return None
