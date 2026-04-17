"""
DB_HELPERS_COMITE.PY - Funciones helper para el sistema de Comité de Crédito
==============================================================================
Gestiona configuración del comité por línea, miembros, evaluaciones y decisiones.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "loansi.db"


def get_db_connection():
    """Obtiene conexión a la base de datos."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================================
# INICIALIZACIÓN DE TABLAS
# ============================================================================

def inicializar_tablas_comite():
    """
    Crea las tablas necesarias para el sistema de comité si no existen.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Tabla de configuración del comité por línea
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comite_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                linea_credito_id INTEGER NOT NULL UNIQUE,
                activo BOOLEAN DEFAULT 1,
                tiempo_max_respuesta_horas INTEGER DEFAULT 48,
                requiere_unanimidad BOOLEAN DEFAULT 0,
                num_minimo_votos INTEGER DEFAULT 1,
                auto_aprobar_si_timeout BOOLEAN DEFAULT 0,
                notificar_email_lista TEXT,
                score_minimo_comite REAL DEFAULT 0,
                score_maximo_comite REAL DEFAULT 100,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (linea_credito_id) REFERENCES lineas_credito(id)
            )
        """)
        
        # Tabla de miembros del comité
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comite_miembros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                linea_credito_id INTEGER,
                rol TEXT DEFAULT 'Revisor',
                puede_aprobar BOOLEAN DEFAULT 1,
                puede_rechazar BOOLEAN DEFAULT 1,
                limite_monto_decision REAL,
                activo BOOLEAN DEFAULT 1,
                fecha_desde TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fecha_hasta TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
                FOREIGN KEY (linea_credito_id) REFERENCES lineas_credito(id)
            )
        """)
        
        # Tabla de votos del comité (para decisiones que requieren múltiples votos)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comite_votos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluacion_timestamp TEXT NOT NULL,
                usuario_id INTEGER NOT NULL,
                voto TEXT NOT NULL,
                comentario TEXT,
                fecha_voto TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )
        """)
        
        # Tabla de comentarios del comité
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comite_comentarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluacion_timestamp TEXT NOT NULL,
                usuario_id INTEGER NOT NULL,
                comentario TEXT NOT NULL,
                tipo TEXT DEFAULT 'nota',
                fecha_comentario TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )
        """)
        
        # ====================================================================
        # NIVEL 1: Configuración Global del Comité
        # ====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comite_config_global (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tiempo_max_decision_horas INTEGER DEFAULT 48,
                accion_al_expirar TEXT DEFAULT 'rechazar',
                alertas_habilitadas BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insertar configuración global por defecto si no existe
        cursor.execute("SELECT COUNT(*) FROM comite_config_global")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO comite_config_global 
                (tiempo_max_decision_horas, accion_al_expirar, alertas_habilitadas)
                VALUES (48, 'rechazar', 1)
            """)
        
        # ====================================================================
        # NIVEL 2 - Sección B: Criterios Borderline por Línea
        # ====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comite_criterios_borderline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                linea_credito_id INTEGER NOT NULL UNIQUE,
                
                -- Categoría 1: Criterios de Bureau (DataCrédito)
                score_datacredito_minimo INTEGER DEFAULT 500,
                mora_max_financiero_dias INTEGER DEFAULT 30,
                mora_max_telcos_dias INTEGER DEFAULT 60,
                consultas_max_60_dias INTEGER DEFAULT 6,
                
                -- Categoría 2: Criterios de Capacidad de Pago
                dti_maximo REAL DEFAULT 40.0,
                ingreso_minimo REAL DEFAULT 1400000,
                cupo_total_minimo REAL DEFAULT 5000000,
                
                -- Categoría 3: Criterios de Estabilidad
                antiguedad_laboral_min_meses INTEGER DEFAULT 6,
                historial_pagos_min_meses INTEGER DEFAULT 6,
                creditos_cerrados_minimos INTEGER DEFAULT 1,
                
                -- Categoría 4: Comportamiento Interno Loansi
                evaluar_historial_loansi BOOLEAN DEFAULT 1,
                creditos_anteriores_min INTEGER DEFAULT 0,
                mora_max_historica_loansi_dias INTEGER DEFAULT 15,
                pct_pagos_puntuales_min REAL DEFAULT 80.0,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (linea_credito_id) REFERENCES lineas_credito(id)
            )
        """)
        
        # ====================================================================
        # NIVEL 2 - Sección C: Señales de Alerta por Línea
        # ====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comite_alertas_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                linea_credito_id INTEGER NOT NULL UNIQUE,
                
                -- Alertas con umbral numérico
                alerta_score_datacredito_bajo BOOLEAN DEFAULT 1,
                umbral_score_datacredito INTEGER DEFAULT 450,
                
                alerta_dti_alto BOOLEAN DEFAULT 1,
                umbral_dti REAL DEFAULT 40.0,
                
                alerta_consultas_excesivas BOOLEAN DEFAULT 1,
                umbral_consultas INTEGER DEFAULT 5,
                
                alerta_ingreso_vs_dane BOOLEAN DEFAULT 1,
                umbral_ingreso_dane_pct REAL DEFAULT 200.0,
                
                alerta_monto_alto BOOLEAN DEFAULT 1,
                umbral_monto_pct REAL DEFAULT 80.0,
                
                -- Alertas booleanas simples
                alerta_sin_historial_loansi BOOLEAN DEFAULT 1,
                alerta_mora_activa BOOLEAN DEFAULT 1,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (linea_credito_id) REFERENCES lineas_credito(id)
            )
        """)
        
        # ====================================================================
        # Tabla de alertas dinámicas (basadas en criterios de scoring)
        # ====================================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comite_alertas_dinamicas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                linea_credito_id INTEGER NOT NULL,
                criterio_codigo TEXT NOT NULL,
                habilitada BOOLEAN DEFAULT 0,
                valor_umbral REAL,
                operador TEXT DEFAULT '<',
                valor_alerta TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(linea_credito_id, criterio_codigo)
            )
        """)
        
        conn.commit()
        print("✅ Tablas de comité inicializadas correctamente (incluye criterios borderline, alertas y alertas dinámicas)")
        return True
        
    except Exception as e:
        print(f"❌ Error inicializando tablas de comité: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# ============================================================================
# CONFIGURACIÓN DEL COMITÉ POR LÍNEA
# ============================================================================

def obtener_config_comite(linea_id):
    """
    Obtiene la configuración del comité para una línea específica.
    
    Args:
        linea_id: ID de la línea de crédito
        
    Returns:
        dict: Configuración del comité o valores por defecto
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Obtener config de comité CON puntaje_revision_manual desde comite_config
        # y puntaje_minimo_aprobacion desde scoring_config_linea (solo lectura)
        cursor.execute("""
            SELECT cc.*, lc.nombre as linea_nombre,
                   scl.puntaje_minimo_aprobacion,
                   scl.escala_max
            FROM comite_config cc
            JOIN lineas_credito lc ON cc.linea_credito_id = lc.id
            LEFT JOIN scoring_config_linea scl ON cc.linea_credito_id = scl.linea_credito_id
            WHERE cc.linea_credito_id = ?
        """, (linea_id,))
        
        row = cursor.fetchone()
        
        if row:
            return {
                "id": row["id"],
                "linea_credito_id": row["linea_credito_id"],
                "linea_nombre": row["linea_nombre"],
                "activo": bool(row["activo"]),
                "tiempo_max_respuesta_horas": row["tiempo_max_respuesta_horas"] or 48,
                "requiere_unanimidad": bool(row["requiere_unanimidad"]),
                "num_minimo_votos": row["num_minimo_votos"] or 1,
                "auto_aprobar_si_timeout": bool(row["auto_aprobar_si_timeout"]),
                "notificar_email_lista": row["notificar_email_lista"],
                "score_minimo_comite": row["score_minimo_comite"] or 0,
                "score_maximo_comite": row["score_maximo_comite"] or 100,
                # puntaje_revision_manual viene de comite_config (fuente única)
                "puntaje_revision_manual": row["puntaje_revision_manual"] or 24,
                # puntaje_minimo_aprobacion viene de scoring_config_linea (solo lectura)
                "puntaje_minimo_aprobacion": row["puntaje_minimo_aprobacion"] or 17,
                "escala_max": row["escala_max"] or 45
            }
        else:
            # Retornar valores por defecto si no hay configuración
            cursor.execute("SELECT nombre FROM lineas_credito WHERE id = ?", (linea_id,))
            linea_row = cursor.fetchone()
            
            return {
                "id": None,
                "linea_credito_id": linea_id,
                "linea_nombre": linea_row["nombre"] if linea_row else "Sin nombre",
                "activo": False,
                "tiempo_max_respuesta_horas": 48,
                "requiere_unanimidad": False,
                "num_minimo_votos": 1,
                "auto_aprobar_si_timeout": False,
                "notificar_email_lista": None,
                "score_minimo_comite": 0,
                "score_maximo_comite": 45,
                "puntaje_minimo_aprobacion": 17,
                "puntaje_revision_manual": 24,
                "escala_max": 45
            }
            
    except Exception as e:
        print(f"Error obteniendo config comité: {e}")
        return None
    finally:
        conn.close()


