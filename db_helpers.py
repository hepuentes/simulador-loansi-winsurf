"""
DB_HELPERS.PY - Funciones Helper para SQLite
=================================================================

Este archivo contiene funciones que reemplazan las funciones JSON
en flask_app.py. Mantiene la misma API para minimizar cambios.

"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from database import conectar_db, DB_PATH


# ============================================================================
# FUNCIONES DE CONFIGURACIÓN (reemplazan cargar_configuracion())
# ============================================================================


def cargar_configuracion():
    """
    Carga configuración completa desde SQLite.
    Reemplaza la función que leía config.json.

    Returns:
        dict: Configuración en el mismo formato que config.json
    """
    conn = conectar_db()
    cursor = conn.cursor()

    config = {}

    # 1. Cargar líneas de crédito
    cursor.execute(
        """
        SELECT nombre, descripcion, monto_min, monto_max,
               plazo_min, plazo_max, tasa_mensual, tasa_anual,
               aval_porcentaje, plazo_tipo, permite_desembolso_neto,
               desembolso_por_defecto
        FROM lineas_credito
        WHERE activo = 1
        ORDER BY orden ASC, nombre ASC
    """
    )

    lineas = {}
    for row in cursor.fetchall():
        nombre = row[0]
        lineas[nombre] = {
            "descripcion": row[1],
            "monto_min": row[2],
            "monto_max": row[3],
            "plazo_min": row[4],
            "plazo_max": row[5],
            "tasa_mensual": row[6],
            "tasa_anual": row[7],
            "aval_porcentaje": row[8],
            "plazo_tipo": row[9],
            "permite_desembolso_neto": bool(row[10]),
            "desembolso_por_defecto": row[11],
        }

    config["LINEAS_CREDITO"] = lineas

    # 2. Cargar costos asociados
    cursor.execute(
        """
        SELECT lc.nombre, ca.nombre_costo, ca.valor
        FROM costos_asociados ca
        JOIN lineas_credito lc ON ca.linea_credito_id = lc.id
        WHERE ca.activo = 1 AND lc.activo = 1
        ORDER BY lc.orden ASC, lc.nombre ASC
    """
    )

    costos = {}
    for row in cursor.fetchall():
        linea_nombre = row[0]
        nombre_costo = row[1]
        valor = row[2]

        if linea_nombre not in costos:
            costos[linea_nombre] = {}
        costos[linea_nombre][nombre_costo] = valor

    config["COSTOS_ASOCIADOS"] = costos

    # 3. Cargar parámetros de capacidad de pago
    cursor.execute(
        """
        SELECT valor FROM configuracion_sistema
        WHERE clave = 'PARAMETROS_CAPACIDAD_PAGO'
    """
    )
    row = cursor.fetchone()
    if row:
        config["PARAMETROS_CAPACIDAD_PAGO"] = json.loads(row[0])

    # 4. Cargar configuración de comité
    cursor.execute(
        """
        SELECT valor FROM configuracion_sistema
        WHERE clave = 'COMITE_CREDITO'
    """
    )
    row = cursor.fetchone()
    if row:
        config["COMITE_CREDITO"] = json.loads(row[0])

    # 5. Cargar usuarios (incluye nombre_completo)
    cursor.execute(
        """
        SELECT username, password_hash, rol, nombre_completo
        FROM usuarios
        WHERE activo = 1
    """
    )

    usuarios = {}
    for row in cursor.fetchall():
        username = row[0]
        usuarios[username] = {
            "password_hash": row[1],
            "rol": row[2],
            "nombre_completo": row[3] or "",
        }

    config["USUARIOS"] = usuarios

    # 6. Cargar configuración de seguros (AGREGADO 2025-12-19)
    cursor.execute(
        """
        SELECT valor FROM configuracion_sistema
        WHERE clave = 'SEGUROS'
    """
    )
    row = cursor.fetchone()
    if row:
        try:
            config["SEGUROS"] = json.loads(row[0])
        except:
            pass

    conn.close()
    return config


def guardar_configuracion(config):
    """
    Guarda configuración completa en SQLite.
    Reemplaza la función que escribía config.json.

    CORREGIDO 2025-12-19: Ahora usa INSERT para líneas nuevas
    y guarda COSTOS_ASOCIADOS y SEGUROS correctamente.

    Args:
        config (dict): Configuración completa
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        # 1. LÍNEAS DE CRÉDITO - INSERT o UPDATE
        if "LINEAS_CREDITO" in config:
            for nombre, datos in config["LINEAS_CREDITO"].items():
                # Verificar si existe
                cursor.execute(
                    "SELECT id FROM lineas_credito WHERE nombre = ?", (nombre,)
                )
                existe = cursor.fetchone()

                if existe:
                    # UPDATE si existe
                    cursor.execute(
                        """
                        UPDATE lineas_credito
                        SET descripcion = ?,
                            monto_min = ?,
                            monto_max = ?,
                            plazo_min = ?,
                            plazo_max = ?,
                            tasa_mensual = ?,
                            tasa_anual = ?,
                            aval_porcentaje = ?,
                            plazo_tipo = ?,
                            permite_desembolso_neto = ?,
                            desembolso_por_defecto = ?,
                            fecha_modificacion = CURRENT_TIMESTAMP
                        WHERE nombre = ?
                    """,
                        (
                            datos.get("descripcion", ""),
                            datos.get("monto_min", 0),
                            datos.get("monto_max", 0),
                            datos.get("plazo_min", 1),
                            datos.get("plazo_max", 12),
                            datos.get("tasa_mensual", 0),
                            datos.get("tasa_anual", 0),
                            datos.get("aval_porcentaje", 0.0),
                            datos.get("plazo_tipo", "meses"),
                            1 if datos.get("permite_desembolso_neto", True) else 0,
                            datos.get("desembolso_por_defecto", "completo"),
                            nombre,
                        ),
                    )
                    print(f"✅ Línea '{nombre}' actualizada en SQLite")
                else:
                    # INSERT si no existe
                    cursor.execute(
                        """
                        INSERT INTO lineas_credito
                        (nombre, descripcion, monto_min, monto_max, plazo_min, plazo_max,
                         tasa_mensual, tasa_anual, aval_porcentaje, plazo_tipo,
                         permite_desembolso_neto, desembolso_por_defecto, activo,
                         fecha_creacion, fecha_modificacion)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                        (
                            nombre,
                            datos.get("descripcion", ""),
                            datos.get("monto_min", 0),
                            datos.get("monto_max", 0),
                            datos.get("plazo_min", 1),
                            datos.get("plazo_max", 12),
                            datos.get("tasa_mensual", 0),
                            datos.get("tasa_anual", 0),
                            datos.get("aval_porcentaje", 0.0),
                            datos.get("plazo_tipo", "meses"),
                            1 if datos.get("permite_desembolso_neto", True) else 0,
                            datos.get("desembolso_por_defecto", "completo"),
                        ),
                    )
                    print(f"✅ Línea '{nombre}' INSERTADA en SQLite (nueva)")

        # 2. COSTOS ASOCIADOS - DELETE + INSERT (CORREGIDO 2025-12-24)
        # Se eliminan TODOS los costos existentes y se insertan los nuevos
        # Esto permite que las eliminaciones desde el frontend persistan
        if "COSTOS_ASOCIADOS" in config:
            for linea_nombre, costos in config["COSTOS_ASOCIADOS"].items():
                # Obtener ID de la línea
                cursor.execute(
                    "SELECT id FROM lineas_credito WHERE nombre = ?", (linea_nombre,)
                )
                linea_row = cursor.fetchone()

                if linea_row:
                    linea_id = linea_row[0]

                    # CRÍTICO: Eliminar TODOS los costos existentes de esta línea
                    cursor.execute(
                        """
                        DELETE FROM costos_asociados
                        WHERE linea_credito_id = ?
                    """,
                        (linea_id,),
                    )

                    # Insertar los costos que vienen del formulario
                    for nombre_costo, valor in costos.items():
                        cursor.execute(
                            """
                            INSERT INTO costos_asociados
                            (linea_credito_id, nombre_costo, valor, activo, fecha_creacion)
                            VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                        """,
                            (linea_id, nombre_costo, valor),
                        )

                    print(
                        f"✅ Costos de '{linea_nombre}' guardados ({len(costos)} costos)"
                    )

        # 3. SEGUROS - Guardar en configuracion_sistema
        if "SEGUROS" in config:
            seguros_json = json.dumps(config["SEGUROS"], ensure_ascii=False)
            cursor.execute(
                """
                INSERT OR REPLACE INTO configuracion_sistema
                (clave, valor, descripcion, fecha_modificacion)
                VALUES ('SEGUROS', ?, 'Configuración de seguros', CURRENT_TIMESTAMP)
            """,
                (seguros_json,),
            )
            print(f"✅ Configuración de seguros guardada")

        # 4. Parámetros de capacidad de pago
        if "PARAMETROS_CAPACIDAD_PAGO" in config:
            cursor.execute(
                """
                INSERT OR REPLACE INTO configuracion_sistema
                (clave, valor, descripcion, fecha_modificacion)
                VALUES ('PARAMETROS_CAPACIDAD_PAGO', ?, 'Parámetros capacidad pago', CURRENT_TIMESTAMP)
            """,
                (json.dumps(config["PARAMETROS_CAPACIDAD_PAGO"]),),
            )

        # 5. Configuración de comité
        if "COMITE_CREDITO" in config:
            cursor.execute(
                """
                INSERT OR REPLACE INTO configuracion_sistema
                (clave, valor, descripcion, fecha_modificacion)
                VALUES ('COMITE_CREDITO', ?, 'Configuración comité', CURRENT_TIMESTAMP)
            """,
                (json.dumps(config["COMITE_CREDITO"]),),
            )

        # 6. USUARIOS - INSERT o UPDATE cada usuario
        if "USUARIOS" in config:
            for username, datos in config["USUARIOS"].items():
                cursor.execute(
                    "SELECT id FROM usuarios WHERE username = ?", (username,)
                )
                existe = cursor.fetchone()

                if existe:
                    # UPDATE si existe - INCLUYE nombre_completo
                    cursor.execute(
                        """
                        UPDATE usuarios
                        SET password_hash = ?,
                            rol = ?,
                            nombre_completo = ?,
                            fecha_modificacion = CURRENT_TIMESTAMP
                        WHERE username = ?
                    """,
                        (
                            datos.get("password_hash", ""),
                            datos.get("rol", "asesor"),
                            datos.get("nombre_completo", ""),
                            username,
                        ),
                    )
                else:
                    # INSERT si no existe - INCLUYE nombre_completo
                    cursor.execute(
                        """
                        INSERT INTO usuarios (username, password_hash, rol, nombre_completo, activo, fecha_creacion, fecha_modificacion)
                        VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                        (
                            username,
                            datos.get("password_hash", ""),
                            datos.get("rol", "asesor"),
                            datos.get("nombre_completo", ""),
                        ),
                    )
                    print(
                        f"✅ Usuario '{username}' ({datos.get('nombre_completo', '')}) INSERTADO en SQLite"
                    )

        conn.commit()
        print("✅ Configuración completa guardada en SQLite")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error guardando configuración: {e}")
        raise e
    finally:
        conn.close()


