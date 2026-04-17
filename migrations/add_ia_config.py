"""
MIGRACIÓN: Agregar configuración de IA a configuracion_sistema
================================================================
Inserta los registros iniciales para el motor de IA.
Usa INSERT OR IGNORE para no duplicar si ya existen.

Ejecutar: python migrations/add_ia_config.py
"""

import os
import sys
import sqlite3
import json

# Agregar directorio raíz al path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

DB_PATH = os.path.join(BASE_DIR, "loansi.db")


def ejecutar_migracion():
    """Inserta configuración de IA en configuracion_sistema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    registros = [
        ("ia_proveedor", json.dumps("anthropic"), "Proveedor de IA para extracción automática"),
        ("ia_modelo", json.dumps("claude-haiku-4-5-20251001"), "Modelo de IA a utilizar"),
        ("ia_api_key", json.dumps(""), "API Key del proveedor de IA"),
        ("ia_url_base", json.dumps("https://api.anthropic.com"), "URL base de la API de IA"),
        ("ia_activo", json.dumps("0"), "Extracción automática con IA activa (0/1)"),
    ]

    insertados = 0
    existentes = 0

    for clave, valor, descripcion in registros:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO configuracion_sistema
                (clave, valor, descripcion, fecha_modificacion)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (clave, valor, descripcion))

            if cursor.rowcount > 0:
                insertados += 1
                print(f"  ✅ Insertado: {clave} = {valor}")
            else:
                existentes += 1
                print(f"  ⏭️  Ya existe: {clave}")
        except Exception as e:
            print(f"  ❌ Error en {clave}: {e}")

    conn.commit()
    conn.close()

    print(f"\nResumen: {insertados} insertados, {existentes} ya existían")
    return insertados


if __name__ == "__main__":
    print("=" * 60)
    print("Migración: Configuración de IA en configuracion_sistema")
    print("=" * 60)
    ejecutar_migracion()
    print("\n✅ Migración completada")