def guardar_config_comite(linea_id, datos):
    """
    Guarda la configuración del comité para una línea.
    
    Args:
        linea_id: ID de la línea de crédito
        datos: Dict con la configuración a guardar
        
    Returns:
        bool: True si se guardó correctamente
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # puntaje_revision_manual ahora se guarda en comite_config (fuente única)
        cursor.execute("""
            INSERT INTO comite_config 
            (linea_credito_id, activo, tiempo_max_respuesta_horas, requiere_unanimidad,
             num_minimo_votos, auto_aprobar_si_timeout, notificar_email_lista,
             score_minimo_comite, score_maximo_comite, puntaje_revision_manual, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(linea_credito_id) DO UPDATE SET
                activo = excluded.activo,
                tiempo_max_respuesta_horas = excluded.tiempo_max_respuesta_horas,
                requiere_unanimidad = excluded.requiere_unanimidad,
                num_minimo_votos = excluded.num_minimo_votos,
                auto_aprobar_si_timeout = excluded.auto_aprobar_si_timeout,
                notificar_email_lista = excluded.notificar_email_lista,
                score_minimo_comite = excluded.score_minimo_comite,
                score_maximo_comite = excluded.score_maximo_comite,
                puntaje_revision_manual = excluded.puntaje_revision_manual,
                updated_at = CURRENT_TIMESTAMP
        """, (
            linea_id,
            datos.get("activo", True),
            datos.get("tiempo_max_respuesta_horas", 48),
            datos.get("requiere_unanimidad", False),
            datos.get("num_minimo_votos", 1),
            datos.get("auto_aprobar_si_timeout", False),
            datos.get("notificar_email_lista"),
            datos.get("score_minimo_comite", 0),
            datos.get("score_maximo_comite", 100),
            datos.get("puntaje_revision_manual", 22)
        ))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Error guardando config comité: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def obtener_todas_configs_comite():
    """
    Obtiene la configuración del comité para todas las líneas activas.
    
    Returns:
        list: Lista de configuraciones
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # puntaje_revision_manual ahora viene de comite_config (fuente única)
        cursor.execute("""
            SELECT lc.id, lc.nombre,
                   COALESCE(cc.activo, 0) as comite_activo,
                   COALESCE(cc.tiempo_max_respuesta_horas, 48) as tiempo_max,
                   COALESCE(cc.num_minimo_votos, 1) as votos_minimos,
                   COALESCE(scl.puntaje_minimo_aprobacion, 17) as puntaje_minimo,
                   COALESCE(cc.puntaje_revision_manual, 24) as puntaje_revision,
                   COALESCE(scl.escala_max, 45) as escala_max,
                   (SELECT COUNT(*) FROM comite_miembros cm 
                    WHERE (cm.linea_credito_id = lc.id OR cm.linea_credito_id IS NULL) 
                    AND cm.activo = 1) as num_miembros
            FROM lineas_credito lc
            LEFT JOIN comite_config cc ON lc.id = cc.linea_credito_id
            LEFT JOIN scoring_config_linea scl ON lc.id = scl.linea_credito_id
            WHERE lc.activo = 1
            ORDER BY lc.nombre
        """)
        
        configs = []
        for row in cursor.fetchall():
            configs.append({
                "linea_id": row["id"],
                "linea_nombre": row["nombre"],
                "comite_activo": bool(row["comite_activo"]),
                "tiempo_max": row["tiempo_max"],
                "votos_minimos": row["votos_minimos"],
                "puntaje_minimo": row["puntaje_minimo"],
                "puntaje_revision": row["puntaje_revision"],
                "escala_max": row["escala_max"],
                "num_miembros": row["num_miembros"],
                # Calcular zona de comité
                "zona_comite": f"{row['puntaje_minimo']} - {row['puntaje_revision']}"
            })
        
        return configs
        
    except Exception as e:
        print(f"Error obteniendo configs comité: {e}")
        return []
    finally:
        conn.close()


# ============================================================================
# GESTIÓN DE MIEMBROS DEL COMITÉ
# ============================================================================

def obtener_miembros_comite(linea_id=None):
    """
    Obtiene los miembros del comité.
    
    Args:
        linea_id: ID de línea específica o None para miembros globales
        
    Returns:
        list: Lista de miembros
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if linea_id:
            # Miembros específicos de la línea + miembros globales
            cursor.execute("""
                SELECT cm.*, u.username, u.nombre as usuario_nombre, u.rol as usuario_rol,
                       lc.nombre as linea_nombre
                FROM comite_miembros cm
                JOIN usuarios u ON cm.usuario_id = u.id
                LEFT JOIN lineas_credito lc ON cm.linea_credito_id = lc.id
                WHERE (cm.linea_credito_id = ? OR cm.linea_credito_id IS NULL)
                AND cm.activo = 1
                ORDER BY cm.rol, u.nombre
            """, (linea_id,))
        else:
            # Todos los miembros
            cursor.execute("""
                SELECT cm.*, u.username, u.nombre as usuario_nombre, u.rol as usuario_rol,
                       lc.nombre as linea_nombre
                FROM comite_miembros cm
                JOIN usuarios u ON cm.usuario_id = u.id
                LEFT JOIN lineas_credito lc ON cm.linea_credito_id = lc.id
                WHERE cm.activo = 1
                ORDER BY lc.nombre NULLS FIRST, cm.rol, u.nombre
            """)
        
        miembros = []
        for row in cursor.fetchall():
            miembros.append({
                "id": row["id"],
                "usuario_id": row["usuario_id"],
                "username": row["username"],
                "usuario_nombre": row["usuario_nombre"],
                "usuario_rol": row["usuario_rol"],
                "linea_credito_id": row["linea_credito_id"],
                "linea_nombre": row["linea_nombre"] or "Todas las líneas",
                "rol": row["rol"],
                "puede_aprobar": bool(row["puede_aprobar"]),
                "puede_rechazar": bool(row["puede_rechazar"]),
                "limite_monto": row["limite_monto_decision"],
                "fecha_desde": row["fecha_desde"]
            })
        
        return miembros
        
    except Exception as e:
        print(f"Error obteniendo miembros comité: {e}")
        return []
    finally:
        conn.close()


def agregar_miembro_comite(usuario_id, linea_id=None, rol="Revisor", puede_aprobar=True, 
                           puede_rechazar=True, limite_monto=None):
    """
    Agrega un miembro al comité.
    
    Args:
        usuario_id: ID del usuario
        linea_id: ID de línea (None = todas las líneas)
        rol: Rol en el comité (Revisor, Decididor, Observador)
        puede_aprobar: Si puede aprobar casos
        puede_rechazar: Si puede rechazar casos
        limite_monto: Límite de monto para decisiones (None = sin límite)
        
    Returns:
        int: ID del nuevo miembro o None si error
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar si ya existe el miembro
        cursor.execute("""
            SELECT id FROM comite_miembros 
            WHERE usuario_id = ? AND (linea_credito_id = ? OR (linea_credito_id IS NULL AND ? IS NULL))
            AND activo = 1
        """, (usuario_id, linea_id, linea_id))
        
        if cursor.fetchone():
            print(f"Usuario {usuario_id} ya es miembro del comité para línea {linea_id}")
            return None
        
        cursor.execute("""
            INSERT INTO comite_miembros 
            (usuario_id, linea_credito_id, rol, puede_aprobar, puede_rechazar, limite_monto_decision)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (usuario_id, linea_id, rol, puede_aprobar, puede_rechazar, limite_monto))
        
        conn.commit()
        return cursor.lastrowid
        
    except Exception as e:
        print(f"Error agregando miembro comité: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


def actualizar_miembro_comite(miembro_id, datos):
    """
    Actualiza los datos de un miembro del comité.
    
    Args:
        miembro_id: ID del registro de miembro
        datos: Dict con campos a actualizar
        
    Returns:
        bool: True si se actualizó correctamente
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE comite_miembros SET
                rol = COALESCE(?, rol),
                puede_aprobar = COALESCE(?, puede_aprobar),
                puede_rechazar = COALESCE(?, puede_rechazar),
                limite_monto_decision = ?
            WHERE id = ?
        """, (
            datos.get("rol"),
            datos.get("puede_aprobar"),
            datos.get("puede_rechazar"),
            datos.get("limite_monto"),
            miembro_id
        ))
        
        conn.commit()
        return cursor.rowcount > 0
        
    except Exception as e:
        print(f"Error actualizando miembro comité: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def eliminar_miembro_comite(miembro_id):
    """
    Desactiva un miembro del comité (soft delete).
    
    Args:
        miembro_id: ID del registro de miembro
        
    Returns:
        bool: True si se eliminó correctamente
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE comite_miembros 
            SET activo = 0, fecha_hasta = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (miembro_id,))
        
        conn.commit()
        return cursor.rowcount > 0
        
    except Exception as e:
        print(f"Error eliminando miembro comité: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def es_miembro_comite(usuario_id, linea_id=None):
    """
    Verifica si un usuario es miembro del comité.
    
    Args:
        usuario_id: ID del usuario
        linea_id: ID de línea específica o None
        
    Returns:
        dict: Info del miembro o None si no es miembro
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT * FROM comite_miembros 
            WHERE usuario_id = ? 
            AND (linea_credito_id = ? OR linea_credito_id IS NULL)
            AND activo = 1
        """, (usuario_id, linea_id))
        
        row = cursor.fetchone()
        if row:
            return {
                "id": row["id"],
                "rol": row["rol"],
                "puede_aprobar": bool(row["puede_aprobar"]),
                "puede_rechazar": bool(row["puede_rechazar"]),
                "limite_monto": row["limite_monto_decision"]
            }
        return None
        
    except Exception as e:
        print(f"Error verificando miembro comité: {e}")
        return None
    finally:
        conn.close()


def puede_decidir(usuario_id, linea_id, monto):
    """
    Verifica si un usuario puede tomar decisión sobre un caso.
    
    Args:
        usuario_id: ID del usuario
        linea_id: ID de la línea de crédito
        monto: Monto del crédito
        
    Returns:
        tuple: (puede_decidir: bool, razon: str)
    """
    miembro = es_miembro_comite(usuario_id, linea_id)
    
    if not miembro:
        return False, "No es miembro del comité para esta línea"
    
    if not miembro["puede_aprobar"] and not miembro["puede_rechazar"]:
        return False, "No tiene permisos de decisión (solo observador)"
    
    if miembro["limite_monto"] and monto > miembro["limite_monto"]:
        return False, f"Monto excede su límite de decisión (${miembro['limite_monto']:,.0f})"
    
    return True, "OK"


# ============================================================================
# OBTENER USUARIOS DISPONIBLES PARA COMITÉ
# ============================================================================

def obtener_usuarios_disponibles_comite():
    """
    Obtiene usuarios que pueden ser agregados al comité.
    
    Returns:
        list: Lista de usuarios con roles apropiados
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, username, nombre, rol
            FROM usuarios
            WHERE activo = 1 AND rol IN ('admin', 'admin_tecnico', 'coordinador', 'asesor_senior')
            ORDER BY nombre
        """)
        
        usuarios = []
        for row in cursor.fetchall():
            usuarios.append({
                "id": row["id"],
                "username": row["username"],
                "nombre": row["nombre"],
                "rol": row["rol"]
            })
        
        return usuarios
        
    except Exception as e:
        print(f"Error obteniendo usuarios: {e}")
        return []
    finally:
        conn.close()