# ============================================================================
# FUNCIONES DE RENOMBRADO DE LÍNEAS DE CRÉDITO (AGREGADA 2026-02-09)
# ============================================================================


def renombrar_linea_credito_db(nombre_original, nombre_nuevo):
    """
    Renombra una línea de crédito en la BD preservando su ID y todas las FK.
    
    Esto asegura que scoring, comité, costos y demás configuraciones
    vinculadas por linea_credito_id se mantengan intactas.
    
    NOTA: Se desactiva PRAGMA foreign_keys temporalmente porque la tabla
    simulaciones tiene FK a lineas_credito.nombre con ON UPDATE NO ACTION,
    lo que bloquea el UPDATE del nombre si hay simulaciones referenciándolo.

    Args:
        nombre_original (str): Nombre actual de la línea
        nombre_nuevo (str): Nuevo nombre para la línea

    Returns:
        bool: True si se renombró exitosamente
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        # Verificar que la línea original existe y está activa
        cursor.execute(
            "SELECT id FROM lineas_credito WHERE nombre = ? AND activo = 1",
            (nombre_original,),
        )
        linea = cursor.fetchone()

        if not linea:
            print(f"⚠️ Línea '{nombre_original}' no encontrada para renombrar")
            return False

        linea_id = linea[0]

        # Verificar que el nuevo nombre no exista ya
        cursor.execute(
            "SELECT id FROM lineas_credito WHERE nombre = ? AND id != ?",
            (nombre_nuevo, linea_id),
        )
        if cursor.fetchone():
            print(f"⚠️ Ya existe otra línea con nombre '{nombre_nuevo}'")
            return False

        # Desactivar FK temporalmente para evitar bloqueo por
        # simulaciones.linea_credito -> lineas_credito.nombre (ON UPDATE NO ACTION)
        cursor.execute("PRAGMA foreign_keys = OFF")

        # 1. Actualizar PRIMERO las tablas hijas que referencian por nombre (TEXT)
        cursor.execute(
            "UPDATE simulaciones SET linea_credito = ? WHERE linea_credito = ?",
            (nombre_nuevo, nombre_original),
        )

        cursor.execute(
            "UPDATE configuracion_scoring SET linea_credito = ? WHERE linea_credito = ?",
            (nombre_nuevo, nombre_original),
        )

        cursor.execute(
            "UPDATE evaluaciones SET linea_credito = ? WHERE linea_credito = ?",
            (nombre_nuevo, nombre_original),
        )

        # 2. Renombrar la línea de crédito (preserva ID y todas las FK por id)
        cursor.execute(
            """UPDATE lineas_credito 
               SET nombre = ?, fecha_modificacion = CURRENT_TIMESTAMP 
               WHERE id = ?""",
            (nombre_nuevo, linea_id),
        )

        conn.commit()

        # Reactivar FK después del commit
        cursor.execute("PRAGMA foreign_keys = ON")

        print(f"✅ Línea renombrada: '{nombre_original}' → '{nombre_nuevo}' (ID: {linea_id})")
        print(f"   - Scoring, comité, costos y demás vínculos preservados por FK")
        print(f"   - Tablas TEXT actualizadas: simulaciones, configuracion_scoring, evaluaciones")
        return True

    except Exception as e:
        conn.rollback()
        # Reactivar FK en caso de error
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass
        print(f"❌ Error al renombrar línea: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


# ============================================================================
# FUNCIONES DE ELIMINACIÓN DE LÍNEAS DE CRÉDITO (AGREGADAS 2025-12-23)
# ============================================================================


def eliminar_linea_credito_db(nombre_linea):
    """
    Elimina (soft delete) una línea de crédito de la base de datos.

    CORRECCIÓN BUG #2: Esta función es necesaria porque guardar_configuracion()
    solo hace INSERT/UPDATE, nunca DELETE. Sin esta función, las líneas
    "eliminadas" del diccionario en memoria nunca se eliminan de la DB
    y reaparecen al recargar la página.

    Args:
        nombre_linea (str): Nombre de la línea a eliminar

    Returns:
        bool: True si se eliminó exitosamente
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        # Verificar que la línea existe
        cursor.execute(
            "SELECT id FROM lineas_credito WHERE nombre = ? AND activo = 1",
            (nombre_linea,),
        )
        linea = cursor.fetchone()

        if not linea:
            print(f"⚠️ Línea '{nombre_linea}' no encontrada o ya está inactiva")
            return False

        linea_id = linea[0]

        # Soft delete: marcar como inactiva (no eliminar físicamente)
        # Esto preserva integridad referencial con evaluaciones históricas
        cursor.execute(
            """
            UPDATE lineas_credito
            SET activo = 0,
                fecha_modificacion = CURRENT_TIMESTAMP
            WHERE nombre = ?
        """,
            (nombre_linea,),
        )

        # También desactivar costos asociados
        cursor.execute(
            """
            UPDATE costos_asociados
            SET activo = 0
            WHERE linea_credito_id = ?
        """,
            (linea_id,),
        )

        conn.commit()
        print(
            f"✅ Línea '{nombre_linea}' marcada como inactiva en SQLite (soft delete)"
        )
        print(f"   - Línea ID: {linea_id}")
        print(f"   - Costos asociados también desactivados")
        return True

    except Exception as e:
        conn.rollback()
        print(f"❌ Error al eliminar línea de crédito: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        conn.close()


def reactivar_linea_credito_db(nombre_linea):
    """
    Reactiva una línea de crédito previamente eliminada (soft delete).

    Útil para recuperar líneas eliminadas por error.

    Args:
        nombre_linea (str): Nombre de la línea a reactivar

    Returns:
        bool: True si se reactivó exitosamente
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        # Verificar que la línea existe pero está inactiva
        cursor.execute(
            "SELECT id FROM lineas_credito WHERE nombre = ? AND activo = 0",
            (nombre_linea,),
        )
        linea = cursor.fetchone()

        if not linea:
            print(f"⚠️ Línea '{nombre_linea}' no encontrada o ya está activa")
            return False

        linea_id = linea[0]

        # Reactivar línea
        cursor.execute(
            """
            UPDATE lineas_credito
            SET activo = 1,
                fecha_modificacion = CURRENT_TIMESTAMP
            WHERE nombre = ?
        """,
            (nombre_linea,),
        )

        # Reactivar costos asociados
        cursor.execute(
            """
            UPDATE costos_asociados
            SET activo = 1
            WHERE linea_credito_id = ?
        """,
            (linea_id,),
        )

        conn.commit()
        print(f"✅ Línea '{nombre_linea}' reactivada en SQLite")
        return True

    except Exception as e:
        conn.rollback()
        print(f"❌ Error al reactivar línea: {e}")
        return False
    finally:
        conn.close()


def listar_lineas_eliminadas():
    """
    Lista todas las líneas de crédito eliminadas (inactivas).

    Returns:
        list: Lista de diccionarios con líneas inactivas
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT nombre, descripcion, fecha_modificacion
            FROM lineas_credito
            WHERE activo = 0
            ORDER BY fecha_modificacion DESC
        """
        )

        lineas = []
        for row in cursor.fetchall():
            lineas.append(
                {"nombre": row[0], "descripcion": row[1], "fecha_eliminacion": row[2]}
            )

        return lineas

    except Exception as e:
        print(f"❌ Error al listar líneas eliminadas: {e}")
        return []
    finally:
        conn.close()


# ============================================================================
# FUNCIONES DE SCORING (CORREGIDAS 2025-12-18)
# ============================================================================


def cargar_scoring():
    """
    Carga configuración COMPLETA de scoring desde SQLite.
    Reemplaza la función que leía scoring.json.

    IMPORTANTE: Esta función retorna la MISMA estructura que scoring.json
    para mantener compatibilidad con el frontend.

    Estructura retornada:
    {
        'criterios': {...},                    # 21 criterios de scoring
        'niveles_riesgo': [...],               # 3 niveles con tasas
        'factores_rechazo_automatico': [...],  # 16 factores
        'puntaje_minimo_aprobacion': int,
        'umbral_mora_telcos_rechazo': int,
        'configuracion_por_linea': {...},
        'tabla_dane_2025': {...},
        'ponderaciones_sectoriales': {...},
        'escala_max': int
    }

    Returns:
        dict: Configuración de scoring completa
    """
    conn = conectar_db()
    cursor = conn.cursor()

    scoring = {}

    try:
        # =========================================================
        # 1. CARGAR CRITERIOS (criterios)
        # =========================================================
        cursor.execute(
            """
            SELECT valor FROM configuracion_sistema
            WHERE clave = 'CRITERIOS_SCORING'
        """
        )
        row = cursor.fetchone()
        if row:
            criterios_raw = json.loads(row[0])
            # CORRECCIÓN 2025-12-25: Ordenar criterios por campo 'orden'
            criterios_items = list(criterios_raw.items())
            criterios_items.sort(key=lambda x: x[1].get("orden", 9999))
            scoring["criterios"] = dict(criterios_items)
            print(
                f"✅ cargar_scoring: {len(scoring['criterios'])} criterios cargados y ordenados"
            )
        else:
            scoring["criterios"] = {}
            print("⚠️ cargar_scoring: No se encontraron criterios en SQLite")

        # =========================================================
        # 2. CARGAR NIVELES DE RIESGO (CRÍTICO para tasas)
        # =========================================================
        cursor.execute(
            """
            SELECT valor FROM configuracion_sistema
            WHERE clave = 'NIVELES_RIESGO'
        """
        )
        row = cursor.fetchone()
        if row:
            scoring["niveles_riesgo"] = json.loads(row[0])
        else:
            # Valores por defecto si no existe
            scoring["niveles_riesgo"] = [
                {"nombre": "Alto riesgo", "min": 0, "max": 30, "color": "#FF4136"},
                {
                    "nombre": "Riesgo moderado",
                    "min": 30.1,
                    "max": 70,
                    "color": "#FFDC00",
                },
                {"nombre": "Bajo riesgo", "min": 70.1, "max": 100, "color": "#2ECC40"},
            ]
            print("⚠️ cargar_scoring: Usando niveles_riesgo por defecto")

        # =========================================================
        # 3. CARGAR FACTORES DE RECHAZO AUTOMÁTICO
        # =========================================================
        cursor.execute(
            """
            SELECT valor FROM configuracion_sistema
            WHERE clave = 'FACTORES_RECHAZO'
        """
        )
        row = cursor.fetchone()
        if row:
            scoring["factores_rechazo_automatico"] = json.loads(row[0])
        else:
            scoring["factores_rechazo_automatico"] = []
            print("⚠️ cargar_scoring: No se encontraron factores de rechazo")

        # =========================================================
        # 4. CARGAR PUNTAJE MÍNIMO DE APROBACIÓN
        # =========================================================
        cursor.execute(
            """
            SELECT valor FROM configuracion_sistema
            WHERE clave = 'PUNTAJE_MINIMO_APROBACION'
        """
        )
        row = cursor.fetchone()
        if row:
            scoring["puntaje_minimo_aprobacion"] = json.loads(row[0])
        else:
            scoring["puntaje_minimo_aprobacion"] = 17  # Valor por defecto

        # =========================================================
        # 5. CARGAR UMBRAL MORA TELCOS
        # =========================================================
        cursor.execute(
            """
            SELECT valor FROM configuracion_sistema
            WHERE clave = 'UMBRAL_MORA_TELCOS'
        """
        )
        row = cursor.fetchone()
        if row:
            scoring["umbral_mora_telcos_rechazo"] = json.loads(row[0])
        else:
            scoring["umbral_mora_telcos_rechazo"] = 200000  # Valor por defecto

        # =========================================================
        # 6. CARGAR TABLA DANE 2025
        # =========================================================
        cursor.execute(
            """
            SELECT valor FROM configuracion_sistema
            WHERE clave = 'TABLA_DANE_2025'
        """
        )
        row = cursor.fetchone()
        if row:
            scoring["tabla_dane_2025"] = json.loads(row[0])
        else:
            scoring["tabla_dane_2025"] = {}

        # =========================================================
        # 7. CARGAR PONDERACIONES SECTORIALES
        # =========================================================
        cursor.execute(
            """
            SELECT valor FROM configuracion_sistema
            WHERE clave = 'PONDERACIONES_SECTORIALES'
        """
        )
        row = cursor.fetchone()
        if row:
            scoring["ponderaciones_sectoriales"] = json.loads(row[0])
        else:
            scoring["ponderaciones_sectoriales"] = {
                "cooperativo": 1.2,
                "financiero": 1.5,
                "real": 1.3,
                "telcos": 0.8,
            }

        # =========================================================
        # 8. CARGAR ESCALA MÁXIMA
        # =========================================================
        cursor.execute(
            """
            SELECT valor FROM configuracion_sistema
            WHERE clave = 'ESCALA_MAX'
        """
        )
        row = cursor.fetchone()
        if row:
            scoring["escala_max"] = json.loads(row[0])
        else:
            scoring["escala_max"] = 100

        # =========================================================
        # 9. CARGAR CONFIGURACIÓN POR LÍNEA DE CRÉDITO
        # =========================================================
        cursor.execute(
            """
            SELECT linea_credito, configuracion
            FROM configuracion_scoring
            ORDER BY version DESC
        """
        )

        config_por_linea = {}
        for row in cursor.fetchall():
            linea = row[0]
            config = json.loads(row[1])
            config_por_linea[linea] = config

        scoring["configuracion_por_linea"] = config_por_linea

        # =========================================================
        # 10. CARGAR SECCIONES DE CRITERIOS (2025-12-26)
        # =========================================================
        cursor.execute(
            """
            SELECT valor FROM configuracion_sistema
            WHERE clave = 'SECCIONES_SCORING'
        """
        )
        row = cursor.fetchone()
        if row:
            scoring["secciones"] = json.loads(row[0])
            print(f"✅ cargar_scoring: {len(scoring['secciones'])} secciones cargadas")
        else:
            # Secciones por defecto
            scoring["secciones"] = [
                {
                    "id": "probabilidad_pago",
                    "nombre": "Análisis de Probabilidad de Pago",
                    "icono": "bi-graph-up",
                    "color": "purple",
                    "orden": 0,
                },
                {
                    "id": "ingresos",
                    "nombre": "Análisis de Ingresos",
                    "icono": "bi-cash-stack",
                    "color": "green",
                    "orden": 1,
                },
                {
                    "id": "endeudamiento",
                    "nombre": "Análisis de Endeudamiento",
                    "icono": "bi-credit-card",
                    "color": "blue",
                    "orden": 2,
                },
                {
                    "id": "comportamiento_pago",
                    "nombre": "Comportamiento de Pago",
                    "icono": "bi-calendar-check",
                    "color": "orange",
                    "orden": 3,
                },
                {
                    "id": "sectorial",
                    "nombre": "Análisis Sectorial",
                    "icono": "bi-building",
                    "color": "teal",
                    "orden": 4,
                },
                {
                    "id": "verificacion",
                    "nombre": "Verificación Documental",
                    "icono": "bi-file-earmark-check",
                    "color": "red",
                    "orden": 5,
                },
                {
                    "id": "otros",
                    "nombre": "Otros Criterios",
                    "icono": "bi-gear",
                    "color": "gray",
                    "orden": 99,
                },
            ]
            print("⚠️ cargar_scoring: Usando secciones por defecto")

        # =========================================================
        # 11. METADATOS OPCIONALES
        # =========================================================
        cursor.execute(
            """
            SELECT valor FROM configuracion_sistema
            WHERE clave = 'SCORING_VERSION'
        """
        )
        row = cursor.fetchone()
        if row:
            scoring["version"] = json.loads(row[0])
        else:
            scoring["version"] = "2.0"

    except Exception as e:
        print(f"❌ Error en cargar_scoring(): {e}")
        import traceback

        traceback.print_exc()
        # Retornar estructura mínima para evitar errores
        scoring = {
            "criterios": {},
            "niveles_riesgo": [],
            "factores_rechazo_automatico": [],
            "puntaje_minimo_aprobacion": 17,
            "configuracion_por_linea": {},
        }
    finally:
        conn.close()

    return scoring


def guardar_scoring(scoring_data):
    """
    Guarda configuración COMPLETA de scoring en SQLite.
    Reemplaza la función que escribía scoring.json.

    IMPORTANTE: Guarda en el MISMO formato que cargar_scoring() lee.

    Args:
        scoring_data (dict): Configuración de scoring con estructura:
            - criterios
            - niveles_riesgo
            - factores_rechazo_automatico
            - puntaje_minimo_aprobacion
            - umbral_mora_telcos_rechazo
            - configuracion_por_linea
            - etc.
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        # =========================================================
        # 1. GUARDAR CRITERIOS
        # =========================================================
        if "criterios" in scoring_data:
            cursor.execute(
                """
                INSERT OR REPLACE INTO configuracion_sistema
                (clave, valor, descripcion, fecha_modificacion)
                VALUES ('CRITERIOS_SCORING', ?, 'Criterios de scoring interno', CURRENT_TIMESTAMP)
            """,
                (json.dumps(scoring_data["criterios"], ensure_ascii=False),),
            )
            print(f"✅ Criterios guardados: {len(scoring_data['criterios'])} criterios")

        # =========================================================
        # 2. GUARDAR NIVELES DE RIESGO (CRÍTICO)
        # =========================================================
        if "niveles_riesgo" in scoring_data:
            cursor.execute(
                """
                INSERT OR REPLACE INTO configuracion_sistema
                (clave, valor, descripcion, fecha_modificacion)
                VALUES ('NIVELES_RIESGO', ?, 'Niveles de riesgo con tasas diferenciadas', CURRENT_TIMESTAMP)
            """,
                (json.dumps(scoring_data["niveles_riesgo"], ensure_ascii=False),),
            )
            print(
                f"✅ Niveles de riesgo guardados: {len(scoring_data['niveles_riesgo'])} niveles"
            )

        # =========================================================
        # 3. GUARDAR FACTORES DE RECHAZO AUTOMÁTICO
        # =========================================================
        if "factores_rechazo_automatico" in scoring_data:
            cursor.execute(
                """
                INSERT OR REPLACE INTO configuracion_sistema
                (clave, valor, descripcion, fecha_modificacion)
                VALUES ('FACTORES_RECHAZO', ?, 'Factores de rechazo automático', CURRENT_TIMESTAMP)
            """,
                (
                    json.dumps(
                        scoring_data["factores_rechazo_automatico"], ensure_ascii=False
                    ),
                ),
            )
            print(
                f"✅ Factores de rechazo guardados: {len(scoring_data['factores_rechazo_automatico'])} factores"
            )

        # =========================================================
        # 4. GUARDAR PUNTAJE MÍNIMO DE APROBACIÓN
        # =========================================================
        if "puntaje_minimo_aprobacion" in scoring_data:
            cursor.execute(
                """
                INSERT OR REPLACE INTO configuracion_sistema
                (clave, valor, descripcion, fecha_modificacion)
                VALUES ('PUNTAJE_MINIMO_APROBACION', ?, 'Puntaje mínimo para aprobación', CURRENT_TIMESTAMP)
            """,
                (json.dumps(scoring_data["puntaje_minimo_aprobacion"]),),
            )

        # =========================================================
        # 5. GUARDAR UMBRAL MORA TELCOS
        # =========================================================
        if "umbral_mora_telcos_rechazo" in scoring_data:
            cursor.execute(
                """
                INSERT OR REPLACE INTO configuracion_sistema
                (clave, valor, descripcion, fecha_modificacion)
                VALUES ('UMBRAL_MORA_TELCOS', ?, 'Umbral mora telcos para rechazo', CURRENT_TIMESTAMP)
            """,
                (json.dumps(scoring_data["umbral_mora_telcos_rechazo"]),),
            )

        # =========================================================
        # 6. GUARDAR TABLA DANE
        # =========================================================
        if "tabla_dane_2025" in scoring_data:
            cursor.execute(
                """
                INSERT OR REPLACE INTO configuracion_sistema
                (clave, valor, descripcion, fecha_modificacion)
                VALUES ('TABLA_DANE_2025', ?, 'Tabla DANE 2025', CURRENT_TIMESTAMP)
            """,
                (json.dumps(scoring_data["tabla_dane_2025"], ensure_ascii=False),),
            )

        # =========================================================
        # 7. GUARDAR PONDERACIONES SECTORIALES
        # =========================================================
        if "ponderaciones_sectoriales" in scoring_data:
            cursor.execute(
                """
                INSERT OR REPLACE INTO configuracion_sistema
                (clave, valor, descripcion, fecha_modificacion)
                VALUES ('PONDERACIONES_SECTORIALES', ?, 'Ponderaciones por sector', CURRENT_TIMESTAMP)
            """,
                (
                    json.dumps(
                        scoring_data["ponderaciones_sectoriales"], ensure_ascii=False
                    ),
                ),
            )

        # =========================================================
        # 8. GUARDAR CONFIGURACIÓN POR LÍNEA DE CRÉDITO
        # =========================================================
        if "configuracion_por_linea" in scoring_data:
            for linea, config in scoring_data["configuracion_por_linea"].items():
                if linea == "descripcion":
                    continue
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO configuracion_scoring
                    (linea_credito, configuracion, version, fecha_modificacion)
                    VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                """,
                    (linea, json.dumps(config, ensure_ascii=False)),
                )
            print(f"✅ Configuración por línea guardada")

        # =========================================================
        # 9. GUARDAR SECCIONES DE CRITERIOS (2025-12-26)
        # =========================================================
        if "secciones" in scoring_data:
            cursor.execute(
                """
                INSERT OR REPLACE INTO configuracion_sistema
                (clave, valor, descripcion, fecha_modificacion)
                VALUES ('SECCIONES_SCORING', ?, 'Secciones de agrupación de criterios', CURRENT_TIMESTAMP)
            """,
                (json.dumps(scoring_data["secciones"], ensure_ascii=False),),
            )
            print(f"✅ Secciones guardadas: {len(scoring_data['secciones'])} secciones")

        conn.commit()
        print("✅ guardar_scoring(): Configuración completa guardada en SQLite")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error en guardar_scoring(): {e}")
        import traceback

        traceback.print_exc()
        raise e
    finally:
        conn.close()


# ============================================================================
# FUNCIONES DE EVALUACIONES
# ============================================================================


def cargar_evaluaciones():
    """
    Carga todas las evaluaciones desde SQLite.
    Reemplaza la función que leía evaluaciones_log.json.

    Returns:
        list: Lista de evaluaciones
    """
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT timestamp, asesor, nombre_cliente, cedula,
               tipo_credito, linea_credito, estado_desembolso, origen,
               resultado, criterios_evaluados, monto_solicitado,
               estado_comite, decision_admin, visto_por_asesor,
               fecha_visto_asesor, fecha_envio_comite,
               puntaje_datacredito, criterios_detalle, valores_criterios, nivel_riesgo
        FROM evaluaciones
        ORDER BY timestamp DESC
    """
    )

    evaluaciones = []
    for row in cursor.fetchall():
        ev = {
            "timestamp": row[0],
            "asesor": row[1],
            "cliente": row[2],
            "nombre_cliente": row[2],
            "cedula": row[3],
            "tipo_credito": row[4],
            "linea_credito": row[5],
            "estado_desembolso": row[6],
            "origen": row[7],
            "resultado": json.loads(row[8]) if row[8] else {},
            "criterios_evaluados": json.loads(row[9]) if row[9] else [],
            "monto_solicitado": row[10],
            "estado_comite": row[11],
            "decision_admin": json.loads(row[12]) if row[12] else None,
            "visto_por_asesor": bool(row[13]),
            "fecha_visto_asesor": row[14],
            "fecha_envio_comite": row[15],
            "puntaje_datacredito": row[16],
            "datacredito": row[16],
            "criterios_detalle": json.loads(row[17]) if row[17] else [],
            "valores_criterios": json.loads(row[18]) if row[18] else {},
            "nivel_riesgo": row[19],
        }
        evaluaciones.append(ev)

    conn.close()
    return evaluaciones


