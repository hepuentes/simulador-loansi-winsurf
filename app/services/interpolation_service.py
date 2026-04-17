"""
Servicio de Interpolación Dinámica para Scoring

Implementa interpolación lineal inversa para calcular tasas y avales
según el score exacto del cliente dentro de un nivel de riesgo.

Fórmula:
    Valor_Interpolado = Valor_Max_Rango - (Valor_Max - Valor_Min) × Factor_Posición
    Factor_Posición = (Score_Cliente - Score_Min_Nivel) / (Score_Max_Nivel - Score_Min_Nivel)

Autor: Sistema LOANSI
Fecha: Febrero 2026
"""

import sqlite3
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


# Ruta a la base de datos
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "loansi.db")


@dataclass
class ResultadoInterpolacion:
    """Resultado del cálculo de interpolación."""
    score_cliente: float
    nivel_nombre: str
    nivel_codigo: str
    score_min_nivel: float
    score_max_nivel: float
    factor_posicion: float          # 0.0 a 1.0 (posición dentro del nivel)
    tasa_ea_interpolada: float      # Tasa E.A. calculada
    tasa_nominal_interpolada: float # Tasa nominal mensual calculada
    aval_interpolado: float         # Porcentaje de aval calculado
    color_nivel: str
    interpolacion_activa: bool      # Si se usó interpolación o valor fijo
    desglose: Dict                  # Desglose del cálculo para UI


@dataclass
class ResultadoDegradacion:
    """Resultado de aplicar reglas de degradación."""
    score_original: float
    score_ajustado: float
    nivel_original: str
    nivel_ajustado: str
    penalizacion_puntos: float
    niveles_degradados: int
    reglas_aplicadas: List[Dict]
    requiere_evaluacion_manual: bool
    mensaje: str


def conectar_db():
    """Conecta a la base de datos SQLite."""
    return sqlite3.connect(DB_PATH)


def calcular_factor_posicion(score: float, score_min: float, score_max: float) -> float:
    """
    Calcula el factor de posición del score dentro del rango del nivel.
    
    Args:
        score: Score del cliente
        score_min: Score mínimo del nivel
        score_max: Score máximo del nivel
        
    Returns:
        Factor entre 0.0 (peor) y 1.0 (mejor)
    """
    if score_max == score_min:
        return 0.5  # Si el rango es de un solo punto
    
    factor = (score - score_min) / (score_max - score_min)
    return max(0.0, min(1.0, factor))  # Limitar entre 0 y 1


def interpolar_valor(valor_at_min: float, valor_at_max: float, factor: float) -> float:
    """
    Interpola un valor usando interpolación lineal inversa.
    Mayor score = menor valor (mejor tasa/aval).
    
    Args:
        valor_at_min: Valor cuando score = score_min (el peor/más alto)
        valor_at_max: Valor cuando score = score_max (el mejor/más bajo)
        factor: Factor de posición (0.0 a 1.0)
        
    Returns:
        Valor interpolado
    """
    delta = valor_at_min - valor_at_max
    return valor_at_min - (delta * factor)


def obtener_nivel_por_score(linea_id: int, score: float) -> Optional[Dict]:
    """
    Obtiene el nivel de riesgo correspondiente a un score.
    
    Args:
        linea_id: ID de la línea de crédito
        score: Score del cliente
        
    Returns:
        Diccionario con datos del nivel o None si no se encuentra
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, nombre, codigo, score_min, score_max,
                   tasa_ea, tasa_nominal_mensual, aval_porcentaje,
                   tasa_ea_at_min, tasa_ea_at_max, aval_at_min, aval_at_max,
                   interpolacion_activa, color, orden
            FROM niveles_riesgo_linea
            WHERE linea_credito_id = ? 
              AND ? >= score_min AND ? <= score_max
              AND activo = 1
            ORDER BY orden
            LIMIT 1
        """, (linea_id, score, score))
        
        row = cursor.fetchone()
        if not row:
            return None
            
        return {
            "id": row[0],
            "nombre": row[1],
            "codigo": row[2],
            "score_min": row[3],
            "score_max": row[4],
            "tasa_ea": row[5],
            "tasa_nominal_mensual": row[6],
            "aval_porcentaje": row[7],
            "tasa_ea_at_min": row[8] or row[5],  # Fallback a tasa_ea
            "tasa_ea_at_max": row[9] or row[5],
            "aval_at_min": row[10] or row[7],    # Fallback a aval_porcentaje
            "aval_at_max": row[11] or row[7],
            "interpolacion_activa": bool(row[12]) if row[12] is not None else False,
            "color": row[13],
            "orden": row[14]
        }
        
    finally:
        conn.close()