# ============================================================================
# COMENTARIOS Y VOTOS
# ============================================================================

def agregar_comentario_comite(evaluacion_timestamp, usuario_id, comentario, tipo="nota"):
    """
    Agrega un comentario a una evaluación del comité.
    
    Args:
        evaluacion_timestamp: Timestamp de la evaluación
        usuario_id: ID del usuario que comenta
        comentario: Texto del comentario
        tipo: Tipo de comentario (nota, alerta, solicitud_doc)
        
    Returns:
        int: ID del comentario o None si error
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO comite_comentarios 
            (evaluacion_timestamp, usuario_id, comentario, tipo)
            VALUES (?, ?, ?, ?)
        """, (evaluacion_timestamp, usuario_id, comentario, tipo))
        
        conn.commit()
        return cursor.lastrowid
        
    except Exception as e:
        print(f"Error agregando comentario: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


def obtener_comentarios_comite(evaluacion_timestamp):
    """
    Obtiene los comentarios de una evaluación.
    
    Args:
        evaluacion_timestamp: Timestamp de la evaluación
        
    Returns:
        list: Lista de comentarios
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT cc.*, u.nombre as usuario_nombre, u.username
            FROM comite_comentarios cc
            JOIN usuarios u ON cc.usuario_id = u.id
            WHERE cc.evaluacion_timestamp = ?
            ORDER BY cc.fecha_comentario DESC
        """, (evaluacion_timestamp,))
        
        comentarios = []
        for row in cursor.fetchall():
            comentarios.append({
                "id": row["id"],
                "usuario_nombre": row["usuario_nombre"],
                "username": row["username"],
                "comentario": row["comentario"],
                "tipo": row["tipo"],
                "fecha": row["fecha_comentario"]
            })
        
        return comentarios
        
    except Exception as e:
        print(f"Error obteniendo comentarios: {e}")
        return []
    finally:
        conn.close()