def guardar_evaluacion(evaluacion):
    """
    Guarda una evaluación en SQLite.
    Reemplaza la función que escribía en evaluaciones_log.json.

    Args:
        evaluacion (dict): Evaluación a guardar
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        # Preparar datos
        timestamp = evaluacion.get("timestamp", datetime.now().isoformat())
        asesor = evaluacion.get("asesor")
        nombre_cliente = evaluacion.get("cliente") or evaluacion.get("nombre_cliente")
        cedula = evaluacion.get("cedula")
        tipo_credito = evaluacion.get("tipo_credito")
        linea_credito = evaluacion.get("linea_credito")
        estado_desembolso = evaluacion.get("estado_desembolso", "Pendiente")
        origen = evaluacion.get("origen", "Automático")

        resultado = json.dumps(evaluacion.get("resultado", {}))
        criterios = json.dumps(evaluacion.get("criterios_evaluados", []))
        monto_solicitado = evaluacion.get("monto_solicitado")

        estado_comite = evaluacion.get("estado_comite")
        decision_admin = (
            json.dumps(evaluacion.get("decision_admin"))
            if evaluacion.get("decision_admin")
            else None
        )
        visto_por_asesor = 1 if evaluacion.get("visto_por_asesor") else 0
        fecha_visto_asesor = evaluacion.get("fecha_visto_asesor")
        fecha_envio_comite = evaluacion.get("fecha_envio_comite")

        puntaje_datacredito = evaluacion.get("puntaje_datacredito") or evaluacion.get(
            "datacredito"
        )

        # Campos adicionales para el detalle
        criterios_detalle = (
            json.dumps(evaluacion.get("criterios_detalle", []))
            if evaluacion.get("criterios_detalle")
            else None
        )
        valores_criterios = (
            json.dumps(evaluacion.get("valores_criterios", {}))
            if evaluacion.get("valores_criterios")
            else None
        )
        nivel_riesgo = evaluacion.get("nivel_riesgo")
        genero = evaluacion.get("genero_solicitante")

        # Insertar o actualizar
        cursor.execute(
            """
            INSERT OR REPLACE INTO evaluaciones (
                timestamp, asesor, nombre_cliente, cedula,
                tipo_credito, linea_credito, estado_desembolso, origen,
                resultado, criterios_evaluados, monto_solicitado,
                estado_comite, decision_admin, visto_por_asesor,
                fecha_visto_asesor, fecha_envio_comite,
                puntaje_datacredito, datacredito,
                criterios_detalle, valores_criterios, nivel_riesgo,
                genero
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                timestamp,
                asesor,
                nombre_cliente,
                cedula,
                tipo_credito,
                linea_credito,
                estado_desembolso,
                origen,
                resultado,
                criterios,
                monto_solicitado,
                estado_comite,
                decision_admin,
                visto_por_asesor,
                fecha_visto_asesor,
                fecha_envio_comite,
                puntaje_datacredito,
                puntaje_datacredito,
                criterios_detalle,
                valores_criterios,
                nivel_riesgo,
                genero,
            ),
        )

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def actualizar_evaluacion(timestamp, datos_actualizar):
    """
    Actualiza campos específicos de una evaluación.
    Útil para actualizar estado_comite, decision_admin, etc.

    Args:
        timestamp (str): Timestamp de la evaluación
        datos_actualizar (dict): Campos a actualizar
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        # Construir query dinámicamente
        campos_set = []
        valores = []

        for campo, valor in datos_actualizar.items():
            if campo in [
                "resultado",
                "criterios_evaluados",
                "decision_admin",
                "criterios_detalle",
                "valores_criterios",
            ]:
                # Campos JSON
                campos_set.append(f"{campo} = ?")
                valores.append(json.dumps(valor) if valor else None)
            elif campo == "visto_por_asesor":
                campos_set.append(f"{campo} = ?")
                valores.append(1 if valor else 0)
            else:
                campos_set.append(f"{campo} = ?")
                valores.append(valor)

        if not campos_set:
            return

        campos_set.append("fecha_modificacion = CURRENT_TIMESTAMP")
        valores.append(timestamp)

        query = f"""
            UPDATE evaluaciones
            SET {', '.join(campos_set)}
            WHERE timestamp = ?
        """

        cursor.execute(query, valores)
        conn.commit()

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# ============================================================================
# FUNCIONES DE SIMULACIONES
# ============================================================================


def cargar_simulaciones():
    """
    Carga todas las simulaciones desde SQLite.
    Reemplaza la función que leía simulaciones_log.json.

    Returns:
        list: Lista de simulaciones
    """
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT timestamp, asesor, cliente, cedula,
               monto, plazo, linea_credito, tasa_ea, tasa_mensual,
               cuota_mensual, nivel_riesgo, aval, seguro, plataforma,
               total_financiar, caso_origen, modalidad_desembolso
        FROM simulaciones
        ORDER BY timestamp DESC
    """
    )

    simulaciones = []
    for row in cursor.fetchall():
        sim = {
            "timestamp": row[0],
            "asesor": row[1],
            "cliente": row[2],
            "cedula": row[3],
            "monto": row[4],
            "plazo": row[5],
            "linea_credito": row[6],
            "tasa_ea": row[7],
            "tasa_mensual": row[8],
            "cuota_mensual": row[9],
            "nivel_riesgo": row[10],
            "aval": row[11],
            "seguro": row[12],
            "plataforma": row[13],
            "total_financiar": row[14],
            "caso_origen": row[15],
            "modalidad_desembolso": row[16],
        }
        simulaciones.append(sim)

    conn.close()
    return simulaciones


