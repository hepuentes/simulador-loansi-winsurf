"""
Migración: Actualizar instrucciones de extracción IA para criterios
de la sección "Extracto Bancario".

Criterios actualizados (6 existentes + 1 nuevo):
  - Ingreso Promedio Mensual (ID 74)
  - Regularidad de Ingresos (ID 75)
  - Saldo Promedio Mensual (ID 76)
  - Días con Saldo en Cero o Negativo (ID 77)
  - Coherencia Ingresos vs Declarado (ID 78)
  - Pagos de Cuotas Visibles (ID 79)
  - Alertas Extracto Bancario (NUEVO - penalización)

Solo toca el campo instruccion_extraccion. No modifica peso, rangos,
ni ningún otro campo.
"""
import sqlite3
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "loansi.db")

# ═══════════════════════════════════════════════════════════════
# Instrucciones por nombre de criterio
# ═══════════════════════════════════════════════════════════════

INSTRUCCIONES = {
    "Ingreso Promedio Mensual": """Extrae el ingreso promedio mensual del extracto bancario colombiano.

PASO 1 — Identifica el tipo de banco:
  • "ESTADO DE CUENTA" + "CUENTA DE AHORROS" + columnas VALOR/SALDO → BANCOLOMBIA
  • "Extracto de depósito de bajo monto" + logo Nequi → NEQUI
  • "EXTRACTO DEPÓSITO ELECTRÓNICO" + logo MOVII → MOVII
  • "Nu Placa" + "Dinero en tus cajitas" + "Lo que entró a tu cuenta" → NU AHORRO
  • "Tu cupo definido" + "Pago mínimo" + tabla de cuotas → NU TDC
  • "Banco Falabella" + columnas CRÉDITOS/DÉBITOS/SALDOS → FALABELLA
  • Cualquier otro banco colombiano → BANCO GENÉRICO

PASO 2 — Extrae el total de ingresos según banco:

  BANCOLOMBIA:
    Lee "TOTAL ABONOS" del RESUMEN.
    Excluye líneas "ABONO INTERESES AHORROS" (son rendimientos, no ingresos).
    Ingresos reales = líneas tipo "PAGO DE PROV [EMPRESA]".
    Si el extracto cubre varios meses divide por número de meses.

  NEQUI:
    Lee "Total abonos" del Resumen.
    Excluye "RECARGA DESDE: COINK" o "RECARGA DESDE PAYPAL" si el mismo
    día hay salidas equivalentes (es tránsito de dinero, no ingreso).
    Busca el patrón recurrente mensual como ingreso real.

  MOVII:
    Lee "A tu cuenta entró".
    Excluye subsidios puntuales como "PAGO TRANSITO A RENTA CIUDADAN".

  NU AHORRO:
    Lee "Lo que entró a tu cuenta" del Resumen de movimientos.
    Excluye "Rendimiento total de tu cuenta" (son intereses).
    Si en movimientos dice "Recibiste de [mismo nombre del titular]"
    → son transferencias propias, NO son ingresos reales → retorna 0.

  NU TDC:
    No tiene ingresos. Retorna 0.

  FALABELLA:
    Lee "Total Créditos" del RESUMEN.
    Excluye "INGRESO POR INTERESES CUENTA DE AHORRO".
    Si todos los créditos son solo intereses → retorna 0
    (cuenta inactiva, no refleja ingresos reales).

  BANCO GENÉRICO:
    Busca en Resumen: "Total abonos", "Total créditos", "Total entradas".
    Si no hay resumen → suma todos los valores positivos de la columna
    de movimientos.
    Excluye líneas que contengan: "interés", "rendimiento", "reverso",
    "devolución", "reintegro".
    Divide por número de meses si cubre más de uno.

Retorna número entero en pesos. Si no se puede determinar → retorna 0.
Ejemplo: 2165000""",

    "Regularidad de Ingresos": """Analiza si el solicitante recibe ingresos de forma regular.

PASO 1 — Identifica el tipo de banco igual que en ingreso promedio.

PASO 2 — Evalúa el patrón de ingresos:

  BANCOLOMBIA:
    Busca "PAGO DE PROV [EMPRESA]" recurrente cada mes.
    Si aparece en todos los meses del extracto con montos similares
    (variación ≤15%) → Regular.

  NEQUI:
    Busca el mismo origen con montos similares cada mes.
    Si hay muchos orígenes distintos sin patrón → Irregular.

  NU AHORRO:
    Si los únicos ingresos son transferencias del mismo titular
    → Sin ingresos identificables.

  FALABELLA / cuenta inactiva:
    Si solo hay intereses y sin movimientos reales
    → Sin ingresos identificables.

  BANCO GENÉRICO:
    Busca cualquier abono recurrente del mismo origen cada mes.

PASO 3 — Determina la regularidad:
  "Regular" → mismo origen, monto similar (±15%), mismas fechas (±5 días)
  "Semi-regular" → hay ingresos cada mes pero montos varían >20%
  "Irregular" → sin patrón claro de origen ni fecha
  "Sin ingresos identificables" → solo recargas propias, intereses
    o transferencias circulares

Retorna exactamente una de estas cuatro opciones en texto.""",

    "Saldo Promedio Mensual": """Extrae el saldo promedio mensual del extracto bancario.

PASO 1 — Identifica el tipo de banco igual que en ingreso promedio.

PASO 2 — Obtén el saldo promedio según banco:

  BANCOLOMBIA:
    Lee campo "SALDO PROMEDIO" de la tabla RESUMEN → úsalo directo.

  NEQUI:
    Lee campo "Saldo promedio" de la tabla Resumen → úsalo directo.

  MOVII:
    No tiene saldo promedio explícito.
    Calcula: (Saldo Inicial + Saldo Final) / 2.

  NU AHORRO:
    Suma "Dinero en tu Cuenta Nu" + "Dinero en tus cajitas".
    Ejemplo: $1.000 + $1.002.531,15 = $1.003.531,15.

  NU TDC:
    Lee "Usado" (es deuda). Retorna ese valor como referencia
    del compromiso financiero activo.

  FALABELLA:
    Lee "Saldo Final" del RESUMEN como proxy del saldo promedio.

  BANCO GENÉRICO:
    Busca "Saldo promedio", "Saldo medio" o "Saldo final"
    en el resumen. Usa el primero que encuentres.

Retorna número entero en pesos.
Ejemplo: 2121331""",

    "Días con Saldo en Cero o Negativo": """Cuenta los días en que el saldo fue $0 o menor a $1.000.

PASO 1 — Identifica el tipo de banco igual que en ingreso promedio.

PASO 2 — Cuenta días según banco:

  BANCOLOMBIA / NEQUI:
    Recorre columna SALDO cronológicamente.
    Cuenta días ÚNICOS (no transacciones) donde el saldo
    cierra en menos de $1.000.
    Si el mismo día hay varias transacciones, cuenta ese día
    solo si el saldo al FINAL del día queda bajo $1.000.

  MOVII:
    Si "Saldo Final" = $0 exacto → retorna 30 (todo el mes en cero).
    Si no → recorre la columna "Nuevo Saldo" igual que arriba.

  NU AHORRO:
    Lee "Tu dinero al inicio del mes".
    Si es $0,00 → cuenta los días desde inicio del mes hasta
    la primera entrada de dinero como días en cero.
    Ejemplo: primera entrada el 17 feb → retorna 16 días en cero.

  NU TDC:
    No aplica para cuenta. Retorna 0.

  FALABELLA (caso cuenta inactiva con solo intereses):
    Si el saldo siempre es positivo y estable → retorna 0.

  BANCO GENÉRICO:
    Recorre la columna de saldo y cuenta días únicos
    con saldo < $1.000.

Retorna número entero de días.
Ejemplo: 2""",

    "Coherencia Ingresos vs Declarado": """Compara los ingresos del extracto con los ingresos declarados
en el campo ingresos_netos del formulario.

PASO 1 — Obtén el ingreso del extracto usando la misma lógica
que el criterio "Ingreso Promedio Mensual".

PASO 2 — Calcula la diferencia:
  diferencia = |ingreso_extracto - ingresos_netos| / ingresos_netos × 100

PASO 3 — Evalúa:
  Si diferencia ≤ 20% → retorna: "Coherente"
  Si diferencia entre 21% y 40% → retorna: "Diferencia leve"
  Si diferencia > 40% → retorna: "Diferencia significativa"

CASOS ESPECIALES:
  NU AHORRO con transferencias propias:
    Si los ingresos del extracto son transferencias del mismo titular
    → no comparar, retorna: "Coherente" (no hay dato real que contradiga)

  FALABELLA / cuenta inactiva:
    Si ingreso_extracto = 0 por ser cuenta sin movimientos reales
    → retorna: "Coherente" (no hay dato que contradiga)

  NEQUI con alto tránsito:
    Si "Total abonos" es más de 3 veces el ingresos_netos declarado
    pero "Saldo promedio" es bajo (< $300.000) → es tránsito de dinero.
    En ese caso usa saldo_promedio como proxy y recalcula la diferencia.

  BANCO GENÉRICO sin datos suficientes:
    Si no se pudo determinar el ingreso del extracto → retorna: "Coherente"

Retorna exactamente: "Coherente", "Diferencia leve" o
"Diferencia significativa" """,

    "Pagos de Cuotas Visibles": """Cuenta las cuotas de crédito activas visibles en el extracto.

PASO 1 — Identifica el tipo de banco igual que en ingreso promedio.

PASO 2 — Busca cuotas según banco:

  BANCOLOMBIA:
    Busca líneas con: "PAGO PSE [ENTIDAD FINANCIERA]",
    "PAGO DE PROV [BANCO O FINANCIERA]".
    Cada entidad diferente = 1 cuota activa.
    Ejemplos reales: "PAGO PSE NU Colombia", "PAGO PSE BANCO FALABELLA",
    "PAGO PSE CARDPAY PSP COLOMBIA".

  NEQUI:
    Busca "SISTECREDITO SAS" recurrente → 1 cuota.
    Busca "COMPRA PSE EN FIDUCIARIA" recurrente → 1 cuota.
    Busca montos idénticos al mismo destinatario en meses diferentes → 1 cuota.

  NU AHORRO:
    Cuenta dormida o nueva. Retorna 0.

  NU TDC:
    En la tabla de movimientos busca filas con formato "X de Y"
    donde Y > 1. Cada fila diferente = 1 cuota activa.
    Ejemplo: "1 de 24" = cuota vigente de 24 meses.

  FALABELLA cuenta inactiva:
    Sin movimientos reales. Retorna 0.

  BANCO GENÉRICO:
    Busca palabras clave recurrentes: "cuota", "crédito",
    "financiamiento", "pago préstamo", "débito automático".
    Cada patrón recurrente de diferente entidad = 1 cuota.

  IMPORTANTE: no contar el mismo crédito dos veces aunque
  aparezca en múltiples meses del extracto.

Retorna número entero.
Ejemplo: 3""",
}