# ============================================================================
# DETERMINAR SI REQUIERE COMITÉ
# ============================================================================

def determinar_requiere_comite(score_normalizado, linea_id):
    """
    Determina si una evaluación requiere revisión del comité.
    
    Args:
        score_normalizado: Puntaje normalizado (0-100)
        linea_id: ID de la línea de crédito
        
    Returns:
        tuple: (requiere_comite: bool, razon: str)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Obtener umbrales de la línea
        cursor.execute("""
            SELECT puntaje_minimo_aprobacion, puntaje_revision_manual, escala_max
            FROM scoring_config_linea
            WHERE linea_credito_id = ?
        """, (linea_id,))
        
        row = cursor.fetchone()
        
        if not row:
            # Sin configuración, usar valores por defecto
            puntaje_minimo = 38
            puntaje_revision = 55
        else:
            puntaje_minimo = row["puntaje_minimo_aprobacion"] or 38
            puntaje_revision = row["puntaje_revision_manual"] or 55
        
        # Verificar si está en zona de comité
        if score_normalizado < puntaje_minimo:
            return False, "Rechazado automáticamente (puntaje muy bajo)"
        
        if score_normalizado >= puntaje_revision:
            return False, "Aprobado automáticamente (puntaje suficiente)"
        
        # Está en zona de comité
        return True, f"Puntaje en zona de revisión manual ({puntaje_minimo}-{puntaje_revision})"
        
    except Exception as e:
        print(f"Error determinando comité: {e}")
        return False, "Error en evaluación"
    finally:
        conn.close()


# ============================================================================
# NIVEL 1: CONFIGURACIÓN GLOBAL DEL COMITÉ
# ============================================================================

def obtener_config_global_comite():
    """
    Obtiene la configuración global del comité.
    
    Returns:
        dict: Configuración global
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM comite_config_global LIMIT 1")
        row = cursor.fetchone()
        
        if row:
            return {
                "id": row["id"],
                "tiempo_max_decision_horas": row["tiempo_max_decision_horas"],
                "accion_al_expirar": row["accion_al_expirar"],
                "alertas_habilitadas": bool(row["alertas_habilitadas"])
            }
        else:
            return {
                "id": None,
                "tiempo_max_decision_horas": 48,
                "accion_al_expirar": "rechazar",
                "alertas_habilitadas": True
            }
            
    except Exception as e:
        print(f"Error obteniendo config global: {e}")
        return {
            "tiempo_max_decision_horas": 48,
            "accion_al_expirar": "rechazar",
            "alertas_habilitadas": True
        }
    finally:
        conn.close()