def guardar_simulacion(simulacion):
    """
    Guarda una simulación en SQLite.
    Reemplaza la función que escribía en simulaciones_log.json.

    Args:
        simulacion (dict): Simulación a guardar
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO simulaciones (
                timestamp, asesor, cliente, cedula,
                monto, plazo, linea_credito, tasa_ea, tasa_mensual,
                cuota_mensual, nivel_riesgo, aval, seguro, plataforma,
                total_financiar, caso_origen, modalidad_desembolso
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                simulacion.get("timestamp"),
                simulacion.get("asesor"),
                simulacion.get("cliente"),
                simulacion.get("cedula"),
                simulacion.get("monto"),
                simulacion.get("plazo"),
                simulacion.get("linea_credito"),
                simulacion.get("tasa_ea"),
                simulacion.get("tasa_mensual"),
                simulacion.get("cuota_mensual"),
                simulacion.get("nivel_riesgo"),
                simulacion.get("aval", 0),
                simulacion.get("seguro", 0),
                simulacion.get("plataforma", 0),
                simulacion.get("total_financiar"),
                simulacion.get("caso_origen"),
                simulacion.get("modalidad_desembolso", "completo"),
            ),
        )

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# ============================================================================
# FUNCIONES ESPECÍFICAS PARA COMITÉ
# ============================================================================


def obtener_casos_comite(filtros=None):
    """
    Obtiene casos de comité con filtros opcionales.

    Args:
        filtros (dict): Filtros opcionales
            - estado_comite: 'pending', 'approved', 'rejected'
            - asesor: username del asesor
            - limite: número máximo de resultados

    Returns:
        list: Lista de casos
    """
    conn = conectar_db()
    cursor = conn.cursor()

    query = """
        SELECT timestamp, asesor, nombre_cliente, cedula,
               tipo_credito, monto_solicitado, resultado,
               estado_comite, decision_admin, visto_por_asesor,
               fecha_envio_comite, puntaje_datacredito,
               criterios_detalle, valores_criterios, nivel_riesgo,
               criterios_evaluados
        FROM evaluaciones
        WHERE estado_comite IS NOT NULL
    """

    params = []

    if filtros:
        if "estado_comite" in filtros:
            query += " AND estado_comite = ?"
            params.append(filtros["estado_comite"])

        if "asesor" in filtros:
            query += " AND asesor = ?"
            params.append(filtros["asesor"])

        if "visto_por_asesor" in filtros:
            query += " AND visto_por_asesor = ?"
            params.append(1 if filtros["visto_por_asesor"] else 0)

    query += " ORDER BY timestamp DESC"

    if filtros and "limite" in filtros:
        query += " LIMIT ?"
        params.append(filtros["limite"])

    cursor.execute(query, params)

    casos = []
    for row in cursor.fetchall():
        puntaje_dc = row[11]
        criterios_eval = json.loads(row[15]) if row[15] else []
        
        # Si puntaje_datacredito es null, intentar extraer de criterios_evaluados
        if puntaje_dc is None and criterios_eval:
            for c in criterios_eval:
                if isinstance(c, dict) and c.get("codigo") == "puntaje_datacredito" and c.get("valor") is not None:
                    try:
                        puntaje_dc = float(c["valor"])
                    except (ValueError, TypeError):
                        pass
                    break
        
        caso = {
            "timestamp": row[0],
            "asesor": row[1],
            "nombre_cliente": row[2],
            "cliente": row[2],
            "cedula": row[3],
            "tipo_credito": row[4],
            "monto_solicitado": row[5],
            "resultado": json.loads(row[6]) if row[6] else {},
            "estado_comite": row[7],
            "decision_admin": json.loads(row[8]) if row[8] else None,
            "visto_por_asesor": bool(row[9]),
            "fecha_envio_comite": row[10],
            "puntaje_datacredito": puntaje_dc,
            "datacredito": puntaje_dc,
            "criterios_detalle": json.loads(row[12]) if row[12] else [],
            "valores_criterios": json.loads(row[13]) if row[13] else {},
            "nivel_riesgo": row[14],
            "criterios_evaluados": criterios_eval,
        }
        casos.append(caso)

    conn.close()
    return casos


def contar_casos_nuevos_asesor(username):
    """
    Cuenta casos nuevos (aprobados/rechazados no vistos) para un asesor.

    Args:
        username (str): Username del asesor

    Returns:
        int: Número de casos nuevos
    """
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM evaluaciones
        WHERE asesor = ?
          AND estado_comite IN ('approved', 'rejected')
          AND visto_por_asesor = 0
    """,
        (username,),
    )

    count = cursor.fetchone()[0]
    conn.close()

    return count