def calcular_interpolacion(
    linea_id: int, 
    score: float,
    forzar_interpolacion: bool = False
) -> Optional[ResultadoInterpolacion]:
    """
    Calcula la tasa y aval interpolados para un score específico.
    
    Args:
        linea_id: ID de la línea de crédito
        score: Score del cliente (0-100)
        forzar_interpolacion: Si True, usa interpolación aunque no esté activa
        
    Returns:
        ResultadoInterpolacion con todos los valores calculados
    """
    nivel = obtener_nivel_por_score(linea_id, score)
    if not nivel:
        return None
    
    usar_interpolacion = nivel["interpolacion_activa"] or forzar_interpolacion
    
    # Calcular factor de posición
    factor = calcular_factor_posicion(
        score, 
        nivel["score_min"], 
        nivel["score_max"]
    )
    
    if usar_interpolacion:
        # Interpolar tasa E.A.
        tasa_ea = interpolar_valor(
            nivel["tasa_ea_at_min"],
            nivel["tasa_ea_at_max"],
            factor
        )
        
        # Calcular tasa nominal mensual desde la E.A. interpolada
        tasa_nominal = (pow(1 + tasa_ea/100, 1/12) - 1) * 100
        
        # Interpolar aval
        aval = interpolar_valor(
            nivel["aval_at_min"],
            nivel["aval_at_max"],
            factor
        )
    else:
        # Usar valores fijos del nivel
        tasa_ea = nivel["tasa_ea"]
        tasa_nominal = nivel["tasa_nominal_mensual"]
        aval = nivel["aval_porcentaje"]
    
    # Construir desglose del cálculo para UI
    desglose = {
        "score_min_nivel": nivel["score_min"],
        "score_max_nivel": nivel["score_max"],
        "tasa_en_score_min": nivel["tasa_ea_at_min"],
        "tasa_en_score_max": nivel["tasa_ea_at_max"],
        "aval_en_score_min": nivel["aval_at_min"],
        "aval_en_score_max": nivel["aval_at_max"],
        "factor_posicion_porcentaje": round(factor * 100, 2),
        "delta_tasa": round(nivel["tasa_ea_at_min"] - nivel["tasa_ea_at_max"], 4),
        "delta_aval": round(nivel["aval_at_min"] - nivel["aval_at_max"], 4),
        "formula_aplicada": f"Tasa = {nivel['tasa_ea_at_min']}% - ({nivel['tasa_ea_at_min'] - nivel['tasa_ea_at_max']}% × {factor:.4f})"
    }
    
    return ResultadoInterpolacion(
        score_cliente=score,
        nivel_nombre=nivel["nombre"],
        nivel_codigo=nivel["codigo"],
        score_min_nivel=nivel["score_min"],
        score_max_nivel=nivel["score_max"],
        factor_posicion=factor,
        tasa_ea_interpolada=round(tasa_ea, 4),
        tasa_nominal_interpolada=round(tasa_nominal, 4),
        aval_interpolado=round(aval, 4),
        color_nivel=nivel["color"],
        interpolacion_activa=usar_interpolacion,
        desglose=desglose
    )