def guardar_config_global_comite(datos):
    """
    Guarda la configuración global del comité.
    
    Args:
        datos: Dict con la configuración a guardar
        
    Returns:
        bool: True si se guardó correctamente
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE comite_config_global SET
                tiempo_max_decision_horas = ?,
                accion_al_expirar = ?,
                alertas_habilitadas = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        """, (
            datos.get("tiempo_max_decision_horas", 48),
            datos.get("accion_al_expirar", "rechazar"),
            datos.get("alertas_habilitadas", True)
        ))
        
        if cursor.rowcount == 0:
            cursor.execute("""
                INSERT INTO comite_config_global 
                (tiempo_max_decision_horas, accion_al_expirar, alertas_habilitadas)
                VALUES (?, ?, ?)
            """, (
                datos.get("tiempo_max_decision_horas", 48),
                datos.get("accion_al_expirar", "rechazar"),
                datos.get("alertas_habilitadas", True)
            ))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Error guardando config global: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# ============================================================================
# NIVEL 2 - SECCIÓN B: CRITERIOS BORDERLINE POR LÍNEA
# ============================================================================

def obtener_criterios_borderline(linea_id):
    """
    Obtiene los criterios borderline para una línea específica.
    
    Args:
        linea_id: ID de la línea de crédito
        
    Returns:
        dict: Criterios borderline o valores por defecto
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT * FROM comite_criterios_borderline
            WHERE linea_credito_id = ?
        """, (linea_id,))
        
        row = cursor.fetchone()
        
        if row:
            return {
                "linea_credito_id": row["linea_credito_id"],
                # Bureau
                "score_datacredito_minimo": row["score_datacredito_minimo"],
                "mora_max_financiero_dias": row["mora_max_financiero_dias"],
                "mora_max_telcos_dias": row["mora_max_telcos_dias"],
                "consultas_max_60_dias": row["consultas_max_60_dias"],
                # Capacidad
                "dti_maximo": row["dti_maximo"],
                "ingreso_minimo": row["ingreso_minimo"],
                "cupo_total_minimo": row["cupo_total_minimo"],
                # Estabilidad
                "antiguedad_laboral_min_meses": row["antiguedad_laboral_min_meses"],
                "historial_pagos_min_meses": row["historial_pagos_min_meses"],
                "creditos_cerrados_minimos": row["creditos_cerrados_minimos"],
                # Loansi
                "evaluar_historial_loansi": bool(row["evaluar_historial_loansi"]),
                "creditos_anteriores_min": row["creditos_anteriores_min"],
                "mora_max_historica_loansi_dias": row["mora_max_historica_loansi_dias"],
                "pct_pagos_puntuales_min": row["pct_pagos_puntuales_min"]
            }
        else:
            # Valores por defecto
            return obtener_defaults_borderline(linea_id)
            
    except Exception as e:
        print(f"Error obteniendo criterios borderline: {e}")
        return obtener_defaults_borderline(linea_id)
    finally:
        conn.close()


def obtener_defaults_borderline(linea_id):
    """
    Retorna valores por defecto para criterios borderline según la línea.
    """
    # Valores diferenciados por línea según especificación
    defaults = {
        5: {  # LoansiFlex
            "score_datacredito_minimo": 580,
            "mora_max_financiero_dias": 0,
            "mora_max_telcos_dias": 200000,
            "consultas_max_60_dias": 5,
            "dti_maximo": 38.0,
            "ingreso_minimo": 2100000,
            "cupo_total_minimo": 5000000
        },
        6: {  # LoansiMoto
            "score_datacredito_minimo": 500,
            "mora_max_financiero_dias": 30,
            "mora_max_telcos_dias": 250000,
            "consultas_max_60_dias": 7,
            "dti_maximo": 45.0,
            "ingreso_minimo": 1700000,
            "cupo_total_minimo": 3000000
        },
        7: {  # Microflex
            "score_datacredito_minimo": 550,
            "mora_max_financiero_dias": 15,
            "mora_max_telcos_dias": 200000,
            "consultas_max_60_dias": 6,
            "dti_maximo": 40.0,
            "ingreso_minimo": 1400000,
            "cupo_total_minimo": 2000000
        }
    }
    
    base = defaults.get(linea_id, {
        "score_datacredito_minimo": 500,
        "mora_max_financiero_dias": 30,
        "mora_max_telcos_dias": 200000,
        "consultas_max_60_dias": 6,
        "dti_maximo": 40.0,
        "ingreso_minimo": 1400000,
        "cupo_total_minimo": 5000000
    })
    
    return {
        "linea_credito_id": linea_id,
        **base,
        "antiguedad_laboral_min_meses": 6,
        "historial_pagos_min_meses": 6,
        "creditos_cerrados_minimos": 1,
        "evaluar_historial_loansi": True,
        "creditos_anteriores_min": 0,
        "mora_max_historica_loansi_dias": 15,
        "pct_pagos_puntuales_min": 80.0
    }


