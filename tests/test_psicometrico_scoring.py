"""
Tests unitarios para el motor de scoring psicométrico.
Ejecutar con: pytest tests/test_psicometrico_scoring.py -v
"""

import sys
from pathlib import Path

# Agregar raíz del proyecto al path para importaciones
ROOT = Path(__file__).parent.parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from psicometrico.scoring_engine import calcular_scores


def _registro_base():
    """Crea un registro base con todos los campos en None."""
    campos = [
        'a1', 'a2', 'a3', 'a4', 'a5',
        'b1', 'b2', 'b3',
        'c1', 'c2', 'c3', 'c4',
        'd1', 'd2', 'd3', 'd4', 'd5',
        'e1', 'e2', 'e3',
        'atencion_1', 'atencion_2', 'atencion_3',
    ]
    return {campo: None for campo in campos}


def test_perfil_ideal_score_alto():
    """
    Perfil ideal: todas las respuestas favorables.
    Espera score_total >= 85 y estado_validacion = 'valido'.
    """
    reg = _registro_base()

    # Bloque A: Responsabilidad — todos 5 (mejor) excepto a3 que es reverso
    # a3 = "arranca proyectos y no los termina" → 1 = totalmente en desacuerdo (bueno)
    reg['a1'] = 5
    reg['a2'] = 5
    reg['a3'] = 1  # reverso: 6-1 = 5 (se convierte a bueno)
    reg['a4'] = 5
    reg['a5'] = 5

    # Bloque B: Locus de control
    # b2 = "sin suerte no sale adelante" → reverso: 1 = totalmente en desacuerdo (bueno)
    reg['b1'] = 5
    reg['b2'] = 1  # reverso: 6-1 = 5
    reg['b3'] = 5

    # Bloque C: Gratificación diferida
    reg['c1'] = 5
    reg['c2'] = 5
    reg['c3'] = 2  # paciente (espera $130k) → convertido a 5
    reg['c4'] = 5

    # Bloque D: Integridad
    # d2 = "mentirillas necesarias" → reverso: 1 = totalmente en desacuerdo (bueno)
    # d4 = situacional: 2 = entrega a policía → convertido a 5
    # d5 = "presta al primo" → reverso: 1 = nada probable (bueno) → 6-1 = 5
    reg['d1'] = 5
    reg['d2'] = 1  # reverso: 6-1 = 5
    reg['d3'] = 5
    reg['d4'] = 2  # convertido a 5
    reg['d5'] = 1  # reverso: 6-1 = 5

    # Bloque E: Estabilidad emocional
    # e1 = "preocupaste por plata" → reverso: 1 = nunca (bueno) → 6-1 = 5
    reg['e1'] = 1  # reverso: 6-1 = 5
    reg['e2'] = 5
    reg['e3'] = 5

    # Ítems de atención: respuestas correctas
    reg['atencion_1'] = 2
    reg['atencion_2'] = 4
    reg['atencion_3'] = 3

    resultado = calcular_scores(reg)

    assert resultado['score_total'] >= 85, \
        f"Score total debería ser >= 85, pero fue {resultado['score_total']}"
    assert resultado['estado_validacion'] == 'valido', \
        f"Estado debería ser 'valido', pero fue {resultado['estado_validacion']}"
    assert resultado['fallos_atencion'] == 0
    assert resultado['flag_straight_lining'] == 0
    assert resultado['flag_integridad_baja'] == 0


def test_perfil_malo_score_bajo():
    """
    Perfil malo: todas las respuestas desfavorables.
    Espera score_total <= 30.
    """
    reg = _registro_base()

    # Bloque A: Responsabilidad — todos 1 (peor) excepto a3 reverso
    # a3 = "arranca proyectos y no los termina" → 5 = totalmente de acuerdo (malo)
    reg['a1'] = 1
    reg['a2'] = 1
    reg['a3'] = 5  # reverso: 6-5 = 1 (malo)
    reg['a4'] = 1
    reg['a5'] = 1

    # Bloque B: b2 reverso → 5 = de acuerdo con "sin suerte no sale" (malo)
    reg['b1'] = 1
    reg['b2'] = 5  # reverso: 6-5 = 1
    reg['b3'] = 1

    # Bloque C
    reg['c1'] = 1
    reg['c2'] = 1
    reg['c3'] = 1  # impulsivo → convertido a 1
    reg['c4'] = 1

    # Bloque D
    reg['d1'] = 1
    reg['d2'] = 5  # reverso: 6-5 = 1 (acepta mentiras)
    reg['d3'] = 1
    reg['d4'] = 0  # se queda la plata → convertido a 1
    reg['d5'] = 5  # reverso: 6-5 = 1 (muy probable prestar)

    # Bloque E
    reg['e1'] = 5  # reverso: 6-5 = 1 (se preocupa todos los días)
    reg['e2'] = 1
    reg['e3'] = 1

    # Atención: correctas para que sea válido
    reg['atencion_1'] = 2
    reg['atencion_2'] = 4
    reg['atencion_3'] = 3

    resultado = calcular_scores(reg)

    assert resultado['score_total'] <= 30, \
        f"Score total debería ser <= 30, pero fue {resultado['score_total']}"
    assert resultado['flag_integridad_baja'] == 1, \
        "Flag integridad baja debería ser 1 (d4=0)"


def test_fallos_atencion_estado_invalido():
    """
    Perfil con 2 fallos de atención → estado_validacion = 'invalido'.
    """
    reg = _registro_base()

    # Respuestas genéricas (valor medio)
    for campo in ['a1', 'a2', 'a3', 'a4', 'a5',
                   'b1', 'b2', 'b3',
                   'c1', 'c2', 'c4',
                   'd1', 'd2', 'd3', 'd5',
                   'e1', 'e2', 'e3']:
        reg[campo] = 3

    reg['c3'] = 1  # binario
    reg['d4'] = 1  # situacional

    # 2 fallos de atención (respuestas INCORRECTAS)
    reg['atencion_1'] = 5  # esperaba 2 → FALLO
    reg['atencion_2'] = 1  # esperaba 4 → FALLO
    reg['atencion_3'] = 3  # esperaba 3 → CORRECTO

    resultado = calcular_scores(reg)

    assert resultado['fallos_atencion'] == 2, \
        f"Fallos atención debería ser 2, pero fue {resultado['fallos_atencion']}"
    assert resultado['estado_validacion'] == 'invalido', \
        f"Estado debería ser 'invalido', pero fue {resultado['estado_validacion']}"
