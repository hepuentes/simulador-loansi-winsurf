"""
Migración: Agregar campos de extracción automática a criterios_scoring_master

Nuevos campos:
- fuente_extraccion: Fuente de donde se extrae el dato (ej: midecisor_pdf, apitude_runt)
- instruccion_extraccion: Instrucción para la IA sobre qué buscar en el documento
- activo_extraccion: Si la extracción automática está activa para este criterio
"""

import sqlite3
import os
import sys

# Agregar directorio raíz al path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

DB_PATH = os.path.join(BASE_DIR, "loansi.db")


def migrar():
    """Ejecuta la migración para agregar campos de extracción."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("🔄 Iniciando migración de campos de extracción...")

        campos_nuevos = [
            ("fuente_extraccion", "TEXT", "NULL"),
            ("instruccion_extraccion", "TEXT", "NULL"),
            ("activo_extraccion", "INTEGER", "0"),
        ]

        # Verificar qué columnas ya existen
        cursor.execute("PRAGMA table_info(criterios_scoring_master)")
        columnas_existentes = {col[1] for col in cursor.fetchall()}

        agregadas = 0
        for campo, tipo, default in campos_nuevos:
            if campo not in columnas_existentes:
                cursor.execute(f"""
                    ALTER TABLE criterios_scoring_master
                    ADD COLUMN {campo} {tipo} DEFAULT {default}
                """)
                print(f"  ✅ Columna '{campo}' agregada a criterios_scoring_master")
                agregadas += 1
            else:
                print(f"  ⏭️ Columna '{campo}' ya existe, omitiendo")

        conn.commit()

        if agregadas > 0:
            print(f"\n✅ Migración completada: {agregadas} columna(s) agregada(s)")
        else:
            print("\n✅ Migración no necesaria: todas las columnas ya existían")

        return True

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error en migración: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


def verificar_migracion():
    """Verifica que la migración se aplicó correctamente."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(criterios_scoring_master)")
        columnas_existentes = {col[1] for col in cursor.fetchall()}

        campos_requeridos = {'fuente_extraccion', 'instruccion_extraccion', 'activo_extraccion'}
        faltan = campos_requeridos - columnas_existentes

        if faltan:
            print(f"❌ Faltan columnas: {faltan}")
            return False

        # Mostrar estado actual de los campos
        cursor.execute("""
            SELECT codigo, nombre, fuente_extraccion, instruccion_extraccion, activo_extraccion
            FROM criterios_scoring_master
            WHERE fuente_extraccion IS NOT NULL
            LIMIT 5
        """)
        rows = cursor.fetchall()

        if rows:
            print(f"\n📊 Criterios con extracción configurada: {len(rows)}")
            for r in rows:
                print(f"  - {r[0]} ({r[1]}): fuente={r[2]}, activo={r[4]}")
        else:
            print("\n📊 Ningún criterio tiene extracción configurada aún")

        print("✅ Migración verificada correctamente")
        return True

    finally:
        conn.close()


if __name__ == "__main__":
    migrar()
    verificar_migracion()