def guardar_criterios_borderline(linea_id, datos):
    """
    Guarda los criterios borderline para una línea.
    
    Args:
        linea_id: ID de la línea de crédito
        datos: Dict con los criterios a guardar
        
    Returns:
        bool: True si se guardó correctamente
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO comite_criterios_borderline 
            (linea_credito_id, score_datacredito_minimo, mora_max_financiero_dias,
             mora_max_telcos_dias, consultas_max_60_dias, dti_maximo, ingreso_minimo,
             cupo_total_minimo, antiguedad_laboral_min_meses, historial_pagos_min_meses,
             creditos_cerrados_minimos, evaluar_historial_loansi, creditos_anteriores_min,
             mora_max_historica_loansi_dias, pct_pagos_puntuales_min, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(linea_credito_id) DO UPDATE SET
                score_datacredito_minimo = excluded.score_datacredito_minimo,
                mora_max_financiero_dias = excluded.mora_max_financiero_dias,
                mora_max_telcos_dias = excluded.mora_max_telcos_dias,
                consultas_max_60_dias = excluded.consultas_max_60_dias,
                dti_maximo = excluded.dti_maximo,
                ingreso_minimo = excluded.ingreso_minimo,
                cupo_total_minimo = excluded.cupo_total_minimo,
                antiguedad_laboral_min_meses = excluded.antiguedad_laboral_min_meses,
                historial_pagos_min_meses = excluded.historial_pagos_min_meses,
                creditos_cerrados_minimos = excluded.creditos_cerrados_minimos,
                evaluar_historial_loansi = excluded.evaluar_historial_loansi,
                creditos_anteriores_min = excluded.creditos_anteriores_min,
                mora_max_historica_loansi_dias = excluded.mora_max_historica_loansi_dias,
                pct_pagos_puntuales_min = excluded.pct_pagos_puntuales_min,
                updated_at = CURRENT_TIMESTAMP
        """, (
            linea_id,
            datos.get("score_datacredito_minimo", 500),
            datos.get("mora_max_financiero_dias", 30),
            datos.get("mora_max_telcos_dias", 60),
            datos.get("consultas_max_60_dias", 6),
            datos.get("dti_maximo", 40.0),
            datos.get("ingreso_minimo", 1400000),
            datos.get("cupo_total_minimo", 5000000),
            datos.get("antiguedad_laboral_min_meses", 6),
            datos.get("historial_pagos_min_meses", 6),
            datos.get("creditos_cerrados_minimos", 1),
            datos.get("evaluar_historial_loansi", True),
            datos.get("creditos_anteriores_min", 0),
            datos.get("mora_max_historica_loansi_dias", 15),
            datos.get("pct_pagos_puntuales_min", 80.0)
        ))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Error guardando criterios borderline: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# ============================================================================
# NIVEL 2 - SECCIÓN C: SEÑALES DE ALERTA POR LÍNEA
# ============================================================================

def obtener_alertas_config(linea_id):
    """
    Obtiene la configuración de alertas para una línea específica.
    
    Args:
        linea_id: ID de la línea de crédito
        
    Returns:
        dict: Configuración de alertas o valores por defecto
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT * FROM comite_alertas_config
            WHERE linea_credito_id = ?
        """, (linea_id,))
        
        row = cursor.fetchone()
        
        if row:
            return {
                "linea_credito_id": row["linea_credito_id"],
                "alerta_score_datacredito_bajo": bool(row["alerta_score_datacredito_bajo"]),
                "umbral_score_datacredito": row["umbral_score_datacredito"],
                "alerta_dti_alto": bool(row["alerta_dti_alto"]),
                "umbral_dti": row["umbral_dti"],
                "alerta_consultas_excesivas": bool(row["alerta_consultas_excesivas"]),
                "umbral_consultas": row["umbral_consultas"],
                "alerta_ingreso_vs_dane": bool(row["alerta_ingreso_vs_dane"]),
                "umbral_ingreso_dane_pct": row["umbral_ingreso_dane_pct"],
                "alerta_monto_alto": bool(row["alerta_monto_alto"]),
                "umbral_monto_pct": row["umbral_monto_pct"],
                "alerta_sin_historial_loansi": bool(row["alerta_sin_historial_loansi"]),
                "alerta_mora_activa": bool(row["alerta_mora_activa"])
            }
        else:
            return {
                "linea_credito_id": linea_id,
                "alerta_score_datacredito_bajo": True,
                "umbral_score_datacredito": 450,
                "alerta_dti_alto": True,
                "umbral_dti": 40.0,
                "alerta_consultas_excesivas": True,
                "umbral_consultas": 5,
                "alerta_ingreso_vs_dane": True,
                "umbral_ingreso_dane_pct": 200.0,
                "alerta_monto_alto": True,
                "umbral_monto_pct": 80.0,
                "alerta_sin_historial_loansi": True,
                "alerta_mora_activa": True
            }
            
    except Exception as e:
        print(f"Error obteniendo alertas config: {e}")
        return None
    finally:
        conn.close()


def guardar_alertas_config(linea_id, datos):
    """
    Guarda la configuración de alertas para una línea.
    
    Args:
        linea_id: ID de la línea de crédito
        datos: Dict con la configuración a guardar
        
    Returns:
        bool: True si se guardó correctamente
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO comite_alertas_config 
            (linea_credito_id, alerta_score_datacredito_bajo, umbral_score_datacredito,
             alerta_dti_alto, umbral_dti, alerta_consultas_excesivas, umbral_consultas,
             alerta_ingreso_vs_dane, umbral_ingreso_dane_pct, alerta_monto_alto,
             umbral_monto_pct, alerta_sin_historial_loansi, alerta_mora_activa, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(linea_credito_id) DO UPDATE SET
                alerta_score_datacredito_bajo = excluded.alerta_score_datacredito_bajo,
                umbral_score_datacredito = excluded.umbral_score_datacredito,
                alerta_dti_alto = excluded.alerta_dti_alto,
                umbral_dti = excluded.umbral_dti,
                alerta_consultas_excesivas = excluded.alerta_consultas_excesivas,
                umbral_consultas = excluded.umbral_consultas,
                alerta_ingreso_vs_dane = excluded.alerta_ingreso_vs_dane,
                umbral_ingreso_dane_pct = excluded.umbral_ingreso_dane_pct,
                alerta_monto_alto = excluded.alerta_monto_alto,
                umbral_monto_pct = excluded.umbral_monto_pct,
                alerta_sin_historial_loansi = excluded.alerta_sin_historial_loansi,
                alerta_mora_activa = excluded.alerta_mora_activa,
                updated_at = CURRENT_TIMESTAMP
        """, (
            linea_id,
            datos.get("alerta_score_datacredito_bajo", True),
            datos.get("umbral_score_datacredito", 450),
            datos.get("alerta_dti_alto", True),
            datos.get("umbral_dti", 40.0),
            datos.get("alerta_consultas_excesivas", True),
            datos.get("umbral_consultas", 5),
            datos.get("alerta_ingreso_vs_dane", True),
            datos.get("umbral_ingreso_dane_pct", 200.0),
            datos.get("alerta_monto_alto", True),
            datos.get("umbral_monto_pct", 80.0),
            datos.get("alerta_sin_historial_loansi", True),
            datos.get("alerta_mora_activa", True)
        ))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Error guardando alertas config: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# ============================================================================
