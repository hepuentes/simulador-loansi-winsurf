"""
SCORING_ENGINE.PY - Motor de cálculo de scores del test psicométrico
=====================================================================
Calcula scores por bloque, score total ponderado y flags de validación.
Usa escala 0-100 por bloque, ponderación global configurable.
"""

# Ítems con escala Likert invertida (5 = peor → se convierte a 5 = mejor)
ITEMS_REVERSOS = ['a3', 'b2', 'd2', 'e1', 'd5']

# Ítems de atención: campo → valor esperado
ITEMS_ATENCION = {'atencion_1': 2, 'atencion_2': 4, 'atencion_3': 3}

# Configuración de bloques: ítems y peso en el score total
BLOQUES = {
    'a': {'items': ['a1', 'a2', 'a3', 'a4', 'a5'], 'peso': 0.35},
    'b': {'items': ['b1', 'b2', 'b3'], 'peso': 0.15},
    'c': {'items': ['c1', 'c2', 'c3', 'c4'], 'peso': 0.20},
    'd': {'items': ['d1', 'd2', 'd3', 'd4', 'd5'], 'peso': 0.20},
    'e': {'items': ['e1', 'e2', 'e3'], 'peso': 0.10},
}

# Ítems Likert estándar (para detección de straight-lining)
LIKERT_ITEMS = [
    'a1', 'a2', 'a3', 'a4', 'a5',
    'b1', 'b2', 'b3',
    'c1', 'c2', 'c4',
    'd1', 'd2', 'd3',
    'e1', 'e2', 'e3',
]


def calcular_scores(registro):
    """
    Calcula scores por bloque, score total ponderado y flags de validación.

    Args:
        registro: dict con las respuestas del test (claves a1, a2, ..., e3,
                  atencion_1, atencion_2, atencion_3, etc.)

    Returns:
        dict con score_total, scores por bloque, flags y estado_validacion
    """
    # 1. Copiar registro para no mutar el original
    resp = dict(registro)

    # 2. Convertir c3 (binario MPL) a escala 1-5
    #    c3=1 → impulsivo (recibe hoy) → 1
    #    c3=2 → paciente (espera un mes) → 5
    if resp.get('c3') == 1:
        resp['c3'] = 1
    elif resp.get('c3') == 2:
        resp['c3'] = 5

    # 3. Convertir d4 (situacional tri) a escala 1-5
    #    d4=0 → se queda con la plata → 1
    #    d4=1 → busca dueño → 3
    #    d4=2 → entrega a policía → 5
    if resp.get('d4') == 0:
        resp['d4'] = 1
    elif resp.get('d4') == 1:
        resp['d4'] = 3
    elif resp.get('d4') == 2:
        resp['d4'] = 5

    # 4. Invertir ítems reversos (escala 1-5 → 6-valor)
    for item in ITEMS_REVERSOS:
        if resp.get(item) is not None:
            resp[item] = 6 - resp[item]

    # 5. Calcular scores por bloque (escala 0-100)
    scores_bloque = {}
    for bloque, config in BLOQUES.items():
        valores = [resp[i] for i in config['items'] if resp.get(i) is not None]
        if not valores:
            scores_bloque[bloque] = None
            continue
        promedio = sum(valores) / len(valores)
        # Normalizar: (promedio - 1) / 4 * 100 → escala 0-100
        scores_bloque[bloque] = round(100 * (promedio - 1) / 4, 2)

    # 6. Score total ponderado
    score_total = 0.0
    for bloque, config in BLOQUES.items():
        if scores_bloque[bloque] is not None:
            score_total += scores_bloque[bloque] * config['peso']
    score_total = round(score_total, 2)

    # 7. Flags de validación

    # 7a. Fallos de atención (comparar con valores del registro ORIGINAL)
    fallos_atencion = sum(
        1 for campo, valor_esperado in ITEMS_ATENCION.items()
        if registro.get(campo) != valor_esperado
    )

    # 7b. Straight-lining: varianza de respuestas Likert < 0.5
    valores_likert = [registro[i] for i in LIKERT_ITEMS if registro.get(i) is not None]
    if len(valores_likert) >= 10:
        mean = sum(valores_likert) / len(valores_likert)
        varianza = sum((v - mean) ** 2 for v in valores_likert) / len(valores_likert)
    else:
        varianza = 1.0
    flag_straight_lining = 1 if varianza < 0.5 else 0

    # 7c. Inconsistencia: d2 y d3 ambos altos en el registro original
    #     d2 alto (>=4) = acepta mentirillas, d3 alto (>=4) = prefiere no engañar → contradicción
    d2_orig = registro.get('d2', 3)
    d3_orig = registro.get('d3', 3)
    flag_inconsistencia = 1 if (d2_orig >= 4 and d3_orig >= 4) else 0

    # 7d. Integridad baja: d4=0 (se queda plata) O d5=5 (muy probable prestar al primo)
    d4_orig = registro.get('d4')
    d5_orig = registro.get('d5')
    flag_integridad_baja = 1 if (d4_orig == 0 or d5_orig == 5) else 0

    # 8. Estado de validación
    if fallos_atencion >= 2:
        estado = 'invalido'
    elif fallos_atencion == 1 or flag_straight_lining or flag_inconsistencia:
        estado = 'sospechoso'
    else:
        estado = 'valido'

    # 9. Retornar resultados
    return {
        'score_total': score_total,
        'score_bloque_a': scores_bloque['a'],
        'score_bloque_b': scores_bloque['b'],
        'score_bloque_c': scores_bloque['c'],
        'score_bloque_d': scores_bloque['d'],
        'score_bloque_e': scores_bloque['e'],
        'fallos_atencion': fallos_atencion,
        'flag_straight_lining': flag_straight_lining,
        'flag_inconsistencia': flag_inconsistencia,
        'flag_integridad_baja': flag_integridad_baja,
        'estado_validacion': estado,
    }
