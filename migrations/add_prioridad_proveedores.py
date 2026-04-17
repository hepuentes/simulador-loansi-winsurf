"""
Migración: Agregar columna 'prioridad' a ia_proveedores
========================================================
Permite establecer orden de failover entre proveedores.
prioridad = 1 es el principal, 2 es el primer fallback, etc.

Ejecutar: python migrations/add_prioridad_proveedores.py
"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "loansi.db")


def migrar():
    """Agrega columna prioridad a ia_proveedores si no existe."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Verificar si la columna ya existe
    cursor.execute("PRAGMA table_info(ia_proveedores)")
    columnas = [col[1] for col in cursor.fetchall()]

    if "prioridad" not in columnas:
        cursor.execute("ALTER TABLE ia_proveedores ADD COLUMN prioridad INTEGER DEFAULT 0")
        print("  Columna 'prioridad' agregada a ia_proveedores")

        # Asignar prioridades iniciales: activo = 1, resto = 0
        cursor.execute("UPDATE ia_proveedores SET prioridad = 1 WHERE activo = 1")
        cursor.execute("""
            UPDATE ia_proveedores SET prioridad = (
                SELECT COUNT(*) + 1 FROM ia_proveedores p2
                WHERE p2.activo = 0 AND p2.id < ia_proveedores.id
            ) + 1
            WHERE activo = 0
        """)
        print("  Prioridades iniciales asignadas")
    else:
        print("  Columna 'prioridad' ya existe")

    conn.commit()
    conn.close()
    print("Migracion completada: prioridad en ia_proveedores")


if __name__ == "__main__":
    migrar()