# ============================================================================
# FUNCIONES DE USUARIOS
# ============================================================================


def obtener_usuario(username):
    """
    Obtiene información de un usuario.

    Args:
        username (str): Username

    Returns:
        dict: Información del usuario o None
    """
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT username, password_hash, rol, activo
        FROM usuarios
        WHERE username = ?
    """,
        (username,),
    )

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "username": row[0],
            "password_hash": row[1],
            "rol": row[2],
            "activo": bool(row[3]),
        }
    return None


def crear_usuario(username, password_hash, rol="asesor", nombre_completo=""):
    """
    Crea un nuevo usuario.

    Args:
        username (str): Username
        password_hash (str): Hash de la contraseña
        rol (str): Rol del usuario
        nombre_completo (str): Nombre completo del usuario (para identificación)

    Returns:
        bool: True si se creó exitosamente
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO usuarios (username, password_hash, rol, nombre_completo, activo)
            VALUES (?, ?, ?, ?, 1)
        """,
            (username, password_hash, rol, nombre_completo),
        )

        conn.commit()
        print(f"✅ Usuario '{username}' ({nombre_completo}) creado con rol '{rol}'")
        return True

    except sqlite3.IntegrityError:
        # Usuario ya existe
        print(f"⚠️ Usuario '{username}' ya existe")
        return False
    except Exception as e:
        conn.rollback()
        print(f"❌ Error creando usuario: {e}")
        raise e
    finally:
        conn.close()


def eliminar_usuario_db(username):
    """
    Elimina (soft delete) un usuario de la base de datos.

    CORRECCIÓN 2025-12-24: Necesario porque guardar_configuracion()
    solo hace INSERT/UPDATE, nunca DELETE.

    Args:
        username (str): Username del usuario a eliminar

    Returns:
        bool: True si se eliminó exitosamente
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        # No permitir eliminar admin
        if username == "admin":
            print(f"⚠️ No se puede eliminar el usuario admin")
            return False

        # Verificar que el usuario existe
        cursor.execute(
            "SELECT id FROM usuarios WHERE username = ? AND activo = 1", (username,)
        )
        usuario = cursor.fetchone()

        if not usuario:
            print(f"⚠️ Usuario '{username}' no encontrado o ya está inactivo")
            return False

        # Soft delete: marcar como inactivo
        cursor.execute(
            """
            UPDATE usuarios
            SET activo = 0,
                fecha_modificacion = CURRENT_TIMESTAMP
            WHERE username = ?
        """,
            (username,),
        )

        conn.commit()
        print(f"✅ Usuario '{username}' marcado como inactivo en SQLite (soft delete)")
        return True

    except Exception as e:
        conn.rollback()
        print(f"❌ Error al eliminar usuario: {e}")
        return False
    finally:
        conn.close()


