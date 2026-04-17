"""
Migración: Crear tabla ia_proveedores
=====================================
Tabla para almacenar proveedores de IA configurados por el usuario.
Solo un proveedor puede estar activo a la vez.

Ejecutar: python migrations/add_ia_proveedores.py
"""

import os
import sys
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "loansi.db")


def migrar():
    """Crea la tabla ia_proveedores si no existe."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ia_proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            proveedor_tipo TEXT NOT NULL DEFAULT 'anthropic',
            modelo TEXT NOT NULL DEFAULT 'claude-haiku-4-5-20251001',
            api_key TEXT DEFAULT '',
            url_base TEXT DEFAULT '',
            activo INTEGER DEFAULT 0,
            fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Verificar si la tabla esta vacia para migrar datos existentes
    cursor.execute("SELECT COUNT(*) FROM ia_proveedores")
    count = cursor.fetchone()[0]

    if count == 0:
        # Intentar migrar datos desde configuracion_sistema (config anterior)
        try:
            cursor.execute("""
                SELECT clave, valor FROM configuracion_sistema
                WHERE clave IN ('ia_proveedor','ia_modelo','ia_api_key','ia_url_base','ia_activo')
            """)
            config = {}
            import json
            for row in cursor.fetchall():
                try:
                    config[row[0]] = json.loads(row[1])
                except (json.JSONDecodeError, TypeError):
                    config[row[0]] = row[1]

            if config.get("ia_api_key"):
                cursor.execute("""
                    INSERT INTO ia_proveedores (nombre, proveedor_tipo, modelo, api_key, url_base, activo)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    "Anthropic Claude (migrado)",
                    config.get("ia_proveedor", "anthropic"),
                    config.get("ia_modelo", "claude-haiku-4-5-20251001"),
                    config.get("ia_api_key", ""),
                    config.get("ia_url_base", "https://api.anthropic.com"),
                    1 if config.get("ia_activo") in ("1", 1) else 0
                ))
                print("  Datos migrados desde configuracion_sistema a ia_proveedores")
        except Exception as e:
            print(f"  No se pudieron migrar datos anteriores: {e}")

    conn.commit()
    conn.close()
    print("Migracion completada: tabla ia_proveedores creada")


if __name__ == "__main__":
    migrar()
