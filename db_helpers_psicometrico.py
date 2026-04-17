"""
DB_HELPERS_PSICOMETRICO.PY - Funciones helper para el test psicométrico
========================================================================
Gestiona la tabla psicometrico_respuestas: creación, inserción,
actualización y consulta de respuestas del test psicométrico.
Usa sqlite3 puro (sin ORM).
"""

import sqlite3
import json
import secrets
from datetime import datetime
from database import conectar_db


# ============================================================================
# CREACIÓN DE TABLA
# ============================================================================

def crear_tabla_psicometrico():
    """Crea la tabla psicometrico_respuestas y sus índices si no existen."""
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS psicometrico_respuestas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                cedula TEXT,
                nombre_completo TEXT,
                telefono TEXT,
                fecha_inicio TEXT NOT NULL,
                fecha_fin TEXT,
                completado INTEGER DEFAULT 0,

                -- Bloque A: Responsabilidad (5 ítems, escala 1-5)
                a1 INTEGER, a2 INTEGER, a3 INTEGER, a4 INTEGER, a5 INTEGER,

                -- Bloque B: Locus de control (3 ítems, escala 1-5)
                b1 INTEGER, b2 INTEGER, b3 INTEGER,

                -- Bloque C: Gratificación diferida (4 ítems, escala 1-5 / C3 binario a=1 b=2)
                c1 INTEGER, c2 INTEGER, c3 INTEGER, c4 INTEGER,

                -- Bloque D: Integridad (3 ítems Likert + 2 situacionales)
                d1 INTEGER, d2 INTEGER, d3 INTEGER, d4 INTEGER, d5 INTEGER,

                -- Bloque E: Estabilidad emocional (3 ítems, escala 1-5)
                e1 INTEGER, e2 INTEGER, e3 INTEGER,

                -- Ítems de atención (esperan respuesta específica = 2)
                atencion_1 INTEGER, atencion_2 INTEGER, atencion_3 INTEGER,

                -- Latencias por ítem en milisegundos (JSON)
                latencias_json TEXT,

                -- Metadata
                user_agent TEXT,
                ip TEXT,
                canal TEXT, -- 'web', 'whatsapp_link', 'asesor'
                asesor_id INTEGER,

                -- Cálculos derivados
                score_bloque_a REAL,
                score_bloque_b REAL,
                score_bloque_c REAL,
                score_bloque_d REAL,
                score_bloque_e REAL,
                score_total REAL,
                fallos_atencion INTEGER DEFAULT 0,
                flag_straight_lining INTEGER DEFAULT 0,
                flag_inconsistencia INTEGER DEFAULT 0,
                flag_integridad_baja INTEGER DEFAULT 0,
                estado_validacion TEXT, -- 'valido', 'sospechoso', 'invalido'

                -- Vínculo con scoring posterior
                scoring_id INTEGER, -- FK a la solicitud de scoring cuando se asocie

                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_psic_token
            ON psicometrico_respuestas(token)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_psic_cedula
            ON psicometrico_respuestas(cedula)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_psic_scoring
            ON psicometrico_respuestas(scoring_id)
        """)

        conn.commit()
        print("Tabla psicometrico_respuestas e índices creados/verificados correctamente.")
    except Exception as e:
        print(f"Error al crear tabla psicometrico_respuestas: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        if conn:
            conn.close()


# ============================================================================
# GENERACIÓN DE TOKEN
# ============================================================================

def generar_token():
    """Genera un token único de 32 caracteres URL-safe."""
    return secrets.token_urlsafe(24)[:32]


# ============================================================================
# OPERACIONES CRUD
# ============================================================================

def guardar_respuesta_inicial(token, ip, user_agent, canal):
    """
    Crea el registro inicial al abrir el formulario.
    Retorna el id del registro creado.
    """
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        fecha_inicio = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO psicometrico_respuestas (token, ip, user_agent, canal, fecha_inicio)
            VALUES (?, ?, ?, ?, ?)
        """, (token, ip, user_agent, canal, fecha_inicio))

        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error al guardar respuesta inicial (token={token}): {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        if conn:
            conn.close()


def actualizar_respuestas(token, dict_respuestas, latencias_json=None):
    """
    Actualiza los campos de respuestas para un token dado.
    dict_respuestas: diccionario con claves como 'a1', 'b2', 'cedula', etc.
    latencias_json: string JSON con latencias por ítem en milisegundos.
    """
    # Columnas válidas para evitar inyección por nombre de campo
    columnas_validas = {
        'cedula', 'nombre_completo', 'telefono',
        'a1', 'a2', 'a3', 'a4', 'a5',
        'b1', 'b2', 'b3',
        'c1', 'c2', 'c3', 'c4',
        'd1', 'd2', 'd3', 'd4', 'd5',
        'e1', 'e2', 'e3',
        'atencion_1', 'atencion_2', 'atencion_3',
        'asesor_id'
    }

    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()

        # Filtrar solo columnas válidas
        campos = []
        valores = []
        for campo, valor in dict_respuestas.items():
            if campo in columnas_validas:
                campos.append(f"{campo} = ?")
                valores.append(valor)

        # Agregar latencias si se proporcionan
        if latencias_json is not None:
            campos.append("latencias_json = ?")
            valores.append(latencias_json if isinstance(latencias_json, str) else json.dumps(latencias_json))

        # Agregar updated_at
        campos.append("updated_at = ?")
        valores.append(datetime.now().isoformat())

        if not campos:
            print(f"No hay campos válidos para actualizar (token={token})")
            return False

        # Agregar token al final para el WHERE
        valores.append(token)

        sql = f"UPDATE psicometrico_respuestas SET {', '.join(campos)} WHERE token = ?"
        cursor.execute(sql, valores)
        conn.commit()

        if cursor.rowcount == 0:
            print(f"Token no encontrado para actualizar: {token}")
            return False

        return True
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error al actualizar respuestas (token={token}): {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        if conn:
            conn.close()


def marcar_completado(token):
    """
    Marca el test como completado: completado=1 y fecha_fin=now.
    Retorna True si se actualizó correctamente.
    """
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        ahora = datetime.now().isoformat()

        cursor.execute("""
            UPDATE psicometrico_respuestas
            SET completado = 1, fecha_fin = ?, updated_at = ?
            WHERE token = ?
        """, (ahora, ahora, token))

        conn.commit()

        if cursor.rowcount == 0:
            print(f"Token no encontrado para marcar completado: {token}")
            return False

        return True
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error al marcar completado (token={token}): {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        if conn:
            conn.close()


def obtener_por_token(token):
    """
    Devuelve el registro completo como dict para un token dado.
    Retorna None si no existe.
    """
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM psicometrico_respuestas WHERE token = ?",
            (token,)
        )
        row = cursor.fetchone()

        if row is None:
            return None

        return dict(row)
    except Exception as e:
        print(f"Error al obtener por token ({token}): {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        if conn:
            conn.close()


def obtener_por_cedula(cedula):
    """
    Devuelve el registro más reciente para una cédula dada.
    Retorna None si no existe.
    """
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM psicometrico_respuestas
            WHERE cedula = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (cedula,))
        row = cursor.fetchone()

        if row is None:
            return None

        return dict(row)
    except Exception as e:
        print(f"Error al obtener por cédula ({cedula}): {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        if conn:
            conn.close()


# ============================================================================
# EJECUCIÓN DIRECTA
# ============================================================================

if __name__ == '__main__':
    crear_tabla_psicometrico()
    print("Tabla psicometrico_respuestas creada/verificada.")