# ============================================================================
# FUNCIONES DE SEGUROS
# ============================================================================


def cargar_seguros():
    """
    Carga configuración de seguros desde SQLite.

    Returns:
        dict: Configuración de seguros
    """
    conn = conectar_db()
    cursor = conn.cursor()

    seguros = {}

    cursor.execute(
        """
        SELECT valor FROM configuracion_sistema
        WHERE clave = 'SEGURO_VIDA'
    """
    )
    row = cursor.fetchone()
    if row:
        seguros["SEGURO_VIDA"] = json.loads(row[0])
    else:
        seguros["SEGURO_VIDA"] = []

    conn.close()
    return seguros


def guardar_seguros(seguros_data):
    """
    Guarda configuración de seguros en SQLite.

    Args:
        seguros_data (dict): Configuración de seguros
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        if "SEGURO_VIDA" in seguros_data:
            cursor.execute(
                """
                INSERT OR REPLACE INTO configuracion_sistema
                (clave, valor, descripcion, fecha_modificacion)
                VALUES ('SEGURO_VIDA', ?, 'Configuración de seguro de vida', CURRENT_TIMESTAMP)
            """,
                (json.dumps(seguros_data["SEGURO_VIDA"], ensure_ascii=False),),
            )

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================


def ejecutar_query(query, params=None, fetchone=False):
    """
    Ejecuta una query SQL genérica (para casos especiales).

    Args:
        query (str): Query SQL
        params (tuple): Parámetros de la query
        fetchone (bool): Si True, retorna solo un resultado

    Returns:
        list/tuple: Resultados de la query
    """
    conn = conectar_db()
    cursor = conn.cursor()

    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)

    if fetchone:
        resultado = cursor.fetchone()
    else:
        resultado = cursor.fetchall()

    conn.close()
    return resultado


def obtener_evaluacion_por_timestamp(timestamp):
    """
    Obtiene una evaluación específica por su timestamp.

    Args:
        timestamp (str): Timestamp de la evaluación

    Returns:
        dict: Evaluación o None
    """
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT timestamp, asesor, nombre_cliente, cedula,
               tipo_credito, linea_credito, estado_desembolso, origen,
               resultado, criterios_evaluados, monto_solicitado,
               estado_comite, decision_admin, visto_por_asesor,
               fecha_visto_asesor, fecha_envio_comite,
               puntaje_datacredito, criterios_detalle, valores_criterios, nivel_riesgo
        FROM evaluaciones
        WHERE timestamp = ?
    """,
        (timestamp,),
    )

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "timestamp": row[0],
            "asesor": row[1],
            "cliente": row[2],
            "nombre_cliente": row[2],
            "cedula": row[3],
            "tipo_credito": row[4],
            "linea_credito": row[5],
            "estado_desembolso": row[6],
            "origen": row[7],
            "resultado": json.loads(row[8]) if row[8] else {},
            "criterios_evaluados": json.loads(row[9]) if row[9] else [],
            "monto_solicitado": row[10],
            "estado_comite": row[11],
            "decision_admin": json.loads(row[12]) if row[12] else None,
            "visto_por_asesor": bool(row[13]),
            "fecha_visto_asesor": row[14],
            "fecha_envio_comite": row[15],
            "puntaje_datacredito": row[16],
            "datacredito": row[16],
            "criterios_detalle": json.loads(row[17]) if row[17] else [],
            "valores_criterios": json.loads(row[18]) if row[18] else {},
            "nivel_riesgo": row[19],
        }
    return None


