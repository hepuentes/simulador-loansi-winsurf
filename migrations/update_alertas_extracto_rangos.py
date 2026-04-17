"""
Migración: Agregar rangos y actualizar instrucción IA del criterio
"Alertas Extracto Bancario" (ID 80).

1. Agrega 8 rangos (opciones select con puntos de penalización)
2. Actualiza instruccion_extraccion con nueva instrucción
3. Cambia tipo_campo a 'composite' para que funcione con rangos min/max

Solo toca este criterio. No modifica ningún otro.
"""
import sqlite3
import os
import sys
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "loansi.db")

# ═══════════════════════════════════════════════════════════════
# Rangos del criterio (tipo composite: min/max = índice de opción)
# ═══════════════════════════════════════════════════════════════
RANGOS = [
    {"min": 1, "max": 1, "puntos": 0,   "descripcion": "Sin alertas"},
    {"min": 2, "max": 2, "puntos": -25, "descripcion": "Posible actividad de intermediación financiera"},
    {"min": 3, "max": 3, "puntos": -20, "descripcion": "Mora activa en tarjeta de crédito"},
    {"min": 4, "max": 4, "puntos": -15, "descripcion": "Cuenta con saldo cero al cierre del período"},
    {"min": 5, "max": 5, "puntos": -10, "descripcion": "Cuenta sin historial de movimientos reales"},
    {"min": 6, "max": 6, "puntos": -10, "descripcion": "Cuotas visibles superan el 40% del ingreso estimado"},
    {"min": 7, "max": 7, "puntos": -5,  "descripcion": "Ingresos aparentes son transferencias propias entre cuentas"},
    {"min": 8, "max": 8, "puntos": -5,  "descripcion": "Formato de extracto no reconocido — revisar manualmente"},
]

# ═══════════════════════════════════════════════════════════════
# Nueva instrucción de extracción IA
# ═══════════════════════════════════════════════════════════════
INSTRUCCION_ALERTAS = """Detecta la alerta MÁS GRAVE presente en el extracto bancario.
Retorna ÚNICAMENTE UNA opción — la de mayor severidad encontrada.

Orden de severidad (de mayor a menor):
  1. "Posible actividad de intermediación financiera"
     → Nequi u otro: mismo día entran y salen más de $1.000.000
       en múltiples transacciones a diferentes personas

  2. "Mora activa en tarjeta de crédito"
     → Nu TDC: aparece "Estás tarde con tu pago" o
       "Pago mínimo atrasado" con valor > $0

  3. "Cuenta con saldo cero al cierre del período"
     → Saldo Final o "Tu dinero a final del mes" = $0 exacto
     → MOVII: "Saldo Final" = $0

  4. "Cuenta sin historial de movimientos reales"
     → Nu Ahorro: "Tu dinero al inicio del mes" = $0,00
     → Falabella: todos los movimientos son solo intereses de centavos
     → Cualquier banco: sin movimientos reales en el período

  5. "Cuotas visibles superan el 40% del ingreso estimado"
     → El total de cuotas mensuales identificadas supera el 40%
       del ingreso promedio encontrado en el mismo extracto

  6. "Ingresos aparentes son transferencias propias entre cuentas"
     → Nu Ahorro: "Recibiste de [mismo nombre del titular]"

  7. "Formato de extracto no reconocido — revisar manualmente"
     → El banco no coincide con ningún formato conocido y no se
       pudo extraer información confiable

  8. "Sin alertas"
     → No se detectó ninguna de las alertas anteriores

Retorna EXACTAMENTE el texto de una sola opción tal como está escrito arriba."""


def ejecutar():
    """Ejecuta la migración."""
    if not os.path.exists(DB_PATH):
        print(f"ERROR: No se encontró la base de datos en {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("=" * 60)
        print("MIGRACIÓN: Alertas Extracto Bancario — rangos + instrucción")
        print("=" * 60)

        # Buscar el criterio master
        cursor.execute("""
            SELECT id, codigo, nombre, tipo_campo
            FROM criterios_scoring_master
            WHERE nombre = 'Alertas Extracto Bancario'
        """)
        master = cursor.fetchone()
        if not master:
            print("❌ ERROR: No se encontró el criterio 'Alertas Extracto Bancario'")
            sys.exit(1)

        master_id = master[0]
        print(f"  Criterio encontrado: ID={master_id}, codigo={master[1]}, tipo_campo={master[3]}")

        # ──────────────────────────────────────────────
        # 1. Actualizar tipo_campo a 'composite' e instruccion_extraccion
        # ──────────────────────────────────────────────
        cursor.execute("""
            UPDATE criterios_scoring_master
            SET tipo_campo = 'composite',
                instruccion_extraccion = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (INSTRUCCION_ALERTAS.strip(), master_id))
        print(f"  ✅ tipo_campo → 'composite'")
        print(f"  ✅ instruccion_extraccion actualizada ({len(INSTRUCCION_ALERTAS.strip())} chars)")

        # ──────────────────────────────────────────────
        # 2. Agregar rangos en criterios_linea_credito
        # ──────────────────────────────────────────────
        rangos_json = json.dumps(RANGOS, ensure_ascii=False)

        cursor.execute("""
            UPDATE criterios_linea_credito
            SET rangos_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE criterio_master_id = ?
        """, (rangos_json, master_id))

        filas_actualizadas = cursor.rowcount
        print(f"  ✅ rangos_json actualizado en {filas_actualizadas} asignación(es) de línea")

        conn.commit()

        # ──────────────────────────────────────────────
        # 3. Verificación final
        # ──────────────────────────────────────────────
        print(f"\n{'=' * 60}")
        print("VERIFICACIÓN FINAL")
        print(f"{'=' * 60}")

        cursor.execute("""
            SELECT csm.id, csm.nombre, csm.tipo_campo,
                   LENGTH(csm.instruccion_extraccion) as instr_chars,
                   clc.rangos_json, clc.linea_credito_id, clc.peso
            FROM criterios_scoring_master csm
            JOIN criterios_linea_credito clc ON csm.id = clc.criterio_master_id
            WHERE csm.id = ?
        """, (master_id,))

        for row in cursor.fetchall():
            print(f"  ID={row[0]} | {row[1]} | tipo={row[2]} | instr={row[3]} chars | linea={row[5]} | peso={row[6]}")
            rangos = json.loads(row[4])
            print(f"  Rangos ({len(rangos)}):")
            for r in rangos:
                print(f"    [{r['min']}-{r['max']}] {r['puntos']:>4} pts → {r['descripcion']}")

        print("\n  Migración completada exitosamente.")

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