# Instrucción para el criterio NUEVO de penalización
INSTRUCCION_ALERTAS = """Detecta señales de alerta en el extracto bancario.
Retorna TODAS las alertas encontradas separadas por " | ".
Si no hay ninguna → retorna exactamente: "Sin alertas"

ALERTA — MORA ACTIVA TDC:
  Nu TDC: si aparece "Estás tarde con tu pago" o
  "Pago mínimo atrasado" con valor > $0.
  → "Mora activa en tarjeta de crédito"

ALERTA — CUENTA NUEVA O INACTIVA:
  Nu Ahorro: si "Tu dinero al inicio del mes" = $0,00.
  Falabella: si todos los movimientos son solo intereses de centavos.
  Cualquier banco: si no hay movimientos reales en el período.
  → "Cuenta sin historial de movimientos reales"

ALERTA — TRÁFICO INUSUAL:
  Nequi u otro: si el mismo día entran y salen más de $1.000.000
  en múltiples transacciones a diferentes personas.
  → "Posible actividad de intermediación financiera"

ALERTA — SALDO FINAL CERO:
  Si Saldo Final o "Tu dinero a final del mes" = $0 exacto.
  → "Cuenta con saldo cero al cierre del período"

ALERTA — CUOTAS ALTAS vs INGRESOS:
  Si el total de cuotas mensuales identificadas supera el 40%
  del ingreso promedio encontrado en el mismo extracto.
  → "Cuotas visibles superan el 40% del ingreso estimado"

ALERTA — TRANSFERENCIAS PROPIAS COMO INGRESOS:
  Nu Ahorro: si "Recibiste de [mismo nombre del titular]".
  → "Ingresos aparentes son transferencias propias entre cuentas"

ALERTA — FORMATO NO RECONOCIDO:
  Si el banco no coincide con ningún formato conocido y no se
  pudo extraer información confiable.
  → "Formato de extracto no reconocido — revisar manualmente"

Ejemplo de retorno con múltiples alertas:
"Mora activa en tarjeta de crédito | Cuotas visibles superan el 40% del ingreso estimado" """


