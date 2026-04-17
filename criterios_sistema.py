"""
CRITERIOS_SISTEMA.PY - Criterios predefinidos del sistema para factores de rechazo
==================================================================================

Define los criterios estándar del sistema que pueden usarse en factores de rechazo.
Estos criterios son independientes de los criterios de scoring configurables.
"""

# Criterios predefinidos del sistema para factores de rechazo
CRITERIOS_SISTEMA = [
    {
        "id": "score_datacredito",
        "nombre": "Score DataCrédito",
        "tipo": "numerico",
        "unidad": "puntos",
        "rango_min": 150,
        "rango_max": 950,
        "descripcion": "Puntaje de DataCrédito del solicitante",
        "mensaje_sugerido": "Score DataCrédito {operador_texto} {valor} puntos"
    },
    {
        "id": "score_interno",
        "nombre": "Score interno",
        "tipo": "numerico",
        "unidad": "puntos",
        "rango_min": 0,
        "rango_max": 100,
        "descripcion": "Puntaje interno calculado por el sistema",
        "mensaje_sugerido": "Score interno {operador_texto} {valor} puntos"
    },
    {
        "id": "mora_financiero_dias",
        "nombre": "Mora activa sector financiero",
        "tipo": "numerico",
        "unidad": "días",
        "rango_min": 0,
        "rango_max": 999,
        "descripcion": "Días de mora activa en sector financiero",
        "mensaje_sugerido": "Mora en sector financiero {operador_texto} {valor} días"
    },
    {
        "id": "mora_telcos_monto",
        "nombre": "Mora en telecomunicaciones (monto)",
        "tipo": "numerico",
        "unidad": "COP",
        "rango_min": 0,
        "rango_max": 99999999,
        "descripcion": "Monto de mora en telecomunicaciones",
        "mensaje_sugerido": "Mora en telcos {operador_texto} ${valor:,.0f} COP"
    },
    {
        "id": "mora_telcos_dias",
        "nombre": "Mora telcos (días)",
        "tipo": "numerico",
        "unidad": "días",
        "rango_min": 0,
        "rango_max": 999,
        "descripcion": "Días de mora en telecomunicaciones",
        "mensaje_sugerido": "Mora en telcos {operador_texto} {valor} días"
    },
    {
        "id": "dti",
        "nombre": "Relación deuda/ingreso (DTI)",
        "tipo": "numerico",
        "unidad": "%",
        "rango_min": 0,
        "rango_max": 100,
        "descripcion": "Porcentaje de endeudamiento sobre ingresos",
        "mensaje_sugerido": "DTI {operador_texto} {valor}%"
    },
    {
        "id": "obligaciones_castigo",
        "nombre": "Obligaciones en castigo",
        "tipo": "numerico",
        "unidad": "cantidad",
        "rango_min": 0,
        "rango_max": 99,
        "descripcion": "Cantidad de obligaciones en castigo",
        "mensaje_sugerido": "Obligaciones en castigo {operador_texto} {valor}"
    },
    {
        "id": "consultas_3_meses",
        "nombre": "Consultas últimos 3 meses",
        "tipo": "numerico",
        "unidad": "cantidad",
        "rango_min": 0,
        "rango_max": 99,
        "descripcion": "Número de consultas en los últimos 3 meses",
        "mensaje_sugerido": "Consultas (3 meses) {operador_texto} {valor}"
    },
    {
        "id": "edad",
        "nombre": "Edad del solicitante",
        "tipo": "numerico",
        "unidad": "años",
        "rango_min": 18,
        "rango_max": 100,
        "descripcion": "Edad del solicitante en años",
        "mensaje_sugerido": "Edad {operador_texto} {valor} años"
    },
    {
        "id": "antiguedad_laboral",
        "nombre": "Antigüedad laboral",
        "tipo": "numerico",
        "unidad": "meses",
        "rango_min": 0,
        "rango_max": 600,
        "descripcion": "Meses de antigüedad en el empleo actual",
        "mensaje_sugerido": "Antigüedad laboral {operador_texto} {valor} meses"
    },
    {
        "id": "ingreso_minimo",
        "nombre": "Ingreso mínimo verificable",
        "tipo": "numerico",
        "unidad": "COP",
        "rango_min": 0,
        "rango_max": 999999999,
        "descripcion": "Ingreso mensual verificable",
        "mensaje_sugerido": "Ingreso verificable {operador_texto} ${valor:,.0f} COP"
    },
    {
        "id": "verificacion_sarlaft",
        "nombre": "Verificación SARLAFT",
        "tipo": "binario",
        "valores": [0, 1],
        "descripcion": "0 = Falla en verificación, 1 = Aprobado",
        "mensaje_sugerido": "Falla en verificación SARLAFT"
    },
    {
        "id": "validacion_identidad",
        "nombre": "Validación de identidad",
        "tipo": "binario",
        "valores": [0, 1],
        "descripcion": "0 = No verificado, 1 = Verificado",
        "mensaje_sugerido": "Falla en validación de identidad"
    },
    {
        "id": "cupo_disponible",
        "nombre": "Cupo disponible DataCrédito",
        "tipo": "numerico",
        "unidad": "COP",
        "rango_min": 0,
        "rango_max": 999999999,
        "descripcion": "Cupo total disponible reportado en DataCrédito",
        "mensaje_sugerido": "Cupo disponible {operador_texto} ${valor:,.0f} COP"
    },
    {
        "id": "historial_pagos_meses",
        "nombre": "Historial de pagos",
        "tipo": "numerico",
        "unidad": "meses",
        "rango_min": 0,
        "rango_max": 240,
        "descripcion": "Meses de historial de pagos verificable",
        "mensaje_sugerido": "Historial de pagos {operador_texto} {valor} meses"
    }
]