def obtener_usuarios_completos():
    """
    Obtiene lista completa de usuarios con todos sus datos.
    Usado por panel admin para gestión de usuarios.

    Returns:
        list: Lista de diccionarios con datos de usuarios
    """
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, username, nombre_completo, rol, activo,
               fecha_creacion, fecha_modificacion
        FROM usuarios
        WHERE activo = 1
        ORDER BY fecha_creacion DESC
    """
    )

    usuarios = []
    for row in cursor.fetchall():
        usuarios.append(
            {
                "id": row[0],
                "username": row[1],
                "nombre_completo": row[2] or "",
                "rol": row[3],
                "activo": bool(row[4]),
                "fecha_creacion": row[5],
                "fecha_modificacion": row[6],
            }
        )

    conn.close()
    return usuarios


def actualizar_usuario(username, nombre_completo=None, rol=None):
    """
    Actualiza datos de un usuario existente.

    Args:
        username (str): Username del usuario a actualizar
        nombre_completo (str): Nuevo nombre completo (opcional)
        rol (str): Nuevo rol (opcional)

    Returns:
        bool: True si se actualizó exitosamente
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        # Construir query dinámicamente según qué campos se actualizan
        updates = []
        params = []

        if nombre_completo is not None:
            updates.append("nombre_completo = ?")
            params.append(nombre_completo)

        if rol is not None:
            updates.append("rol = ?")
            params.append(rol)

        if not updates:
            return False  # Nada que actualizar

        updates.append("fecha_modificacion = CURRENT_TIMESTAMP")
        params.append(username)

        query = f"UPDATE usuarios SET {', '.join(updates)} WHERE username = ?"
        cursor.execute(query, params)

        conn.commit()
        print(f"✅ Usuario '{username}' actualizado")
        return cursor.rowcount > 0

    except Exception as e:
        conn.rollback()
        print(f"❌ Error actualizando usuario: {e}")
        return False
    finally:
        conn.close()


# ============================================================================
# FUNCIONES DE ASIGNACIONES DE EQUIPO (RBAC)
# ============================================================================


def ensure_user_assignments_table():
    """
    Asegura que la tabla user_assignments existe.
    Llamar desde flask_app.py al iniciar.
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                manager_username TEXT NOT NULL,
                member_username TEXT NOT NULL,
                activo BOOLEAN DEFAULT 1,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(manager_username, member_username)
            )
        """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_assign_manager ON user_assignments(manager_username)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_assign_member ON user_assignments(member_username)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_assign_activo ON user_assignments(activo)"
        )
        conn.commit()
        print("✅ Tabla user_assignments verificada/creada")
        return True
    except Exception as e:
        print(f"❌ Error creando tabla user_assignments: {e}")
        return False
    finally:
        conn.close()


def get_assigned_usernames(manager_username):
    """
    Obtiene los usernames asignados a un manager (supervisor/auditor/gerente).

    Args:
        manager_username (str): Username del manager

    Returns:
        list: Lista de usernames asignados (puede estar vacía)
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT member_username
            FROM user_assignments
            WHERE manager_username = ? AND activo = 1
            ORDER BY member_username
        """,
            (manager_username,),
        )

        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"❌ Error obteniendo asignaciones: {e}")
        return []
    finally:
        conn.close()


def get_assigned_usernames_recursive(manager_username, max_depth: int = 5):
    """Devuelve TODOS los usuarios asignados de forma directa o indirecta (expansión jerárquica).

    Ejemplo:
      gerente -> supervisor
      supervisor -> asesor1, asesor2
    Entonces gerente ve: supervisor, asesor1, asesor2

    max_depth evita loops por asignaciones mal hechas.
    """
    ensure_user_assignments_table()

    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT manager_username, member_username
            FROM user_assignments
            WHERE activo = 1
            """
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    # Construir mapa manager -> set(miembros)
    graph = {}
    for mgr, mem in rows:
        if mgr not in graph:
            graph[mgr] = set()
        graph[mgr].add(mem)

    visited = set([manager_username])
    result = set()
    frontier = [manager_username]
    depth = 0

    while frontier and depth < max_depth:
        next_frontier = []
        for mgr in frontier:
            for mem in graph.get(mgr, set()):
                if mem in visited:
                    continue
                visited.add(mem)
                result.add(mem)
                next_frontier.append(mem)
        frontier = next_frontier
        depth += 1

    return sorted(result)


def get_all_assignments():
    """
    Obtiene todas las asignaciones activas.

    Returns:
        list: Lista de dicts con manager_username, member_username, fecha_creacion
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT ua.id, ua.manager_username, ua.member_username, ua.fecha_creacion,
                   u1.rol as manager_rol, u2.rol as member_rol
            FROM user_assignments ua
            LEFT JOIN usuarios u1 ON ua.manager_username = u1.username
            LEFT JOIN usuarios u2 ON ua.member_username = u2.username
            WHERE ua.activo = 1
            ORDER BY ua.manager_username, ua.member_username
        """
        )

        assignments = []
        for row in cursor.fetchall():
            assignments.append(
                {
                    "id": row[0],
                    "manager_username": row[1],
                    "member_username": row[2],
                    "fecha_creacion": row[3],
                    "manager_rol": row[4],
                    "member_rol": row[5],
                }
            )
        return assignments
    except Exception as e:
        print(f"❌ Error obteniendo todas las asignaciones: {e}")
        return []
    finally:
        conn.close()


def add_assignment(manager_username, member_username):
    """
    Agrega una asignación de usuario a un manager.

    Args:
        manager_username (str): Username del supervisor/auditor/gerente
        member_username (str): Username del usuario asignado

    Returns:
        bool: True si se agregó exitosamente
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        # Verificar que no sea auto-asignación
        if manager_username == member_username:
            print("⚠️ No se permite auto-asignación")
            return False

        cursor.execute(
            """
            INSERT INTO user_assignments (manager_username, member_username, activo)
            VALUES (?, ?, 1)
            ON CONFLICT(manager_username, member_username)
            DO UPDATE SET activo = 1, fecha_creacion = CURRENT_TIMESTAMP
        """,
            (manager_username, member_username),
        )

        conn.commit()
        print(f"✅ Asignación creada: {member_username} → {manager_username}")
        return True
    except Exception as e:
        conn.rollback()
        print(f"❌ Error creando asignación: {e}")
        return False
    finally:
        conn.close()


def remove_assignment(manager_username, member_username):
    """
    Elimina (desactiva) una asignación.

    Args:
        manager_username (str): Username del manager
        member_username (str): Username del miembro

    Returns:
        bool: True si se eliminó exitosamente
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE user_assignments
            SET activo = 0
            WHERE manager_username = ? AND member_username = ?
        """,
            (manager_username, member_username),
        )

        conn.commit()
        if cursor.rowcount > 0:
            print(f"✅ Asignación eliminada: {member_username} ← {manager_username}")
            return True
        return False
    except Exception as e:
        conn.rollback()
        print(f"❌ Error eliminando asignación: {e}")
        return False
    finally:
        conn.close()


def remove_assignment_by_id(assignment_id):
    """
    Elimina una asignación por su ID.

    Args:
        assignment_id (int): ID de la asignación

    Returns:
        bool: True si se eliminó exitosamente
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE user_assignments
            SET activo = 0
            WHERE id = ?
        """,
            (assignment_id,),
        )

        conn.commit()
        print(f"✅ Delete assignment_id={assignment_id}: rowcount={cursor.rowcount}")
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"❌ Error eliminando asignación: {e}")
        return False
    finally:
        conn.close()


def resolve_visible_usernames(
    username_actual, permisos_actuales, contexto="simulaciones"
):
    """
    Resuelve qué usernames puede ver un usuario según sus permisos y asignaciones.

    Args:
        username_actual (str): Username del usuario actual
        permisos_actuales (list): Lista de códigos de permisos del usuario
        contexto (str): 'simulaciones' o 'evaluaciones'

    Returns:
        dict: {
            'scope': 'propio' | 'equipo' | 'todos',
            'usernames_visibles': list[str] | None (None = sin filtro para 'todos')
        }
    """
    # Determinar prefijo según contexto
    if contexto == "simulaciones":
        perm_todos = "sim_hist_todos"
        perm_equipo = "sim_hist_equipo"
        perm_propio = "sim_hist_propio"
    elif contexto == "evaluaciones":
        perm_todos = "sco_hist_todos"
        perm_equipo = "sco_hist_equipo"
        perm_propio = "sco_hist_propio"
    else:
        # Default a propio
        return {"scope": "propio", "usernames_visibles": [username_actual]}

    # Verificar permisos en orden de mayor a menor alcance
    if perm_todos in permisos_actuales:
        return {"scope": "todos", "usernames_visibles": None}

    if perm_equipo in permisos_actuales:
        # Obtener usuarios asignados
        asignados = get_assigned_usernames_recursive(username_actual)
        # POLÍTICA: Si no tiene asignaciones, ve 0 resultados (lista vacía)
        # NO se incluye a sí mismo automáticamente
        return {"scope": "equipo", "usernames_visibles": asignados}

    if perm_propio in permisos_actuales:
        return {"scope": "propio", "usernames_visibles": [username_actual]}

    # Sin permisos = sin acceso
    return {"scope": "ninguno", "usernames_visibles": []}