def obtener_reglas_degradacion(linea_id: Optional[int] = None, tipo_regla: Optional[str] = None) -> List[Dict]:
    """
    Obtiene las reglas de degradación configuradas.
    
    Args:
        linea_id: ID de línea específica (None para reglas globales)
        tipo_regla: Tipo de regla a filtrar (ej: 'mora_telcos')
        
    Returns:
        Lista de reglas de degradación
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        query = """
            SELECT id, linea_credito_id, tipo_regla, descripcion,
                   umbral_min, umbral_max, accion, valor_accion, orden
            FROM reglas_degradacion
            WHERE activo = 1
              AND (linea_credito_id IS NULL OR linea_credito_id = ?)
        """
        params = [linea_id]
        
        if tipo_regla:
            query += " AND tipo_regla = ?"
            params.append(tipo_regla)
            
        query += " ORDER BY tipo_regla, orden"
        
        cursor.execute(query, params)
        
        reglas = []
        for row in cursor.fetchall():
            reglas.append({
                "id": row[0],
                "linea_credito_id": row[1],
                "tipo_regla": row[2],
                "descripcion": row[3],
                "umbral_min": row[4],
                "umbral_max": row[5],
                "accion": row[6],
                "valor_accion": row[7],
                "orden": row[8]
            })
        
        return reglas
        
    finally:
        conn.close()


def aplicar_degradacion_mora_telcos(
    score: float,
    monto_mora_telcos: float,
    linea_id: int
) -> ResultadoDegradacion:
    """
    Aplica reglas de degradación por mora en telecomunicaciones.
    
    Umbrales (Ley 2157 de 2021):
    - $0 - $100,000: Sin impacto
    - $100,001 - $200,000: -5 puntos (sin degradar nivel)
    - $200,001 - $500,000: Degradar 1 nivel
    - $500,001 - $1,000,000: Degradar 2 niveles
    - > $1,000,000: Tratamiento como mora financiera
    
    Args:
        score: Score actual del cliente
        monto_mora_telcos: Monto de mora en telecomunicaciones (COP)
        linea_id: ID de la línea de crédito
        
    Returns:
        ResultadoDegradacion con el resultado de aplicar las reglas
    """
    reglas = obtener_reglas_degradacion(linea_id, 'mora_telcos')
    
    score_ajustado = score
    penalizacion = 0.0
    niveles_a_degradar = 0
    reglas_aplicadas = []
    requiere_manual = False
    mensaje = ""
    
    for regla in reglas:
        umbral_min = regla["umbral_min"] or 0
        umbral_max = regla["umbral_max"]
        
        # Verificar si el monto cae en este rango
        en_rango = monto_mora_telcos >= umbral_min
        if umbral_max is not None:
            en_rango = en_rango and monto_mora_telcos <= umbral_max
            
        if en_rango:
            accion = regla["accion"]
            valor = regla["valor_accion"] or 0
            
            if accion == "sin_impacto":
                mensaje = "Monto de mora menor, sin impacto en scoring"
                
            elif accion == "penalizar_puntos":
                penalizacion = valor
                score_ajustado = score - penalizacion
                mensaje = f"Penalización de {valor} puntos por mora en telcos"
                
            elif accion == "degradar_nivel":
                niveles_a_degradar = int(valor)
                mensaje = f"Degradar {niveles_a_degradar} nivel(es) por mora en telcos"
                
            elif accion == "mora_financiera":
                requiere_manual = True
                mensaje = "Monto elevado - tratamiento igual a mora financiera tradicional"
                
            reglas_aplicadas.append({
                "regla": regla["descripcion"],
                "accion": accion,
                "valor": valor
            })
            break  # Solo aplica la primera regla que coincida
    
    # Obtener nivel original y ajustado
    nivel_original = obtener_nivel_por_score(linea_id, score)
    nivel_ajustado_nombre = nivel_original["nombre"] if nivel_original else "Desconocido"
    
    if niveles_a_degradar > 0 and nivel_original:
        # Buscar nivel degradado
        conn = conectar_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT nombre FROM niveles_riesgo_linea
                WHERE linea_credito_id = ? AND activo = 1
                ORDER BY orden
            """, (linea_id,))
            niveles = [row[0] for row in cursor.fetchall()]
            
            if nivel_original["nombre"] in niveles:
                idx_actual = niveles.index(nivel_original["nombre"])
                idx_nuevo = min(idx_actual + niveles_a_degradar, len(niveles) - 1)
                nivel_ajustado_nombre = niveles[idx_nuevo]
        finally:
            conn.close()
    
    return ResultadoDegradacion(
        score_original=score,
        score_ajustado=max(0, score_ajustado),
        nivel_original=nivel_original["nombre"] if nivel_original else "Desconocido",
        nivel_ajustado=nivel_ajustado_nombre,
        penalizacion_puntos=penalizacion,
        niveles_degradados=niveles_a_degradar,
        reglas_aplicadas=reglas_aplicadas,
        requiere_evaluacion_manual=requiere_manual,
        mensaje=mensaje
    )