# EVALUACIÓN DE CRITERIOS BORDERLINE
# ============================================================================

def evaluar_criterios_borderline(caso_data, linea_id):
    """
    Evalúa los criterios borderline para un caso específico.
    
    Args:
        caso_data: Dict con los datos del caso/evaluación
        linea_id: ID de la línea de crédito
        
    Returns:
        dict: Resultado de la evaluación con criterios cumplidos/no cumplidos y alertas
    """
    config = obtener_criterios_borderline(linea_id)
    alertas_config = obtener_alertas_config(linea_id)
    
    criterios_cumplidos = []
    criterios_no_cumplidos = []
    alertas_activas = []
    
    # =========================================================================
    # CATEGORÍA 1: BUREAU (DataCrédito)
    # =========================================================================
    score_dc = caso_data.get("score_datacredito", 0)
    if score_dc >= config["score_datacredito_minimo"]:
        criterios_cumplidos.append({
            "nombre": "Score DataCrédito",
            "valor": score_dc,
            "requerido": config["score_datacredito_minimo"],
            "categoria": "Bureau"
        })
    else:
        criterios_no_cumplidos.append({
            "nombre": "Score DataCrédito",
            "valor": score_dc,
            "requerido": config["score_datacredito_minimo"],
            "categoria": "Bureau"
        })
    
    mora_fin = caso_data.get("mora_financiero_dias", 0)
    if mora_fin <= config["mora_max_financiero_dias"]:
        criterios_cumplidos.append({
            "nombre": "Mora Sector Financiero",
            "valor": f"{mora_fin} días",
            "requerido": f"≤ {config['mora_max_financiero_dias']} días",
            "categoria": "Bureau"
        })
    else:
        criterios_no_cumplidos.append({
            "nombre": "Mora Sector Financiero",
            "valor": f"{mora_fin} días",
            "requerido": f"≤ {config['mora_max_financiero_dias']} días",
            "categoria": "Bureau"
        })
    
    # Mora Telcos ahora se evalúa en COP (monto de deuda) no en días
    mora_tel_cop = caso_data.get("monto_mora_telcos", caso_data.get("mora_telcos", 0))
    try:
        mora_tel_cop = float(str(mora_tel_cop).replace("$", "").replace(",", "").replace(".", "").strip()) if mora_tel_cop else 0
    except (ValueError, TypeError):
        mora_tel_cop = 0
    umbral_telcos = config["mora_max_telcos_dias"]  # Ahora contiene COP, no días
    if mora_tel_cop <= umbral_telcos:
        criterios_cumplidos.append({
            "nombre": "Mora Telecomunicaciones",
            "valor": f"${mora_tel_cop:,.0f}",
            "requerido": f"≤ ${umbral_telcos:,.0f}",
            "categoria": "Bureau"
        })
    else:
        criterios_no_cumplidos.append({
            "nombre": "Mora Telecomunicaciones",
            "valor": f"${mora_tel_cop:,.0f}",
            "requerido": f"≤ ${umbral_telcos:,.0f}",
            "categoria": "Bureau"
        })
    
    consultas = caso_data.get("consultas_60_dias", 0)
    if consultas <= config["consultas_max_60_dias"]:
        criterios_cumplidos.append({
            "nombre": "Consultas (60 días)",
            "valor": consultas,
            "requerido": f"≤ {config['consultas_max_60_dias']}",
            "categoria": "Bureau"
        })
    else:
        criterios_no_cumplidos.append({
            "nombre": "Consultas (60 días)",
            "valor": consultas,
            "requerido": f"≤ {config['consultas_max_60_dias']}",
            "categoria": "Bureau"
        })
    
    # =========================================================================
    # CATEGORÍA 2: CAPACIDAD DE PAGO
    # =========================================================================
    dti = caso_data.get("dti", 0)
    if dti <= config["dti_maximo"]:
        criterios_cumplidos.append({
            "nombre": "DTI (Deuda/Ingreso)",
            "valor": f"{dti}%",
            "requerido": f"≤ {config['dti_maximo']}%",
            "categoria": "Capacidad"
        })
    else:
        criterios_no_cumplidos.append({
            "nombre": "DTI (Deuda/Ingreso)",
            "valor": f"{dti}%",
            "requerido": f"≤ {config['dti_maximo']}%",
            "categoria": "Capacidad"
        })
    
    ingreso = caso_data.get("ingreso_estimado", 0)
    if ingreso >= config["ingreso_minimo"]:
        criterios_cumplidos.append({
            "nombre": "Ingreso Estimado",
            "valor": f"${ingreso:,.0f}",
            "requerido": f"≥ ${config['ingreso_minimo']:,.0f}",
            "categoria": "Capacidad"
        })
    else:
        criterios_no_cumplidos.append({
            "nombre": "Ingreso Estimado",
            "valor": f"${ingreso:,.0f}",
            "requerido": f"≥ ${config['ingreso_minimo']:,.0f}",
            "categoria": "Capacidad"
        })
    
    # =========================================================================
    # EVALUAR ALERTAS
    # =========================================================================
    if alertas_config:
        # Alerta Score DataCrédito bajo
        if alertas_config["alerta_score_datacredito_bajo"]:
            if score_dc < alertas_config["umbral_score_datacredito"]:
                alertas_activas.append({
                    "tipo": "score_datacredito",
                    "mensaje": f"Score DataCrédito bajo: {score_dc}",
                    "severidad": "alta"
                })
        
        # Alerta DTI alto
        if alertas_config["alerta_dti_alto"]:
            if dti > alertas_config["umbral_dti"]:
                alertas_activas.append({
                    "tipo": "dti",
                    "mensaje": f"DTI alto: {dti}%",
                    "severidad": "media"
                })
        
        # Alerta consultas excesivas
        if alertas_config["alerta_consultas_excesivas"]:
            if consultas > alertas_config["umbral_consultas"]:
                alertas_activas.append({
                    "tipo": "consultas",
                    "mensaje": f"Consultas excesivas: {consultas} en 60 días",
                    "severidad": "media"
                })
        
        # Alerta mora activa
        if alertas_config["alerta_mora_activa"]:
            if mora_fin > 0 or mora_tel_cop > 0:
                alertas_activas.append({
                    "tipo": "mora",
                    "mensaje": f"Mora activa detectada (Fin: {mora_fin}d, Tel: ${mora_tel_cop:,.0f})",
                    "severidad": "alta"
                })
        
        # Alerta sin historial Loansi
        if alertas_config["alerta_sin_historial_loansi"]:
            creditos_loansi = caso_data.get("creditos_loansi", 0)
            if creditos_loansi == 0:
                alertas_activas.append({
                    "tipo": "sin_historial",
                    "mensaje": "Primera solicitud con Loansi",
                    "severidad": "baja"
                })
    
    return {
        "criterios_cumplidos": criterios_cumplidos,
        "criterios_no_cumplidos": criterios_no_cumplidos,
        "alertas_activas": alertas_activas,
        "total_cumplidos": len(criterios_cumplidos),
        "total_no_cumplidos": len(criterios_no_cumplidos),
        "total_alertas": len(alertas_activas),
        "pct_cumplimiento": round(len(criterios_cumplidos) / max(1, len(criterios_cumplidos) + len(criterios_no_cumplidos)) * 100, 1)
    }