# Diccionario indexado por ID para acceso rápido
CRITERIOS_SISTEMA_POR_ID = {c["id"]: c for c in CRITERIOS_SISTEMA}

# Mapeo de texto de operadores para mensajes legibles
OPERADORES_TEXTO = {
    "<": "menor que",
    "<=": "menor o igual a",
    ">": "mayor que",
    ">=": "mayor o igual a",
    "==": "igual a"
}


def obtener_criterios_sistema():
    """
    Retorna la lista de criterios del sistema.
    
    Returns:
        list: Lista de criterios predefinidos del sistema
    """
    return CRITERIOS_SISTEMA


def obtener_criterio_sistema_por_id(criterio_id):
    """
    Obtiene un criterio del sistema por su ID.
    
    Args:
        criterio_id: ID del criterio a buscar
        
    Returns:
        dict o None: Criterio encontrado o None si no existe
    """
    return CRITERIOS_SISTEMA_POR_ID.get(criterio_id)


def generar_mensaje_rechazo(criterio_id, operador, valor):
    """
    Genera un mensaje de rechazo sugerido basado en el criterio.
    
    Args:
        criterio_id: ID del criterio
        operador: Operador de comparación (<, >, <=, >=, ==)
        valor: Valor límite
        
    Returns:
        str: Mensaje de rechazo sugerido
    """
    criterio = CRITERIOS_SISTEMA_POR_ID.get(criterio_id)
    if not criterio:
        return f"Criterio {criterio_id} {OPERADORES_TEXTO.get(operador, operador)} {valor}"
    
    mensaje_base = criterio.get("mensaje_sugerido", f"{criterio['nombre']} {{operador_texto}} {{valor}}")
    
    try:
        return mensaje_base.format(
            operador_texto=OPERADORES_TEXTO.get(operador, operador),
            valor=valor
        )
    except (KeyError, ValueError):
        return f"{criterio['nombre']} {OPERADORES_TEXTO.get(operador, operador)} {valor}"


def normalizar_criterio_existente(criterio_texto):
    """
    Intenta hacer match de un texto de criterio existente con los criterios del sistema.
    Útil para migración de datos existentes.
    
    Args:
        criterio_texto: Texto del criterio a normalizar
        
    Returns:
        tuple: (criterio_id, tipo_criterio) donde tipo_criterio es 'sistema', 'scoring' o 'personalizado'
    """
    if not criterio_texto:
        return None, "personalizado"
    
    texto_normalizado = criterio_texto.lower().strip()
    
    # Mapeo de variaciones comunes a IDs del sistema
    mapeo_variaciones = {
        "score datacredito": "score_datacredito",
        "score datacrédito": "score_datacredito",
        "puntaje datacredito": "score_datacredito",
        "score interno": "score_interno",
        "puntaje interno": "score_interno",
        "mora financiero": "mora_financiero_dias",
        "mora sector financiero": "mora_financiero_dias",
        "mora activa sector financiero": "mora_financiero_dias",
        "mora telcos": "mora_telcos_dias",
        "mora telecomunicaciones": "mora_telcos_monto",
        "mora en telecomunicaciones": "mora_telcos_monto",
        "dti": "dti",
        "relación deuda/ingreso": "dti",
        "relacion deuda ingreso": "dti",
        "obligaciones en castigo": "obligaciones_castigo",
        "castigo": "obligaciones_castigo",
        "consultas": "consultas_3_meses",
        "consultas 3 meses": "consultas_3_meses",
        "consultas últimos 3 meses": "consultas_3_meses",
        "edad": "edad",
        "edad minima": "edad",
        "edad máxima": "edad",
        "antiguedad laboral": "antiguedad_laboral",
        "antigüedad laboral": "antiguedad_laboral",
        "ingreso": "ingreso_minimo",
        "ingreso minimo": "ingreso_minimo",
        "ingreso mínimo": "ingreso_minimo",
        "sarlaft": "verificacion_sarlaft",
        "verificación sarlaft": "verificacion_sarlaft",
        "validacion identidad": "validacion_identidad",
        "validación identidad": "validacion_identidad",
        "identidad": "validacion_identidad",
        "cupo": "cupo_disponible",
        "cupo disponible": "cupo_disponible",
        "historial pagos": "historial_pagos_meses",
        "historial de pagos": "historial_pagos_meses"
    }
    
    # Buscar match exacto primero
    if texto_normalizado in mapeo_variaciones:
        return mapeo_variaciones[texto_normalizado], "sistema"
    
    # Buscar match parcial
    for variacion, criterio_id in mapeo_variaciones.items():
        if variacion in texto_normalizado or texto_normalizado in variacion:
            return criterio_id, "sistema"
    
    # No se encontró match - es personalizado o criterio de scoring
    return criterio_texto, "personalizado"