def aplicar_todas_degradaciones(
    score: float,
    linea_id: int,
    datos_cliente: Dict
) -> ResultadoDegradacion:
    """
    Aplica todas las reglas de degradación aplicables a un cliente.
    
    Args:
        score: Score calculado del cliente
        linea_id: ID de la línea de crédito
        datos_cliente: Diccionario con datos del cliente:
            - monto_mora_telcos: float
            - consultas_30_dias: int
            - meses_desde_mora_pagada: int (0 si no tiene)
            - tiene_historial: bool
            - empleadores_ultimo_anio: int
            - cambios_direccion_12_meses: int
            
    Returns:
        ResultadoDegradacion con el resultado acumulado
    """
    score_ajustado = score
    penalizacion_total = 0.0
    niveles_degradados_total = 0
    todas_reglas_aplicadas = []
    requiere_manual = False
    mensajes = []
    
    # 1. Mora en telecomunicaciones
    if datos_cliente.get("monto_mora_telcos", 0) > 0:
        resultado_telcos = aplicar_degradacion_mora_telcos(
            score_ajustado,
            datos_cliente["monto_mora_telcos"],
            linea_id
        )
        score_ajustado = resultado_telcos.score_ajustado
        penalizacion_total += resultado_telcos.penalizacion_puntos
        niveles_degradados_total += resultado_telcos.niveles_degradados
        todas_reglas_aplicadas.extend(resultado_telcos.reglas_aplicadas)
        if resultado_telcos.mensaje:
            mensajes.append(resultado_telcos.mensaje)
        if resultado_telcos.requiere_evaluacion_manual:
            requiere_manual = True
    
    # 2. Consultas excesivas
    consultas = datos_cliente.get("consultas_30_dias", 0)
    if consultas > 5:
        penalizacion_total += 5
        score_ajustado -= 5
        todas_reglas_aplicadas.append({
            "regla": f"Consultas excesivas ({consultas} en 30 días)",
            "accion": "penalizar_puntos",
            "valor": 5
        })
        mensajes.append(f"Penalización de 5 puntos por {consultas} consultas en 30 días")
    
    # 3. Mora pagada reciente
    meses_mora = datos_cliente.get("meses_desde_mora_pagada", 999)
    if meses_mora < 6 and meses_mora > 0:
        niveles_degradados_total += 1
        todas_reglas_aplicadas.append({
            "regla": f"Mora pagada hace {meses_mora} meses",
            "accion": "degradar_nivel",
            "valor": 1
        })
        mensajes.append(f"Degradar 1 nivel por mora pagada hace {meses_mora} meses")
    
    # 4. Sin historial crediticio
    if not datos_cliente.get("tiene_historial", True):
        niveles_degradados_total += 1
        todas_reglas_aplicadas.append({
            "regla": "Primera vez sin historial crediticio",
            "accion": "degradar_nivel",
            "valor": 1
        })
        mensajes.append("Degradar 1 nivel por ausencia de historial crediticio")
    
    # 5. Múltiples empleadores
    empleadores = datos_cliente.get("empleadores_ultimo_anio", 1)
    if empleadores > 3:
        penalizacion_total += 10
        score_ajustado -= 10
        todas_reglas_aplicadas.append({
            "regla": f"Múltiples empleadores ({empleadores} en último año)",
            "accion": "penalizar_puntos",
            "valor": 10
        })
        mensajes.append(f"Penalización de 10 puntos por {empleadores} empleadores en último año")
    
    # 6. Dirección inestable
    cambios = datos_cliente.get("cambios_direccion_12_meses", 0)
    if cambios > 2:
        penalizacion_total += 5
        score_ajustado -= 5
        todas_reglas_aplicadas.append({
            "regla": f"Dirección inestable ({cambios} cambios)",
            "accion": "penalizar_puntos",
            "valor": 5
        })
        mensajes.append(f"Penalización de 5 puntos por {cambios} cambios de dirección")
    
    # Determinar nivel final
    nivel_original = obtener_nivel_por_score(linea_id, score)
    nivel_ajustado = obtener_nivel_por_score(linea_id, score_ajustado)
    
    # Si hay degradación por niveles, ajustar
    nivel_final_nombre = nivel_ajustado["nombre"] if nivel_ajustado else "Rechazado"
    
    if niveles_degradados_total > 0 and nivel_original:
        conn = conectar_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT nombre FROM niveles_riesgo_linea
                WHERE linea_credito_id = ? AND activo = 1
                ORDER BY score_min DESC
            """, (linea_id,))
            niveles = [row[0] for row in cursor.fetchall()]
            
            if nivel_original["nombre"] in niveles:
                idx_actual = niveles.index(nivel_original["nombre"])
                idx_nuevo = min(idx_actual + niveles_degradados_total, len(niveles) - 1)
                nivel_final_nombre = niveles[idx_nuevo]
        finally:
            conn.close()
    
    return ResultadoDegradacion(
        score_original=score,
        score_ajustado=max(0, score_ajustado),
        nivel_original=nivel_original["nombre"] if nivel_original else "Desconocido",
        nivel_ajustado=nivel_final_nombre,
        penalizacion_puntos=penalizacion_total,
        niveles_degradados=niveles_degradados_total,
        reglas_aplicadas=todas_reglas_aplicadas,
        requiere_evaluacion_manual=requiere_manual,
        mensaje=" | ".join(mensajes) if mensajes else "Sin degradaciones aplicadas"
    )


def calcular_scoring_completo(
    linea_id: int,
    score_base: float,
    datos_cliente: Dict
) -> Dict:
    """
    Calcula el scoring completo incluyendo degradaciones e interpolación.
    
    Args:
        linea_id: ID de la línea de crédito
        score_base: Score base calculado
        datos_cliente: Datos del cliente para evaluar degradaciones
        
    Returns:
        Diccionario con resultado completo del scoring
    """
    # 1. Aplicar degradaciones
    degradacion = aplicar_todas_degradaciones(score_base, linea_id, datos_cliente)
    
    # 2. Calcular interpolación con score ajustado
    interpolacion = calcular_interpolacion(linea_id, degradacion.score_ajustado)
    
    if not interpolacion:
        return {
            "exito": False,
            "error": "No se encontró nivel para el score calculado",
            "score_base": score_base,
            "score_ajustado": degradacion.score_ajustado,
            "degradacion": degradacion.__dict__
        }
    
    return {
        "exito": True,
        "score_base": score_base,
        "score_ajustado": degradacion.score_ajustado,
        "nivel_final": interpolacion.nivel_nombre,
        "tasa_ea": interpolacion.tasa_ea_interpolada,
        "tasa_nominal_mensual": interpolacion.tasa_nominal_interpolada,
        "aval_porcentaje": interpolacion.aval_interpolado,
        "color_nivel": interpolacion.color_nivel,
        "interpolacion_activa": interpolacion.interpolacion_activa,
        "factor_posicion": interpolacion.factor_posicion,
        "degradacion": {
            "penalizacion_puntos": degradacion.penalizacion_puntos,
            "niveles_degradados": degradacion.niveles_degradados,
            "reglas_aplicadas": degradacion.reglas_aplicadas,
            "requiere_manual": degradacion.requiere_evaluacion_manual,
            "mensaje": degradacion.mensaje
        },
        "desglose_interpolacion": interpolacion.desglose
    }


# Funciones auxiliares para configuración de Admin

def guardar_config_interpolacion_nivel(nivel_id: int, config: Dict) -> bool:
    """
    Guarda la configuración de interpolación para un nivel.
    
    Args:
        nivel_id: ID del nivel de riesgo
        config: Diccionario con:
            - tasa_ea_at_min: Tasa en score_min
            - tasa_ea_at_max: Tasa en score_max
            - aval_at_min: Aval en score_min
            - aval_at_max: Aval en score_max
            - interpolacion_activa: bool
            
    Returns:
        True si se guardó exitosamente
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE niveles_riesgo_linea
            SET tasa_ea_at_min = ?,
                tasa_ea_at_max = ?,
                aval_at_min = ?,
                aval_at_max = ?,
                interpolacion_activa = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            config.get("tasa_ea_at_min"),
            config.get("tasa_ea_at_max"),
            config.get("aval_at_min"),
            config.get("aval_at_max"),
            1 if config.get("interpolacion_activa") else 0,
            nivel_id
        ))
        
        conn.commit()
        return cursor.rowcount > 0
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error guardando config interpolación: {e}")
        return False
    finally:
        conn.close()


