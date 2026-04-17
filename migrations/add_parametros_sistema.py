"""
Migracion: Crear tabla parametros_sistema
==========================================
Tabla para almacenar parametros globales del sistema
(SMLV, subsidio transporte, porcentajes laborales, etc.)

Ejecutar: python migrations/add_parametros_sistema.py
"""

import os
import sys
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "loansi.db")


def migrar():
    """Crea la tabla parametros_sistema e inserta valores iniciales."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Crear tabla
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parametros_sistema (
            clave TEXT PRIMARY KEY,
            valor TEXT NOT NULL,
            descripcion TEXT,
            ultima_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Valores iniciales (solo insertar si no existen)
    ahora = datetime.now().isoformat()
    parametros_iniciales = [
        ("smlv", "1423500", "Salario Minimo Legal Vigente 2026", ahora),
        ("subsidio_transporte", "200000", "Auxilio de transporte 2026", ahora),
        ("pct_salud_empleado", "0.04", "Porcentaje deduccion salud empleado", ahora),
        ("pct_pension_empleado", "0.04", "Porcentaje deduccion pension empleado", ahora),
    ]

    for clave, valor, descripcion, fecha in parametros_iniciales:
        cursor.execute("""
            INSERT OR IGNORE INTO parametros_sistema (clave, valor, descripcion, ultima_actualizacion)
            VALUES (?, ?, ?, ?)
        """, (clave, valor, descripcion, fecha))

    conn.commit()
    conn.close()
    print("Migracion completada: tabla parametros_sistema creada con valores iniciales")


if __name__ == "__main__":
    migrar()