# ============================================================================
# ALERTAS DINÁMICAS (basadas en criterios de scoring)
# ============================================================================

def obtener_alertas_dinamicas(linea_id):
    """
    Obtiene alertas dinámicas para una línea, haciendo merge entre los criterios
    de scoring activos y las alertas guardadas en comite_alertas_dinamicas.
    
    Args:
        linea_id: ID de la línea de crédito
        
    Returns:
        list: Lista de alertas con estructura:
              [{criterio_codigo, nombre, tipo_campo, seccion, habilitada, 
                valor_umbral, operador, valor_alerta, rangos}]
    """
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.resolve()
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    from db_helpers_scoring_linea import obtener_config_scoring_linea
    
    # 1. Obtener criterios activos de scoring de esta línea
    scoring_config = obtener_config_scoring_linea(linea_id)
    criterios_scoring = scoring_config.get("criterios", []) if scoring_config else []
    
    # 2. Obtener alertas guardadas en DB
    conn = get_db_connection()
    cursor = conn.cursor()
    alertas_guardadas = {}
    
    try:
        cursor.execute("""
            SELECT criterio_codigo, habilitada, valor_umbral, operador, valor_alerta
            FROM comite_alertas_dinamicas
            WHERE linea_credito_id = ?
        """, (linea_id,))
        
        for row in cursor.fetchall():
            alertas_guardadas[row["criterio_codigo"]] = {
                "habilitada": bool(row["habilitada"]),
                "valor_umbral": row["valor_umbral"],
                "operador": row["operador"] or "<",
                "valor_alerta": row["valor_alerta"]
            }
    except Exception as e:
        print(f"Error obteniendo alertas dinámicas: {e}")
    finally:
        conn.close()
    
    # 3. Merge: criterios activos + estado guardado
    alertas = []
    for criterio in criterios_scoring:
        codigo = criterio.get("codigo")
        if not codigo:
            continue
        
        guardada = alertas_guardadas.get(codigo, {})
        
        alerta = {
            "criterio_codigo": codigo,
            "nombre": criterio.get("nombre", codigo),
            "tipo_campo": criterio.get("tipo_campo", "number"),
            "seccion": criterio.get("seccion", "Sin Categoría"),
            "peso": criterio.get("peso", 0),
            "habilitada": guardada.get("habilitada", False),
            "valor_umbral": guardada.get("valor_umbral"),
            "operador": guardada.get("operador", "<"),
            "valor_alerta": guardada.get("valor_alerta"),
            "rangos": criterio.get("rangos", [])
        }
        alertas.append(alerta)
    
    return alertas


def guardar_alertas_dinamicas(linea_id, alertas_list):
    """
    Guarda la configuración de alertas dinámicas para una línea.
    
    Args:
        linea_id: ID de la línea de crédito
        alertas_list: Lista de dicts con {criterio_codigo, habilitada, valor_umbral, operador, valor_alerta}
        
    Returns:
        bool: True si se guardó correctamente
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        for alerta in alertas_list:
            criterio_codigo = alerta.get("criterio_codigo")
            if not criterio_codigo:
                continue
            
            cursor.execute("""
                INSERT INTO comite_alertas_dinamicas 
                (linea_credito_id, criterio_codigo, habilitada, valor_umbral, operador, valor_alerta, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(linea_credito_id, criterio_codigo) DO UPDATE SET
                    habilitada = excluded.habilitada,
                    valor_umbral = excluded.valor_umbral,
                    operador = excluded.operador,
                    valor_alerta = excluded.valor_alerta,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                linea_id,
                criterio_codigo,
                alerta.get("habilitada", False),
                alerta.get("valor_umbral"),
                alerta.get("operador", "<"),
                alerta.get("valor_alerta")
            ))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Error guardando alertas dinámicas: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# Inicializar tablas al importar el módulo
inicializar_tablas_comite()