def obtener_config_interpolacion_nivel(nivel_id: int) -> Optional[Dict]:
    """Obtiene la configuración de interpolación de un nivel."""
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT tasa_ea_at_min, tasa_ea_at_max, aval_at_min, aval_at_max, interpolacion_activa
            FROM niveles_riesgo_linea
            WHERE id = ?
        """, (nivel_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
            
        return {
            "tasa_ea_at_min": row[0],
            "tasa_ea_at_max": row[1],
            "aval_at_min": row[2],
            "aval_at_max": row[3],
            "interpolacion_activa": bool(row[4])
        }
        
    finally:
        conn.close()


# Ejemplo de uso
if __name__ == "__main__":
    # Ejemplo: Cliente LoansiFlex con score de 62 (Nivel Moderado: 55-74)
    print("=== Ejemplo de Interpolación ===")
    
    # Suponiendo línea_id = 1 para LoansiFlex
    resultado = calcular_interpolacion(1, 62, forzar_interpolacion=True)
    
    if resultado:
        print(f"Score: {resultado.score_cliente}")
        print(f"Nivel: {resultado.nivel_nombre}")
        print(f"Factor posición: {resultado.factor_posicion:.4f} ({resultado.factor_posicion*100:.2f}%)")
        print(f"Tasa E.A.: {resultado.tasa_ea_interpolada}%")
        print(f"Tasa Nominal: {resultado.tasa_nominal_interpolada}%")
        print(f"Aval: {resultado.aval_interpolado*100:.2f}%")
        print(f"\nDesglose: {resultado.desglose}")