def ejecutar():
    """Ejecuta la migración."""
    if not os.path.exists(DB_PATH):
        print(f"ERROR: No se encontró la base de datos en {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # ──────────────────────────────────────────────
        # 1. Actualizar instrucciones de criterios existentes
        # ──────────────────────────────────────────────
        print("=" * 60)
        print("ACTUALIZANDO INSTRUCCIONES DE EXTRACCIÓN IA")
        print("Sección: Extracto Bancario")
        print("=" * 60)

        actualizados = 0
        for nombre, instruccion in INSTRUCCIONES.items():
            cursor.execute("""
                UPDATE criterios_scoring_master
                SET instruccion_extraccion = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE nombre = ?
                  AND fuente_extraccion = 'extracto_bancario'
            """, (instruccion.strip(), nombre))

            if cursor.rowcount > 0:
                print(f"  ✅ '{nombre}' — actualizado ({len(instruccion)} chars)")
                actualizados += 1
            else:
                print(f"  ⚠️  '{nombre}' — NO encontrado con fuente=extracto_bancario")

        # ──────────────────────────────────────────────
        # 2. Crear criterio "Alertas Extracto Bancario" si no existe
        # ──────────────────────────────────────────────
        cursor.execute("""
            SELECT id FROM criterios_scoring_master
            WHERE nombre = 'Alertas Extracto Bancario'
        """)
        existe_alertas = cursor.fetchone()

        if not existe_alertas:
            # Generar código único
            import time
            codigo_nuevo = f"criterio_{int(time.time() * 1000)}"

            cursor.execute("""
                INSERT INTO criterios_scoring_master
                (codigo, nombre, descripcion, tipo_campo, activo,
                 fuente_extraccion, instruccion_extraccion, activo_extraccion)
                VALUES (?, ?, ?, ?, 1, ?, ?, 1)
            """, (
                codigo_nuevo,
                "Alertas Extracto Bancario",
                "Detecta señales de alerta en el extracto bancario (criterio de penalización)",
                "select",
                "extracto_bancario",
                INSTRUCCION_ALERTAS.strip()
            ))
            nuevo_id = cursor.lastrowid
            print(f"\n  🆕 'Alertas Extracto Bancario' — CREADO (ID={nuevo_id}, codigo={codigo_nuevo})")

            # Asignar a las mismas líneas de crédito donde están los otros criterios de extracto
            cursor.execute("""
                SELECT DISTINCT linea_credito_id, seccion, seccion_icono,
                       seccion_descripcion, seccion_orden
                FROM criterios_linea_credito clc
                JOIN criterios_scoring_master csm ON csm.id = clc.criterio_master_id
                WHERE csm.fuente_extraccion = 'extracto_bancario'
            """)
            lineas = cursor.fetchall()

            for linea in lineas:
                linea_id = linea[0]
                # Verificar que no exista ya la asignación
                cursor.execute("""
                    SELECT id FROM criterios_linea_credito
                    WHERE criterio_master_id = ? AND linea_credito_id = ?
                """, (nuevo_id, linea_id))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO criterios_linea_credito
                        (criterio_master_id, linea_credito_id, peso, activo, orden,
                         seccion, seccion_icono, seccion_descripcion, seccion_orden)
                        VALUES (?, ?, 0, 1, 99, ?, ?, ?, ?)
                    """, (nuevo_id, linea_id,
                          "Sin Categoría",
                          linea[2], linea[3], linea[4]))
                    print(f"     → Asignado a línea {linea_id} (sección: Sin Categoría, peso=0)")
        else:
            # Ya existe, solo actualizar instrucción
            cursor.execute("""
                UPDATE criterios_scoring_master
                SET instruccion_extraccion = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE nombre = 'Alertas Extracto Bancario'
            """, (INSTRUCCION_ALERTAS.strip(),))
            print(f"\n  ✅ 'Alertas Extracto Bancario' — instrucción actualizada (ya existía)")

        conn.commit()

        # ──────────────────────────────────────────────
        # 3. Verificación final
        # ──────────────────────────────────────────────
        print(f"\n{'=' * 60}")
        print("VERIFICACIÓN FINAL")
        print(f"{'=' * 60}")

        cursor.execute("""
            SELECT id, nombre, LENGTH(instruccion_extraccion) as chars, activo_extraccion
            FROM criterios_scoring_master
            WHERE fuente_extraccion = 'extracto_bancario'
            ORDER BY id
        """)
        for row in cursor.fetchall():
            estado = "✅ ACTIVO" if row[3] else "❌ INACTIVO"
            print(f"  ID={row[0]} | {row[1]:<45} | {row[2]:>5} chars | {estado}")

        print(f"\n  Total criterios actualizados: {actualizados}")
        print("  Migración completada exitosamente.")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    ejecutar()