def obtener_simulaciones_por_asesores(lista_usernames):
    """
    Obtiene simulaciones filtradas por lista de asesores.

    Args:
        lista_usernames (list): Lista de usernames a filtrar

    Returns:
        list: Lista de simulaciones
    """
    if not lista_usernames:
        return []

    conn = conectar_db()
    cursor = conn.cursor()

    try:
        placeholders = ",".join(["?" for _ in lista_usernames])
        cursor.execute(
            f"""
            SELECT timestamp, asesor, cliente, cedula,
                   monto, plazo, linea_credito, tasa_ea, tasa_mensual,
                   cuota_mensual, nivel_riesgo, aval, seguro, plataforma,
                   total_financiar, caso_origen, modalidad_desembolso
            FROM simulaciones
            WHERE asesor IN ({placeholders})
            ORDER BY timestamp DESC
        """,
            lista_usernames,
        )

        simulaciones = []
        for row in cursor.fetchall():
            sim = {
                "timestamp": row[0],
                "asesor": row[1],
                "cliente": row[2],
                "cedula": row[3],
                "monto": row[4],
                "plazo": row[5],
                "linea_credito": row[6],
                "tasa_ea": row[7],
                "tasa_mensual": row[8],
                "cuota_mensual": row[9],
                "nivel_riesgo": row[10],
                "aval": row[11],
                "seguro": row[12],
                "plataforma": row[13],
                "total_financiar": row[14],
                "caso_origen": row[15],
                "modalidad_desembolso": row[16],
            }
            simulaciones.append(sim)

        return simulaciones
    except Exception as e:
        print(f"❌ Error obteniendo simulaciones por asesores: {e}")
        return []
    finally:
        conn.close()


def obtener_evaluaciones_por_asesores(lista_usernames):
    """
    Obtiene evaluaciones filtradas por lista de asesores.

    Args:
        lista_usernames (list): Lista de usernames a filtrar

    Returns:
        list: Lista de evaluaciones
    """
    if not lista_usernames:
        return []

    conn = conectar_db()
    cursor = conn.cursor()

    try:
        placeholders = ",".join(["?" for _ in lista_usernames])
        cursor.execute(
            f"""
            SELECT id, timestamp, asesor, nombre_cliente, cedula,
                   tipo_credito, linea_credito, estado_desembolso, origen,
                   resultado, criterios_evaluados, monto_solicitado,
                   estado_comite, decision_admin, visto_por_asesor,
                   fecha_visto_asesor, fecha_envio_comite,
                   puntaje_datacredito
            FROM evaluaciones
            WHERE asesor IN ({placeholders})
            ORDER BY timestamp DESC
        """,
            lista_usernames,
        )

        evaluaciones = []
        for row in cursor.fetchall():
            ev = {
                "id": row[0],
                "timestamp": row[1],
                "asesor": row[2],
                "nombre_cliente": row[3],
                "cedula": row[4],
                "tipo_credito": row[5],
                "linea_credito": row[6],
                "estado_desembolso": row[7],
                "origen": row[8],
                "resultado": json.loads(row[9]) if row[9] else {},
                "criterios_evaluados": json.loads(row[10]) if row[10] else [],
                "monto_solicitado": row[11],
                "estado_comite": row[12],
                "decision_admin": json.loads(row[13]) if row[13] else None,
                "visto_por_asesor": bool(row[14]),
                "fecha_visto_asesor": row[15],
                "fecha_envio_comite": row[16],
                "puntaje_datacredito": row[17],
            }
            evaluaciones.append(ev)

        return evaluaciones
    except Exception as e:
        print(f"❌ Error obteniendo evaluaciones por asesores: {e}")
        import traceback

        traceback.print_exc()
        return []
    finally:
        conn.close()


def get_managers_for_assignments():
    """
    Obtiene usuarios que pueden tener asignaciones (supervisor, auditor, gerente).

    Returns:
        list: Lista de dicts con username, nombre_completo, rol
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT username, nombre_completo, rol
            FROM usuarios
            WHERE rol IN ('supervisor', 'auditor', 'gerente') AND activo = 1
            ORDER BY rol, username
        """
        )

        return [
            {"username": row[0], "nombre_completo": row[1], "rol": row[2]}
            for row in cursor.fetchall()
        ]
    except Exception as e:
        print(f"❌ Error obteniendo managers: {e}")
        return []
    finally:
        conn.close()


def get_members_for_assignments():
    """
    Obtiene usuarios que pueden ser asignados (cualquier rol activo).

    Returns:
        list: Lista de dicts con username, nombre_completo, rol
    """
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT username, nombre_completo, rol
            FROM usuarios
            WHERE activo = 1
            ORDER BY rol, username
        """
        )

        return [
            {"username": row[0], "nombre_completo": row[1], "rol": row[2]}
            for row in cursor.fetchall()
        ]
    except Exception as e:
        print(f"❌ Error obteniendo members: {e}")
        return []
    finally:
        conn.close()


# ============================================================================
# FUNCIONES DE PARAMETROS DEL SISTEMA
# ============================================================================

def obtener_parametros_sistema():
    """
    Obtiene todos los parametros del sistema.

    Returns:
        list[dict]: Lista de parametros con clave, valor, descripcion, ultima_actualizacion
    """
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT clave, valor, descripcion, ultima_actualizacion
            FROM parametros_sistema
            ORDER BY clave
        """)
        return [
            {
                "clave": row[0],
                "valor": row[1],
                "descripcion": row[2],
                "ultima_actualizacion": row[3]
            }
            for row in cursor.fetchall()
        ]
    except Exception as e:
        print(f"Error obteniendo parametros del sistema: {e}")
        return []
    finally:
        if conn:
            conn.close()


def obtener_parametro(clave):
    """
    Obtiene el valor de un parametro del sistema por su clave.

    Args:
        clave (str): Clave del parametro

    Returns:
        str|None: Valor del parametro o None si no existe
    """
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT valor FROM parametros_sistema WHERE clave = ?", (clave,))
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"Error obteniendo parametro '{clave}': {e}")
        return None
    finally:
        if conn:
            conn.close()


def guardar_parametro(clave, valor, descripcion=None):
    """
    Guarda o actualiza un parametro del sistema.

    Args:
        clave (str): Clave del parametro
        valor (str): Valor del parametro
        descripcion (str|None): Descripcion opcional

    Returns:
        bool: True si se guardo correctamente
    """
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        ahora = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO parametros_sistema (clave, valor, descripcion, ultima_actualizacion)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(clave) DO UPDATE SET
                valor = excluded.valor,
                descripcion = COALESCE(excluded.descripcion, parametros_sistema.descripcion),
                ultima_actualizacion = excluded.ultima_actualizacion
        """, (clave, str(valor), descripcion, ahora))
        conn.commit()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error guardando parametro '{clave}': {e}")
        return False
    finally:
        if conn:
            conn.close()


def obtener_parametros_laborales():
    """
    Obtiene los parametros laborales desde la BD, con fallback a config.py.

    Returns:
        dict: Parametros laborales compatibles con validacion_nomina_service
    """
    try:
        params = obtener_parametros_sistema()
        params_dict = {p["clave"]: p["valor"] for p in params}

        if "smlv" in params_dict:
            return {
                "anio": 2026,
                "smlv": float(params_dict.get("smlv", "1423500")),
                "subsidio_transporte": float(params_dict.get("subsidio_transporte", "200000")),
                "pct_salud_empleado": float(params_dict.get("pct_salud_empleado", "0.04")),
                "pct_pension_empleado": float(params_dict.get("pct_pension_empleado", "0.04")),
                "pct_fsp_4_smlv": 0.01,
                "pct_retencion_umbral": 5_470_000,
            }
    except Exception as e:
        print(f"Error obteniendo parametros laborales de BD: {e}")

    # Fallback a config.py
    try:
        from app.config import Config
        return Config.PARAMETROS_LABORALES
    except Exception:
        return {
            "anio": 2026,
            "smlv": 1_423_500,
            "subsidio_transporte": 200_000,
            "pct_salud_empleado": 0.04,
            "pct_pension_empleado": 0.04,
            "pct_fsp_4_smlv": 0.01,
            "pct_retencion_umbral": 5_470_000,
        }
