"""
Migración: Simplificar instrucciones de extracción IA para criterios select/composite.

PROBLEMA: Las instrucciones listaban manualmente las opciones del select, lo cual:
1. Duplicaba información que ya está en rangos_json de criterios_linea_credito
2. Podía desincronizarse si se cambiaban opciones desde el admin
3. Hacía los prompts innecesariamente largos

SOLUCIÓN: El sistema ahora auto-inyecta las opciones exactas desde la BD
(ver extractor_service.py → obtener_criterios_activos + construir_prompt).
Las instrucciones solo necesitan decir QUÉ buscar y DÓNDE.

NO se modifican instrucciones de criterios numéricos.
NO se cambian las opciones en sí, solo el texto de la instrucción.

Fecha: 2026-04-04
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'loansi.db')

# Mapa: id → nueva instrucción simplificada
INSTRUCCIONES_SIMPLIFICADAS = {

    # ── MiDecisor PDF ──────────────────────────────────────────────

    47: (
        "criterio_1753284665359",
        "Tipo de Empleo",
        "Determinar el tipo de empleo o vinculación laboral del solicitante "
        "a partir del soporte de ingresos (nómina, certificado laboral o desprendible de pago). "
        "Identificar si es empleado formal con contrato indefinido, a término fijo, "
        "independiente con o sin verificación documental, o desempleado."
    ),

    46: (
        "criterio_1753284563966",
        "Consultas DataCrédito últimos 60 días",
        "En la sección 'Escaneo preventivo' o 'RESULTADO ESCANEO' del reporte MiDecisor, "
        "buscar si menciona consultas de diferentes entidades en los últimos 60 días. "
        "Si NO menciona nada sobre consultas, significa que hay menos de 3."
    ),

    48: (
        "criterio_1770482988658",
        "Viabilidad MiDecisor",
        "En la parte superior del reporte MiDecisor, buscar la viabilidad asignada. "
        "Aparece claramente como texto en mayúsculas (ALTA, MEDIA o BAJA)."
    ),

    52: (
        "criterio_1770494915836",
        "Moras ≥60 días, últimos 6 meses",
        "En la sección 'Escaneo preventivo' del reporte MiDecisor, buscar si el texto "
        "del RESULTADO DEL ESCANEO menciona moras de 60 días o más en los últimos 6 meses."
    ),

    53: (
        "criterio_1770495240743",
        "3 nuevas direcciones o más en los últimos 12 meses",
        "En la sección 'Escaneo preventivo' o 'RESULTADO ESCANEO' del reporte MiDecisor, "
        "buscar si menciona cambios de dirección (3 o más nuevas direcciones) en los últimos 12 meses. "
        "Si el escaneo no menciona nada sobre direcciones, significa que no hay alerta."
    ),

    54: (
        "criterio_1770495908652",
        "Suplantación ID detectada",
        "En la sección 'Escaneo preventivo' del reporte MiDecisor, buscar alertas de "
        "suplantación de identidad asociadas al número de documento. "
        "Si dice 'No se encuentran coincidencias' o 'Sin alertas', significa SIN alerta."
    ),

    55: (
        "criterio_1770496027200",
        "Listas restrictivas SARLAFT",
        "En el escaneo preventivo del reporte MiDecisor, verificar si el número de documento "
        "(cédula) aparece en listas restrictivas: SARLAFT, OFAC, ONU, listas negras. "
        "Ignorar coincidencias solo por nombre sin restricción por número de documento."
    ),

    56: (
        "criterio_1770496114423",
        "Cartera castigada activa",
        "En la sección de comportamiento de pago del reporte MiDecisor, revisar los círculos "
        "de los 12 meses. El código 'C' significa 'Cartera castigada'. "
        "Si hay al menos un círculo con la letra C en cualquiera de los 12 meses, hay cartera castigada."
    ),

    68: (
        "criterio_1771111580296",
        "Validación Documento Identidad, Estado",
        "En el encabezado del reporte MiDecisor o sección de datos personales, "
        "buscar el estado del documento de identidad (cédula): si está vigente, "
        "cancelada, anulada, en trámite o suspendida."
    ),

    # ── Soporte de Ingresos (Nómina) ──────────────────────────────

    58: (
        "criterio_1770763566060",
        "Validación ADRES (régimen salud)",
        "Revisar las deducciones del comprobante de nómina o certificación laboral. "
        "Determinar el régimen de salud del solicitante: si es cotizante dependiente "
        "(empleado formal), cotizante independiente, beneficiario, régimen subsidiado o inactivo. "
        "Buscar la EPS y si la deducción de salud del empleado tiene valor > 0."
    ),

    81: (
        "criterio_1772826714678",
        "Ingreso Documentado vs Declarado",
        "Comparar el ingreso que muestra el documento (nómina, certificado laboral) "
        "con el ingreso declarado por el solicitante. Determinar si son coherentes "
        "(±10%), tienen diferencia leve (10-30%), diferencia significativa (>30%), "
        "o si el documento no permite verificar el ingreso."
    ),

    82: (
        "criterio_1772826886471",
        "Calidad Soporte de Ingresos",
        "Evaluar la calidad y confiabilidad del soporte de ingresos presentado. "
        "Considerar si es de empresa reconocida con detalle completo, si tiene "
        "información básica pero verificable, si tiene datos incompletos, o si presenta "
        "señales sospechosas como logos borrosos o información inconsistente."
    ),

    # ── Extracto Bancario ─────────────────────────────────────────

    75: (
        "criterio_1772741164600",
        "Regularidad de Ingresos",
        "Analizar los depósitos o abonos recurrentes en el extracto bancario de los últimos 3 meses. "
        "Determinar si el ingreso llega de forma regular (mismo día cada mes), semi-regular "
        "(varía pocos días), irregular (sin patrón claro), o si no se detectan ingresos recurrentes."
    ),

    78: (
        "criterio_1772741782689",
        "Coherencia Ingresos vs Declarado",
        "Comparar los ingresos que muestra el extracto bancario (depósitos recurrentes) "
        "con el ingreso declarado por el solicitante. Determinar si el extracto confirma "
        "el ingreso declarado, si hay diferencia leve o significativa, o si no se puede comparar."
    ),

    80: (
        "criterio_1772750519468",
        "Alertas Extracto Bancario",
        "Detectar la alerta más grave del extracto bancario. Buscar señales como: "
        "depósitos fraccionados sospechosos, retiros inmediatos después de depósitos, "
        "transferencias a casas de apuestas, sobregiros frecuentes, o movimientos inusuales. "
        "Si no hay alertas, indicar que el extracto está limpio."
    ),

    # ── Recibo de Servicios Públicos ──────────────────────────────

    83: (
        "criterio_1774566442464",
        "Estrato Socioeconómico",
        "Buscar el número de estrato socioeconómico en el recibo de servicios públicos "
        "colombiano (luz, agua o gas). El estrato aparece como número del 1 al 6. "
        "Buscarlo cerca de las palabras 'Estrato', 'EST', 'Clase de servicio' o 'Categoría'."
    ),

    86: (
        "criterio_1774566901443",
        "Estado Pago Servicios Públicos",
        "Analizar el recibo de servicios públicos colombiano. Determinar si el servicio "
        "está al día o tiene deuda. Buscar campos como 'SALDO ANTERIOR', 'Facturas vencidas', "
        "'RECONEXIÓN', 'SUSPENSIÓN', o 'Último pago realizado' para determinar el estado."
    ),

    # ── Certificado Seguridad Social ──────────────────────────────

    84: (
        "criterio_1774566625270",
        "Verificación Empleo Formal (certificado SS)",
        "Analizar el documento de seguridad social colombiano (certificado de aportes, "
        "certificado de EPS, certificado de fondo de pensión o certificado de cesantías). "
        "Determinar si confirma empleo formal activo, si hay periodos atrasados, "
        "si el régimen es subsidiado (sin empleo formal), o si es régimen especial."
    ),

    88: (
        "criterio_1774969287925",
        "Coherencia RUAF vs Documentos Aportados",
        "Analizar el documento RUAF (Registro Único de Afiliados) del sistema SISPRO. "
        "Verificar el estado de cada subsistema: Salud, Pensiones, Riesgos Laborales, "
        "Compensación Familiar y Cesantías. Determinar si los subsistemas están activos "
        "y son coherentes con empleo formal, o si hay inconsistencias como salud subsidiada "
        "con nómina que muestra empleo formal."
    ),

    # ── Planilla PILA ─────────────────────────────────────────────

    85: (
        "criterio_1774566779608",
        "Coherencia IBC vs Salario",
        "Analizar la planilla PILA colombiana. Extraer el IBC (Ingreso Base de Cotización) "
        "del periodo más reciente. Comparar con el ingreso declarado por el solicitante "
        "para determinar si son coherentes (±10%), difieren levemente (10-20%) o significativamente (>20%)."
    ),

    87: (
        "criterio_1774913580599",
        "Verificación Empresa Aportante (PILA)",
        "Analizar el certificado de aportes de seguridad social (Aportes en Línea). "
        "Si es certificado de aportes, verificar: si tiene las 4 cotizaciones (EPS, AFP, ARL, CCF), "
        "si el periodo más reciente es actual, y si dice 'COTIZACIÓN OBLIGATORIA' y 'PAGADA'. "
        "Si no es certificado de aportes (es certificado de EPS o pensión), indicarlo."
    ),
}


def ejecutar():
    """Ejecuta la migración"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 60)
    print("MIGRACIÓN: Simplificar instrucciones de extracción IA")
    print("=" * 60)

    actualizados = 0
    errores = 0

    for criterio_id, (codigo, nombre, nueva_instruccion) in INSTRUCCIONES_SIMPLIFICADAS.items():
        # Verificar que el criterio existe y tiene el codigo esperado
        cursor.execute(
            "SELECT id, codigo, nombre, instruccion_extraccion FROM criterios_scoring_master WHERE id = ?",
            (criterio_id,)
        )
        row = cursor.fetchone()

        if not row:
            print(f"  ⚠️  ID={criterio_id} ({codigo}) — NO ENCONTRADO en BD")
            errores += 1
            continue

        if row['codigo'] != codigo:
            print(f"  ⚠️  ID={criterio_id} — Código esperado '{codigo}', encontrado '{row['codigo']}'")
            errores += 1
            continue

        # Mostrar cambio
        instr_actual = row['instruccion_extraccion'] or ''
        print(f"\n  [{criterio_id}] {nombre}")
        print(f"    Antes: {len(instr_actual)} chars")
        print(f"    Ahora: {len(nueva_instruccion)} chars")

        # Actualizar
        cursor.execute(
            "UPDATE criterios_scoring_master SET instruccion_extraccion = ? WHERE id = ?",
            (nueva_instruccion, criterio_id)
        )
        actualizados += 1

    conn.commit()
    conn.close()

    print(f"\n{'=' * 60}")
    print(f"RESULTADO: {actualizados} instrucciones actualizadas, {errores} errores")
    print(f"{'=' * 60}")

    return actualizados, errores


if __name__ == "__main__":
    ejecutar()
