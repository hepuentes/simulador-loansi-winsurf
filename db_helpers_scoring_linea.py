"""
DB_HELPERS_SCORING_LINEA.PY - Funciones para Scoring Multi-Línea
================================================================

Este módulo contiene todas las funciones CRUD para el sistema de
scoring por línea de crédito.

Author: Sistema Loansi
Date: 2026-01-13
Version: 1.0
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

# Importar conexión desde database.py
try:
    from database import conectar_db, DB_PATH
except ImportError:
    DB_PATH = Path(__file__).parent / 'loansi.db'
    
    def conectar_db():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


# ============================================================================
# CACHE PARA OPTIMIZACIÓN
# ============================================================================

_SCORING_LINEA_CACHE = {}
_CACHE_TTL = 300  # 5 minutos


def invalidar_cache_scoring_linea(linea_id=None):
    """
    Invalida el cache de scoring por línea.
    
    Args:
        linea_id: Si se especifica, solo invalida esa línea
    """
    global _SCORING_LINEA_CACHE
    
    if linea_id:
        keys_to_remove = [k for k in _SCORING_LINEA_CACHE if str(linea_id) in k]
        for key in keys_to_remove:
            del _SCORING_LINEA_CACHE[key]
        print(f"🔄 Cache de scoring invalidado para línea {linea_id}")
    else:
        _SCORING_LINEA_CACHE = {}
        print("🔄 Cache de scoring completamente invalidado")


# ============================================================================
# FUNCIONES PARA LÍNEAS DE CRÉDITO CON SCORING
# ============================================================================

def obtener_lineas_credito_scoring():
    """
    Obtiene todas las líneas de crédito con información de scoring.
    
    Returns:
        list: Lista de líneas con configuración de scoring
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT 
                lc.id,
                lc.nombre,
                lc.descripcion,
                lc.monto_min,
                lc.monto_max,
                lc.plazo_min,
                lc.plazo_max,
                lc.activo,
                COALESCE(scl.puntaje_minimo_aprobacion, 17) as puntaje_minimo,
                COALESCE(scl.score_datacredito_minimo, 400) as score_min,
                (SELECT COUNT(*) FROM niveles_riesgo_linea WHERE linea_credito_id = lc.id) as num_niveles,
                (SELECT COUNT(*) FROM factores_rechazo_linea WHERE linea_credito_id = lc.id) as num_factores
            FROM lineas_credito lc
            LEFT JOIN scoring_config_linea scl ON lc.id = scl.linea_credito_id
            WHERE lc.activo = 1
            ORDER BY lc.orden ASC, lc.nombre ASC
        """)
        
        lineas = []
        for row in cursor.fetchall():
            lineas.append({
                "id": row[0],
                "nombre": row[1],
                "descripcion": row[2],
                "monto_min": row[3],
                "monto_max": row[4],
                "plazo_min": row[5],
                "plazo_max": row[6],
                "activo": bool(row[7]),
                "puntaje_minimo": row[8],
                "score_datacredito_minimo": row[9],
                "num_niveles_riesgo": row[10],
                "num_factores_rechazo": row[11],
                "tiene_config_scoring": row[10] > 0
            })
        
        return lineas
        
    except Exception as e:
        print(f"❌ Error obteniendo líneas de crédito: {e}")
        return []
    finally:
        conn.close()


def obtener_linea_credito_por_id(linea_id):
    """
    Obtiene una línea de crédito específica por ID.
    
    Args:
        linea_id: ID de la línea de crédito
        
    Returns:
        dict: Datos de la línea o None
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, nombre, descripcion, monto_min, monto_max,
                   plazo_min, plazo_max, tasa_mensual, tasa_anual,
                   aval_porcentaje, activo
            FROM lineas_credito
            WHERE id = ?
        """, (linea_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "nombre": row[1],
                "descripcion": row[2],
                "monto_min": row[3],
                "monto_max": row[4],
                "plazo_min": row[5],
                "plazo_max": row[6],
                "tasa_mensual": row[7],
                "tasa_anual": row[8],
                "aval_porcentaje": row[9],
                "activo": bool(row[10])
            }
        return None
        
    except Exception as e:
        print(f"❌ Error obteniendo línea {linea_id}: {e}")
        return None
    finally:
        conn.close()


def obtener_linea_credito_por_nombre(nombre):
    """
    Obtiene una línea de crédito por nombre.
    
    Args:
        nombre: Nombre de la línea
        
    Returns:
        dict: Datos de la línea o None
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, nombre, descripcion, monto_min, monto_max,
                   plazo_min, plazo_max, tasa_mensual, tasa_anual,
                   aval_porcentaje, activo
            FROM lineas_credito
            WHERE nombre = ? AND activo = 1
        """, (nombre,))
        
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "nombre": row[1],
                "descripcion": row[2],
                "monto_min": row[3],
                "monto_max": row[4],
                "plazo_min": row[5],
                "plazo_max": row[6],
                "tasa_mensual": row[7],
                "tasa_anual": row[8],
                "aval_porcentaje": row[9],
                "activo": bool(row[10])
            }
        return None
        
    except Exception as e:
        print(f"❌ Error obteniendo línea {nombre}: {e}")
        return None
    finally:
        conn.close()


# ============================================================================
# FUNCIONES PARA CONFIGURACIÓN DE SCORING POR LÍNEA
# ============================================================================

def obtener_config_scoring_linea(linea_id):
    """
    Obtiene la configuración de scoring para una línea específica.
    
    Args:
        linea_id: ID de la línea de crédito
        
    Returns:
        dict: Configuración completa de scoring para la línea
    """
    import time
    cache_key = f"config_{linea_id}"
    now = time.time()
    
    # Verificar cache
    if cache_key in _SCORING_LINEA_CACHE:
        cached_data, timestamp = _SCORING_LINEA_CACHE[cache_key]
        if now - timestamp < _CACHE_TTL:
            return cached_data
    
    conn = conectar_db()
    cursor = conn.cursor()
    
    config = {
        "linea_id": linea_id,
        "config_general": {},
        "niveles_riesgo": [],
        "factores_rechazo": [],
        "criterios": []
    }
    
    print(f"\n🔍 DEBUG obtener_config_scoring_linea(linea_id={linea_id})")
    
    try:
        # 1. Configuración general de scoring + puntaje_revision_manual desde comite_config
        cursor.execute("""
            SELECT 
                scl.*,
                lc.nombre as linea_nombre,
                COALESCE(cc.puntaje_revision_manual, 22) as puntaje_revision_comite
            FROM scoring_config_linea scl
            JOIN lineas_credito lc ON scl.linea_credito_id = lc.id
            LEFT JOIN comite_config cc ON scl.linea_credito_id = cc.linea_credito_id
            WHERE scl.linea_credito_id = ?
        """, (linea_id,))
        
        row = cursor.fetchone()
        if row:
            config["config_general"] = {
                "linea_nombre": row["linea_nombre"],
                "puntaje_minimo_aprobacion": row["puntaje_minimo_aprobacion"],
                # puntaje_revision_manual ahora viene de comite_config (fuente única)
                "puntaje_revision_manual": row["puntaje_revision_comite"],
                "umbral_mora_telcos": row["umbral_mora_telcos"],
                "edad_minima": row["edad_minima"],
                "edad_maxima": row["edad_maxima"],
                "dti_maximo": row["dti_maximo"],
                "score_datacredito_minimo": row["score_datacredito_minimo"],
                "consultas_max_3meses": row["consultas_max_3meses"],
                "escala_max": row["escala_max"]
            }
        else:
            # Valores por defecto si no existe configuración
            cursor.execute("SELECT nombre FROM lineas_credito WHERE id = ?", (linea_id,))
            nombre_row = cursor.fetchone()
            config["config_general"] = {
                "linea_nombre": nombre_row[0] if nombre_row else "Sin nombre",
                "puntaje_minimo_aprobacion": 38,
                "puntaje_revision_manual": 22,
                "umbral_mora_telcos": 200000,
                "edad_minima": 18,
                "edad_maxima": 84,
                "dti_maximo": 50,
                "score_datacredito_minimo": 400,
                "consultas_max_3meses": 8,
                "escala_max": 45
            }
        
        # 2. Niveles de riesgo (incluir campos de interpolación)
        cursor.execute("""
            SELECT id, nombre, codigo, score_min, score_max,
                   tasa_ea, tasa_nominal_mensual, aval_porcentaje,
                   color, orden, activo,
                   tasa_ea_at_min, tasa_ea_at_max, aval_at_min, aval_at_max,
                   interpolacion_activa
            FROM niveles_riesgo_linea
            WHERE linea_credito_id = ? AND activo = 1
            ORDER BY orden, score_min DESC
        """, (linea_id,))
        
        for row in cursor.fetchall():
            config["niveles_riesgo"].append({
                "id": row[0],
                "nombre": row[1],
                "codigo": row[2],
                "min": row[3],
                "max": row[4],
                "tasa_ea": row[5],
                "tasa_nominal_mensual": row[6],
                "aval_porcentaje": row[7],
                "color": row[8],
                "orden": row[9],
                "tasa_ea_at_min": row[11] or row[5],
                "tasa_ea_at_max": row[12] or row[5],
                "aval_at_min": row[13] or row[7],
                "aval_at_max": row[14] or row[7],
                "interpolacion_activa": bool(row[15]) if row[15] is not None else False
            })
        
        # 3. Factores de rechazo (con soporte para tipo selección)
        _asegurar_columnas_factores(cursor, conn)
        cursor.execute("""
            SELECT id, criterio_codigo, criterio_nombre, operador,
                   valor_umbral, mensaje_rechazo, activo, orden,
                   tipo_factor, opciones_json
            FROM factores_rechazo_linea
            WHERE linea_credito_id = ? AND activo = 1
            ORDER BY orden
        """, (linea_id,))
        
        for row in cursor.fetchall():
            tipo_factor = row[8] or 'numerico'
            opciones = []
            if row[9]:
                try:
                    opciones = json.loads(row[9])
                except (json.JSONDecodeError, TypeError):
                    pass
            config["factores_rechazo"].append({
                "id": row[0],
                "criterio": row[1],
                "criterio_nombre": row[2],
                "operador": row[3],
                "valor": row[4],
                "mensaje": row[5],
                "activo": bool(row[6]),
                "tipo_factor": tipo_factor,
                "opciones": opciones
            })
        
        # 4. Criterios con configuración por línea (devuelve array para el frontend)
        config["criterios"] = []
        
        # Verificar columnas disponibles
        cursor.execute("PRAGMA table_info(criterios_linea_credito)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Crear columnas faltantes
        for col_name in ['color_context', 'seccion_icono', 'seccion_descripcion', 'seccion_orden']:
            if col_name not in columns:
                try:
                    cursor.execute(f"ALTER TABLE criterios_linea_credito ADD COLUMN {col_name} TEXT DEFAULT NULL")
                    conn.commit()
                    print(f"✅ Columna '{col_name}' agregada a criterios_linea_credito")
                    columns.append(col_name)
                except Exception:
                    pass
        
        has_meta_columns = all(c in columns for c in ['color_context', 'seccion_icono', 'seccion_descripcion', 'seccion_orden'])
        
        # Construir query con todas las columnas de metadatos
        if has_meta_columns:
            cursor.execute("""
                SELECT 
                    csm.codigo,
                    csm.nombre,
                    csm.descripcion,
                    csm.tipo_campo,
                    COALESCE(clc.seccion, 'Sin Categoría') as seccion,
                    clc.peso,
                    clc.activo,
                    clc.orden,
                    clc.rangos_json,
                    clc.color_context,
                    clc.seccion_icono,
                    clc.seccion_descripcion,
                    clc.seccion_orden,
                    csm.fuente_extraccion,
                    csm.instruccion_extraccion,
                    csm.activo_extraccion
                FROM criterios_scoring_master csm
                INNER JOIN criterios_linea_credito clc 
                    ON csm.id = clc.criterio_master_id AND clc.linea_credito_id = ?
                WHERE csm.activo = 1 AND clc.activo = 1
                ORDER BY COALESCE(clc.orden, csm.id)
            """, (linea_id,))
        else:
            cursor.execute("""
                SELECT 
                    csm.codigo,
                    csm.nombre,
                    csm.descripcion,
                    csm.tipo_campo,
                    COALESCE(clc.seccion, 'Sin Categoría') as seccion,
                    clc.peso,
                    clc.activo,
                    clc.orden,
                    clc.rangos_json,
                    csm.fuente_extraccion,
                    csm.instruccion_extraccion,
                    csm.activo_extraccion
                FROM criterios_scoring_master csm
                INNER JOIN criterios_linea_credito clc 
                    ON csm.id = clc.criterio_master_id AND clc.linea_credito_id = ?
                WHERE csm.activo = 1 AND clc.activo = 1
                ORDER BY COALESCE(clc.orden, csm.id)
            """, (linea_id,))
        
        for row in cursor.fetchall():
            rangos = []
            if row[8]:
                try:
                    rangos = json.loads(row[8])
                except:
                    pass
            
            # Índices de campos de extracción dependen de si hay meta_columns
            # Con meta: 9-12 = meta, 13-15 = extracción
            # Sin meta: 9-11 = extracción
            ext_offset = 13 if has_meta_columns else 9
            
            criterio_data = {
                "codigo": row[0],
                "nombre": row[1],
                "descripcion": row[2],
                "tipo_campo": row[3],
                "seccion": row[4] or "Sin Categoría",
                "peso": row[5] or 5,
                "activo": bool(row[6]) if row[6] is not None else True,
                "orden": row[7] or 0,
                "rangos": rangos,
                "color_context": row[9] if has_meta_columns and len(row) > 9 else None,
                "seccion_icono": row[10] if has_meta_columns and len(row) > 10 else None,
                "seccion_descripcion": row[11] if has_meta_columns and len(row) > 11 else None,
                "seccion_orden": row[12] if has_meta_columns and len(row) > 12 else None,
                "fuente_extraccion": row[ext_offset] if len(row) > ext_offset else None,
                "instruccion_extraccion": row[ext_offset + 1] if len(row) > ext_offset + 1 else None,
                "activo_extraccion": int(row[ext_offset + 2]) if len(row) > ext_offset + 2 and row[ext_offset + 2] else 0
            }
            config["criterios"].append(criterio_data)
        
        # DEBUG: Print first 3 criterios for verification
        print(f"   📊 Criterios cargados: {len(config['criterios'])}")
        for i, c in enumerate(config['criterios'][:3]):
            print(f"      [{i}] {c['codigo']}: seccion='{c['seccion']}', peso={c['peso']}, icono={c.get('seccion_icono')}, orden={c.get('seccion_orden')}")
        
        # Guardar en cache
        _SCORING_LINEA_CACHE[cache_key] = (config, now)
        
        return config
        
    except Exception as e:
        print(f"❌ Error obteniendo config scoring línea {linea_id}: {e}")
        import traceback
        traceback.print_exc()
        return config
    finally:
        conn.close()


def guardar_config_scoring_linea(linea_id, config):
    """
    Guarda la configuración de scoring para una línea.
    
    Args:
        linea_id: ID de la línea de crédito
        config: dict con la configuración
        
    Returns:
        bool: True si se guardó exitosamente
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        # 1. Guardar/actualizar configuración general
        if "config_general" in config:
            cg = config["config_general"]
            cursor.execute("""
                INSERT OR REPLACE INTO scoring_config_linea
                (linea_credito_id, puntaje_minimo_aprobacion, puntaje_revision_manual,
                 umbral_mora_telcos, edad_minima, edad_maxima, dti_maximo,
                 score_datacredito_minimo, consultas_max_3meses, escala_max,
                 activo, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            """, (
                linea_id,
                cg.get("puntaje_minimo_aprobacion", 17),
                cg.get("puntaje_revision_manual", 10),
                cg.get("umbral_mora_telcos", 200000),
                cg.get("edad_minima", 18),
                cg.get("edad_maxima", 84),
                cg.get("dti_maximo", 50),
                cg.get("score_datacredito_minimo", 400),
                cg.get("consultas_max_3meses", 8),
                cg.get("escala_max", 45)
            ))
            print(f"✅ Configuración general guardada para línea {linea_id}")
        
        conn.commit()
        
        # Invalidar cache
        invalidar_cache_scoring_linea(linea_id)
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error guardando config scoring: {e}")
        return False
    finally:
        conn.close()


# ============================================================================
# CREAR CONFIGURACIÓN DE SCORING POR DEFECTO PARA NUEVA LÍNEA
# ============================================================================

def crear_config_scoring_linea_defecto(linea_id, tasa_anual=25.0, copiar_de_linea_id=None):
    """
    Crea la configuración de scoring por defecto para una nueva línea de crédito.
    
    Esta función se llama automáticamente cuando se crea una nueva línea de crédito.
    Crea:
    - Configuración general con valores por defecto
    - 3 niveles de riesgo (Bajo Riesgo, Moderado, Alto Riesgo)
    - Factores de rechazo básicos
    
    Args:
        linea_id: ID de la línea de crédito recién creada
        tasa_anual: Tasa anual base para calcular las tasas de niveles
        copiar_de_linea_id: Si se especifica, copia la configuración de otra línea
        
    Returns:
        bool: True si se creó exitosamente
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        # Si se especifica copiar de otra línea, usar esa función
        if copiar_de_linea_id:
            conn.close()
            return copiar_config_scoring(copiar_de_linea_id, linea_id)
        
        # Verificar que la línea existe
        cursor.execute("SELECT nombre FROM lineas_credito WHERE id = ?", (linea_id,))
        linea = cursor.fetchone()
        if not linea:
            print(f"❌ Línea {linea_id} no existe")
            return False
        
        nombre_linea = linea[0]
        print(f"🔧 Creando configuración de scoring para nueva línea: {nombre_linea} (ID: {linea_id})")
        
        # 1. Crear configuración general
        cursor.execute("""
            INSERT OR REPLACE INTO scoring_config_linea
            (linea_credito_id, puntaje_minimo_aprobacion, puntaje_revision_manual,
             umbral_mora_telcos, edad_minima, edad_maxima, dti_maximo,
             score_datacredito_minimo, consultas_max_3meses, escala_max,
             activo, updated_at)
            VALUES (?, 17, 10, 200000, 18, 65, 50, 400, 8, 100, 1, CURRENT_TIMESTAMP)
        """, (linea_id,))
        print(f"  ✅ Configuración general creada")
        
        # 2. Crear niveles de riesgo por defecto
        # Calcular tasas basadas en la tasa anual de la línea
        niveles_defecto = [
            {
                "nombre": "Bajo Riesgo",
                "codigo": "bajo_riesgo",
                "score_min": 70.1,
                "score_max": 100.0,
                "tasa_ea": tasa_anual,  # Tasa base
                "aval_porcentaje": 0.065,
                "color": "#28a745",
                "orden": 1
            },
            {
                "nombre": "Moderado",
                "codigo": "moderado",
                "score_min": 55.1,
                "score_max": 70.0,
                "tasa_ea": tasa_anual + 3,  # Tasa base + 3%
                "aval_porcentaje": 0.10,
                "color": "#ffc107",
                "orden": 2
            },
            {
                "nombre": "Alto Riesgo",
                "codigo": "alto_riesgo",
                "score_min": 0.0,
                "score_max": 55.0,
                "tasa_ea": tasa_anual + 8,  # Tasa base + 8%
                "aval_porcentaje": 0.15,
                "color": "#dc3545",
                "orden": 3
            }
        ]
        
        for nivel in niveles_defecto:
            # Calcular tasa nominal mensual: ((1 + tasa_ea/100)^(1/12) - 1) * 100
            tasa_ea = nivel["tasa_ea"]
            tasa_nominal = (pow(1 + tasa_ea/100, 1/12) - 1) * 100
            
            cursor.execute("""
                INSERT INTO niveles_riesgo_linea
                (linea_credito_id, nombre, codigo, score_min, score_max,
                 tasa_ea, tasa_nominal_mensual, aval_porcentaje, color, orden, activo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                linea_id,
                nivel["nombre"],
                nivel["codigo"],
                nivel["score_min"],
                nivel["score_max"],
                nivel["tasa_ea"],
                round(tasa_nominal, 4),
                nivel["aval_porcentaje"],
                nivel["color"],
                nivel["orden"]
            ))
        print(f"  ✅ {len(niveles_defecto)} niveles de riesgo creados")
        
        # 3. Crear factores de rechazo básicos
        factores_defecto = [
            ("score_datacredito", "Score DataCrédito", "<", 400, "Score DataCrédito inferior al mínimo requerido"),
            ("mora_sector_financiero", "Mora activa sector financiero", ">", 30, "Presenta mora activa en el sector financiero"),
            ("mora_sector_telcos", "Mora Sector Telcos (COP)", ">", 200000, "Mora en telecomunicaciones superior a $200.000"),
            ("dti", "Relación deuda/ingreso (DTI)", ">", 50, "Nivel de endeudamiento superior al 50%"),
            ("consultas_3meses", "Consultas últimos 3 meses", ">", 8, "Exceso de consultas crediticias"),
            ("edad", "Edad del solicitante", "<", 18, f"Edad mínima 18 años para {nombre_linea}"),
            ("edad", "Edad del solicitante", ">", 65, f"Edad máxima 65 años para {nombre_linea}"),
        ]
        
        for i, (criterio, nombre, operador, valor, mensaje) in enumerate(factores_defecto):
            cursor.execute("""
                INSERT INTO factores_rechazo_linea
                (linea_credito_id, criterio_codigo, criterio_nombre, operador,
                 valor_umbral, mensaje_rechazo, activo, orden)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """, (linea_id, criterio, nombre, operador, valor, mensaje, i + 1))
        print(f"  ✅ {len(factores_defecto)} factores de rechazo creados")
        
        conn.commit()
        
        # Invalidar cache
        invalidar_cache_scoring_linea(linea_id)
        
        print(f"✅ Configuración de scoring completa creada para {nombre_linea}")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error creando config scoring por defecto: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


# ============================================================================
# FUNCIONES PARA NIVELES DE RIESGO POR LÍNEA
# ============================================================================

def obtener_niveles_riesgo_linea(linea_id):
    """
    Obtiene los niveles de riesgo para una línea.
    
    Args:
        linea_id: ID de la línea de crédito
        
    Returns:
        list: Lista de niveles de riesgo
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, nombre, codigo, score_min, score_max,
                   tasa_ea, tasa_nominal_mensual, aval_porcentaje,
                   color, orden, activo,
                   tasa_ea_at_min, tasa_ea_at_max, aval_at_min, aval_at_max,
                   interpolacion_activa
            FROM niveles_riesgo_linea
            WHERE linea_credito_id = ?
            ORDER BY orden, score_min DESC
        """, (linea_id,))
        
        niveles = []
        for row in cursor.fetchall():
            niveles.append({
                "id": row[0],
                "nombre": row[1],
                "codigo": row[2],
                "min": row[3],
                "max": row[4],
                "tasa_ea": row[5],
                "tasa_nominal_mensual": row[6],
                "aval_porcentaje": row[7],
                "color": row[8],
                "orden": row[9],
                "activo": bool(row[10]),
                "tasa_ea_at_min": row[11] or row[5],
                "tasa_ea_at_max": row[12] or row[5],
                "aval_at_min": row[13] or row[7],
                "aval_at_max": row[14] or row[7],
                "interpolacion_activa": bool(row[15]) if row[15] is not None else False
            })
        
        return niveles
        
    except Exception as e:
        print(f"❌ Error obteniendo niveles de riesgo: {e}")
        return []
    finally:
        conn.close()


def guardar_niveles_riesgo_linea(linea_id, niveles):
    """
    Guarda los niveles de riesgo para una línea.
    
    Args:
        linea_id: ID de la línea de crédito
        niveles: Lista de niveles de riesgo
        
    Returns:
        bool: True si se guardó exitosamente
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        # Eliminar niveles existentes
        cursor.execute("""
            DELETE FROM niveles_riesgo_linea WHERE linea_credito_id = ?
        """, (linea_id,))
        
        # Insertar nuevos niveles
        for i, nivel in enumerate(niveles):
            tasa_ea = nivel.get("tasa_ea", 24.0)
            aval = nivel.get("aval_porcentaje", 0.10)
            
            cursor.execute("""
                INSERT INTO niveles_riesgo_linea
                (linea_credito_id, nombre, codigo, score_min, score_max,
                 tasa_ea, tasa_nominal_mensual, aval_porcentaje,
                 color, orden, activo,
                 tasa_ea_at_min, tasa_ea_at_max, aval_at_min, aval_at_max,
                 interpolacion_activa)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
            """, (
                linea_id,
                nivel.get("nombre", f"Nivel {i+1}"),
                nivel.get("codigo", f"N{i+1}"),
                nivel.get("min", 0),
                nivel.get("max", 100),
                tasa_ea,
                nivel.get("tasa_nominal_mensual", 1.81),
                aval,
                nivel.get("color", "#FF4136"),
                nivel.get("orden", i),
                nivel.get("tasa_ea_at_min", tasa_ea),
                nivel.get("tasa_ea_at_max", tasa_ea),
                nivel.get("aval_at_min", aval),
                nivel.get("aval_at_max", aval),
                1 if nivel.get("interpolacion_activa") else 0
            ))
        
        conn.commit()
        invalidar_cache_scoring_linea(linea_id)
        
        print(f"✅ {len(niveles)} niveles de riesgo guardados para línea {linea_id}")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error guardando niveles de riesgo: {e}")
        return False
    finally:
        conn.close()


# ============================================================================
# FUNCIONES PARA FACTORES DE RECHAZO POR LÍNEA
# ============================================================================

def _asegurar_columnas_factores(cursor, conn):
    """
    Migración automática: asegura que existan las columnas
    tipo_factor y opciones_json en factores_rechazo_linea.
    """
    for col_name, col_default in [('tipo_factor', "'numerico'"), ('opciones_json', 'NULL')]:
        try:
            cursor.execute(f"ALTER TABLE factores_rechazo_linea ADD COLUMN {col_name} TEXT DEFAULT {col_default}")
            conn.commit()
            print(f"✅ Columna '{col_name}' agregada a factores_rechazo_linea")
        except Exception:
            pass  # Ya existe


def obtener_factores_rechazo_linea(linea_id):
    """
    Obtiene los factores de rechazo para una línea.
    Soporta tipo 'numerico' (operador+valor) y 'seleccion' (opciones).
    
    Args:
        linea_id: ID de la línea de crédito
        
    Returns:
        list: Lista de factores de rechazo
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        _asegurar_columnas_factores(cursor, conn)
        
        cursor.execute("""
            SELECT id, criterio_codigo, criterio_nombre, operador,
                   valor_umbral, mensaje_rechazo, activo, orden,
                   tipo_factor, opciones_json
            FROM factores_rechazo_linea
            WHERE linea_credito_id = ?
            ORDER BY orden
        """, (linea_id,))
        
        factores = []
        for row in cursor.fetchall():
            tipo_factor = row[8] or 'numerico'
            opciones_raw = row[9]
            opciones = []
            if opciones_raw:
                try:
                    opciones = json.loads(opciones_raw)
                except (json.JSONDecodeError, TypeError):
                    pass
            
            factores.append({
                "id": row[0],
                "criterio": row[1],
                "criterio_nombre": row[2],
                "operador": row[3],
                "valor": row[4],
                "mensaje": row[5],
                "activo": bool(row[6]),
                "orden": row[7],
                "tipo_factor": tipo_factor,
                "opciones": opciones
            })
        
        return factores
        
    except Exception as e:
        print(f"❌ Error obteniendo factores de rechazo: {e}")
        return []
    finally:
        conn.close()


def guardar_factores_rechazo_linea(linea_id, factores):
    """
    Guarda los factores de rechazo para una línea.
    Soporta tipo 'numerico' y 'seleccion'.
    
    Args:
        linea_id: ID de la línea de crédito
        factores: Lista de factores de rechazo
        
    Returns:
        bool: True si se guardó exitosamente
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        _asegurar_columnas_factores(cursor, conn)
        
        # Eliminar factores existentes
        cursor.execute("""
            DELETE FROM factores_rechazo_linea WHERE linea_credito_id = ?
        """, (linea_id,))
        
        # Insertar nuevos factores
        for i, factor in enumerate(factores):
            tipo_factor = factor.get("tipo_factor", "numerico")
            opciones = factor.get("opciones", [])
            opciones_json = json.dumps(opciones, ensure_ascii=False) if opciones else None
            
            cursor.execute("""
                INSERT INTO factores_rechazo_linea
                (linea_credito_id, criterio_codigo, criterio_nombre, operador,
                 valor_umbral, mensaje_rechazo, activo, orden, tipo_factor, opciones_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                linea_id,
                factor.get("criterio", ""),
                factor.get("criterio_nombre", ""),
                factor.get("operador", "<"),
                factor.get("valor", 0),
                factor.get("mensaje", ""),
                1 if factor.get("activo", True) else 0,
                factor.get("orden", i),
                tipo_factor,
                opciones_json
            ))
        
        conn.commit()
        invalidar_cache_scoring_linea(linea_id)
        
        print(f"✅ {len(factores)} factores de rechazo guardados para línea {linea_id}")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error guardando factores de rechazo: {e}")
        return False
    finally:
        conn.close()


def agregar_factor_rechazo_linea(linea_id, factor):
    """
    Agrega un nuevo factor de rechazo a una línea.
    
    Args:
        linea_id: ID de la línea de crédito
        factor: dict con datos del factor
        
    Returns:
        int: ID del factor creado o None
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        # Obtener siguiente orden
        cursor.execute("""
            SELECT COALESCE(MAX(orden), -1) + 1 FROM factores_rechazo_linea
            WHERE linea_credito_id = ?
        """, (linea_id,))
        nuevo_orden = cursor.fetchone()[0]
        
        cursor.execute("""
            INSERT INTO factores_rechazo_linea
            (linea_credito_id, criterio_codigo, criterio_nombre, operador,
             valor_umbral, mensaje_rechazo, activo, orden)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            linea_id,
            factor.get("criterio", ""),
            factor.get("criterio_nombre", ""),
            factor.get("operador", "<"),
            factor.get("valor", 0),
            factor.get("mensaje", ""),
            nuevo_orden
        ))
        
        factor_id = cursor.lastrowid
        conn.commit()
        invalidar_cache_scoring_linea(linea_id)
        
        return factor_id
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error agregando factor de rechazo: {e}")
        return None
    finally:
        conn.close()


def eliminar_factor_rechazo(factor_id):
    """
    Elimina un factor de rechazo.
    
    Args:
        factor_id: ID del factor a eliminar
        
    Returns:
        bool: True si se eliminó exitosamente
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        # Obtener linea_id antes de eliminar (para invalidar cache)
        cursor.execute("""
            SELECT linea_credito_id FROM factores_rechazo_linea WHERE id = ?
        """, (factor_id,))
        row = cursor.fetchone()
        linea_id = row[0] if row else None
        
        cursor.execute("""
            DELETE FROM factores_rechazo_linea WHERE id = ?
        """, (factor_id,))
        
        conn.commit()
        
        if linea_id:
            invalidar_cache_scoring_linea(linea_id)
        
        return cursor.rowcount > 0
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error eliminando factor de rechazo: {e}")
        return False
    finally:
        conn.close()


# ============================================================================
# FUNCIONES PARA CRITERIOS POR LÍNEA
# ============================================================================

def obtener_criterios_linea(linea_id):
    """
    Obtiene los criterios configurados para una línea.
    
    Args:
        linea_id: ID de la línea de crédito
        
    Returns:
        dict: Diccionario de criterios con sus configuraciones
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        # Verificar si existe la columna seccion
        cursor.execute("PRAGMA table_info(criterios_linea_credito)")
        columnas = [col[1] for col in cursor.fetchall()]
        tiene_seccion = 'seccion' in columnas
        
        if tiene_seccion:
            cursor.execute("""
                SELECT 
                    csm.codigo,
                    csm.nombre,
                    csm.descripcion,
                    csm.tipo_campo,
                    csm.seccion_id,
                    COALESCE(clc.peso, 5) as peso,
                    COALESCE(clc.activo, 1) as activo,
                    COALESCE(clc.orden, csm.id) as orden,
                    clc.rangos_json,
                    COALESCE(clc.seccion, 'Sin Categoría') as seccion
                FROM criterios_scoring_master csm
                LEFT JOIN criterios_linea_credito clc 
                    ON csm.id = clc.criterio_master_id AND clc.linea_credito_id = ?
                WHERE csm.activo = 1
                ORDER BY orden
            """, (linea_id,))
        else:
            cursor.execute("""
                SELECT 
                    csm.codigo,
                    csm.nombre,
                    csm.descripcion,
                    csm.tipo_campo,
                    csm.seccion_id,
                    COALESCE(clc.peso, 5) as peso,
                    COALESCE(clc.activo, 1) as activo,
                    COALESCE(clc.orden, csm.id) as orden,
                    clc.rangos_json
                FROM criterios_scoring_master csm
                LEFT JOIN criterios_linea_credito clc 
                    ON csm.id = clc.criterio_master_id AND clc.linea_credito_id = ?
                WHERE csm.activo = 1
                ORDER BY orden
            """, (linea_id,))
        
        criterios = {}
        for row in cursor.fetchall():
            rangos = []
            if row[8]:
                try:
                    rangos = json.loads(row[8])
                except:
                    pass
            
            criterios[row[0]] = {
                "nombre": row[1],
                "descripcion": row[2],
                "tipo_campo": row[3],
                "seccion_id": row[4],
                "peso": row[5],
                "activo": bool(row[6]),
                "orden": row[7],
                "rangos": rangos,
                "seccion": row[9] if tiene_seccion and len(row) > 9 else "Sin Categoría"
            }
        
        return criterios
        
    except Exception as e:
        print(f"❌ Error obteniendo criterios: {e}")
        return {}
    finally:
        conn.close()


def guardar_criterio_linea(linea_id, criterio_codigo, config):
    """
    Guarda la configuración de un criterio para una línea.
    
    Args:
        linea_id: ID de la línea de crédito
        criterio_codigo: Código del criterio
        config: dict con la configuración del criterio
        
    Returns:
        bool: True si se guardó exitosamente
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        # Obtener ID del criterio master
        cursor.execute("""
            SELECT id FROM criterios_scoring_master WHERE codigo = ?
        """, (criterio_codigo,))
        row = cursor.fetchone()
        
        if not row:
            print(f"❌ Criterio {criterio_codigo} no encontrado en catálogo master")
            return False
        
        criterio_master_id = row[0]
        
        # Serializar rangos
        rangos_json = json.dumps(config.get("rangos", []), ensure_ascii=False)
        
        # Insertar o actualizar
        cursor.execute("""
            INSERT OR REPLACE INTO criterios_linea_credito
            (criterio_master_id, linea_credito_id, peso, activo, orden, rangos_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            criterio_master_id,
            linea_id,
            config.get("peso", 5),
            1 if config.get("activo", True) else 0,
            config.get("orden", 0),
            rangos_json
        ))
        
        conn.commit()
        invalidar_cache_scoring_linea(linea_id)
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error guardando criterio: {e}")
        return False
    finally:
        conn.close()


def guardar_criterios_completos_linea(linea_id, criterios):
    """
    Guarda todos los criterios de scoring para una línea.
    Maneja criterios como objetos completos con nombre, peso, rangos y sección.
    
    Args:
        linea_id: ID de la línea de crédito
        criterios: Lista de criterios con formato:
                   [{"codigo": "...", "nombre": "...", "peso": N, "seccion": "...", "rangos": [...]}]
        
    Returns:
        bool: True si se guardó exitosamente
    """
    print(f"\n🔧 DEBUG guardar_criterios_completos_linea(linea_id={linea_id})")
    print(f"   📥 Recibidos {len(criterios) if criterios else 0} criterios")
    
    # DEBUG: Show first 3 criterios received
    if criterios:
        for i, c in enumerate(criterios[:3]):
            print(f"      [{i}] {c.get('codigo')}: seccion='{c.get('seccion', 'N/A')}', peso={c.get('peso')}")
    
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        # Asegurar que existe la columna 'seccion' (migración automática)
        try:
            cursor.execute("ALTER TABLE criterios_linea_credito ADD COLUMN seccion TEXT DEFAULT 'Sin Categoría'")
            conn.commit()
            print("✅ Columna 'seccion' agregada a criterios_linea_credito")
        except Exception:
            # La columna ya existe, ignorar
            pass
        
        # Asegurar que existe la columna 'color_context' para colores de sección
        try:
            cursor.execute("ALTER TABLE criterios_linea_credito ADD COLUMN color_context TEXT DEFAULT NULL")
            conn.commit()
            print("✅ Columna 'color_context' agregada a criterios_linea_credito")
        except Exception:
            pass
        
        # Asegurar que existen las columnas para metadatos de sección
        for col_name in ['seccion_icono', 'seccion_descripcion', 'seccion_orden']:
            try:
                cursor.execute(f"ALTER TABLE criterios_linea_credito ADD COLUMN {col_name} TEXT DEFAULT NULL")
                conn.commit()
                print(f"✅ Columna '{col_name}' agregada a criterios_linea_credito")
            except Exception:
                pass
        
        # CRITICAL FIX: Eliminar criterios existentes antes de insertar los nuevos
        # Esto asegura que criterios eliminados por el usuario no persistan
        cursor.execute("""
            DELETE FROM criterios_linea_credito WHERE linea_credito_id = ?
        """, (linea_id,))
        print(f"   🗑️ Criterios anteriores eliminados para línea {linea_id}")
        
        # Primero, asegurar que existen los criterios en el catálogo master
        for i, criterio in enumerate(criterios):
            codigo = criterio.get("codigo", f"criterio_{i}")
            nombre = criterio.get("nombre", f"Criterio {i+1}")
            descripcion = criterio.get("descripcion", "")
            tipo_campo = criterio.get("tipo_campo", "numerico")
            seccion = criterio.get("seccion", "Sin Categoría")
            orden = criterio.get("orden", i)
            
            # Verificar si existe en master, si no, crearlo
            cursor.execute("SELECT id FROM criterios_scoring_master WHERE codigo = ?", (codigo,))
            row = cursor.fetchone()
            
            if row:
                master_id = row[0]
                # Actualizar nombre, descripción y campos de extracción
                fuente_ext = criterio.get("fuente_extraccion", None)
                instruccion_ext = criterio.get("instruccion_extraccion", None)
                activo_ext = 1 if criterio.get("activo_extraccion") else 0
                cursor.execute("""
                    UPDATE criterios_scoring_master 
                    SET nombre = ?, descripcion = ?, tipo_campo = ?,
                        fuente_extraccion = ?, instruccion_extraccion = ?, activo_extraccion = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (nombre, descripcion, tipo_campo, fuente_ext, instruccion_ext, activo_ext, master_id))
            else:
                # Crear nuevo criterio en master
                fuente_ext = criterio.get("fuente_extraccion", None)
                instruccion_ext = criterio.get("instruccion_extraccion", None)
                activo_ext = 1 if criterio.get("activo_extraccion") else 0
                cursor.execute("""
                    INSERT INTO criterios_scoring_master 
                    (codigo, nombre, descripcion, tipo_campo, activo,
                     fuente_extraccion, instruccion_extraccion, activo_extraccion)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                """, (codigo, nombre, descripcion, tipo_campo, fuente_ext, instruccion_ext, activo_ext))
                master_id = cursor.lastrowid
            
            # Guardar configuración del criterio para la línea (con sección, color y metadatos)
            rangos_json = json.dumps(criterio.get("rangos", []), ensure_ascii=False)
            color_context = criterio.get("color_context", None)
            seccion_icono = criterio.get("seccion_icono", None)
            seccion_descripcion = criterio.get("seccion_descripcion", None)
            seccion_orden = criterio.get("seccion_orden", None)
            
            cursor.execute("""
                INSERT OR REPLACE INTO criterios_linea_credito
                (criterio_master_id, linea_credito_id, peso, activo, orden, seccion, color_context, seccion_icono, seccion_descripcion, seccion_orden, rangos_json, updated_at)
                VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                master_id,
                linea_id,
                criterio.get("peso", 5),
                orden,
                seccion,
                color_context,
                seccion_icono,
                seccion_descripcion,
                seccion_orden,
                rangos_json
            ))
        
        conn.commit()
        invalidar_cache_scoring_linea(linea_id)
        
        print(f"✅ {len(criterios)} criterios guardados para línea {linea_id}")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error guardando criterios completos: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


# ============================================================================
# FUNCIONES PARA COPIAR CONFIGURACIÓN ENTRE LÍNEAS
# ============================================================================

def copiar_config_scoring(linea_origen_id, linea_destino_id, incluir_criterios=True,
                          incluir_niveles=True, incluir_aprobacion=True):
    """
    Copia la configuración de scoring de una línea a otra.
    Soporta copia granular por sección: niveles, criterios, aprobación.
    
    Args:
        linea_origen_id: ID de la línea origen
        linea_destino_id: ID de la línea destino
        incluir_criterios: Si True, copia criterios con secciones y rangos
        incluir_niveles: Si True, copia niveles de riesgo
        incluir_aprobacion: Si True, copia config general y factores de rechazo
        
    Returns:
        bool: True si se copió exitosamente
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    copiados = []
    
    try:
        # 1. Copiar configuración general (solo si incluir_aprobacion)
        if incluir_aprobacion:
            cursor.execute("""
                INSERT OR REPLACE INTO scoring_config_linea
                (linea_credito_id, puntaje_minimo_aprobacion, puntaje_revision_manual,
                 umbral_mora_telcos, edad_minima, edad_maxima, dti_maximo,
                 score_datacredito_minimo, consultas_max_3meses, escala_max, activo)
                SELECT 
                    ?, puntaje_minimo_aprobacion, puntaje_revision_manual,
                    umbral_mora_telcos, edad_minima, edad_maxima, dti_maximo,
                    score_datacredito_minimo, consultas_max_3meses, escala_max, activo
                FROM scoring_config_linea
                WHERE linea_credito_id = ?
            """, (linea_destino_id, linea_origen_id))
            
            # Copiar factores de rechazo (incluye tipo_factor y opciones_json)
            cursor.execute("DELETE FROM factores_rechazo_linea WHERE linea_credito_id = ?",
                          (linea_destino_id,))
            
            # Obtener columnas disponibles en factores_rechazo_linea
            cursor.execute("PRAGMA table_info(factores_rechazo_linea)")
            cols_factores = [col[1] for col in cursor.fetchall()]
            
            # Columnas base + opcionales
            cols_copiar_factores = ['criterio_codigo', 'criterio_nombre', 'operador',
                                    'valor_umbral', 'mensaje_rechazo', 'activo', 'orden']
            for col_extra in ['tipo_factor', 'opciones_json']:
                if col_extra in cols_factores:
                    cols_copiar_factores.append(col_extra)
            
            cols_str = ', '.join(cols_copiar_factores)
            cursor.execute(f"""
                INSERT INTO factores_rechazo_linea
                (linea_credito_id, {cols_str})
                SELECT 
                    ?, {cols_str}
                FROM factores_rechazo_linea
                WHERE linea_credito_id = ?
            """, (linea_destino_id, linea_origen_id))
            copiados.append("configuración de aprobación y factores de rechazo")
        
        # 2. Copiar niveles de riesgo (incluye campos de interpolación)
        if incluir_niveles:
            cursor.execute("DELETE FROM niveles_riesgo_linea WHERE linea_credito_id = ?", 
                          (linea_destino_id,))
            
            # Obtener columnas disponibles en niveles_riesgo_linea
            cursor.execute("PRAGMA table_info(niveles_riesgo_linea)")
            cols_niveles = [col[1] for col in cursor.fetchall()]
            
            # Columnas base + opcionales de interpolación
            cols_copiar_niveles = ['nombre', 'codigo', 'score_min', 'score_max',
                                   'tasa_ea', 'tasa_nominal_mensual', 'aval_porcentaje',
                                   'color', 'orden', 'activo']
            for col_extra in ['tasa_ea_at_min', 'tasa_ea_at_max', 'aval_at_min', 'aval_at_max',
                              'interpolacion_activa']:
                if col_extra in cols_niveles:
                    cols_copiar_niveles.append(col_extra)
            
            cols_str = ', '.join(cols_copiar_niveles)
            cursor.execute(f"""
                INSERT INTO niveles_riesgo_linea
                (linea_credito_id, {cols_str})
                SELECT 
                    ?, {cols_str}
                FROM niveles_riesgo_linea
                WHERE linea_credito_id = ?
            """, (linea_destino_id, linea_origen_id))
            copiados.append("niveles de riesgo")
        
        # 3. Copiar criterios con TODAS las columnas de sección
        if incluir_criterios:
            cursor.execute("DELETE FROM criterios_linea_credito WHERE linea_credito_id = ?",
                          (linea_destino_id,))
            
            # Obtener columnas disponibles en criterios_linea_credito
            cursor.execute("PRAGMA table_info(criterios_linea_credito)")
            cols_criterios = [col[1] for col in cursor.fetchall()]
            
            # Columnas base + columnas de sección y metadatos
            cols_copiar_criterios = ['criterio_master_id', 'peso', 'activo', 'orden', 'rangos_json']
            for col_extra in ['seccion', 'color_context', 'seccion_icono', 
                              'seccion_descripcion', 'seccion_orden']:
                if col_extra in cols_criterios:
                    cols_copiar_criterios.append(col_extra)
            
            cols_str = ', '.join(cols_copiar_criterios)
            cursor.execute(f"""
                INSERT INTO criterios_linea_credito
                (linea_credito_id, {cols_str})
                SELECT 
                    ?, {cols_str}
                FROM criterios_linea_credito
                WHERE linea_credito_id = ?
            """, (linea_destino_id, linea_origen_id))
            copiados.append("criterios de scoring con secciones")
        
        conn.commit()
        
        # Invalidar cache de ambas líneas
        invalidar_cache_scoring_linea(linea_origen_id)
        invalidar_cache_scoring_linea(linea_destino_id)
        
        resumen = ', '.join(copiados) if copiados else 'nada seleccionado'
        print(f"✅ Copiado de línea {linea_origen_id} a {linea_destino_id}: {resumen}")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error copiando configuración: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


# ============================================================================
# FUNCIÓN PARA OBTENER SCORING COMPLETO (compatible con sistema actual)
# ============================================================================

def cargar_scoring_por_linea(linea_nombre):
    """
    Carga la configuración de scoring para una línea específica.
    Compatible con el formato usado por el sistema actual.
    
    Args:
        linea_nombre: Nombre de la línea de crédito
        
    Returns:
        dict: Configuración de scoring en formato compatible
    """
    # Obtener ID de la línea
    linea = obtener_linea_credito_por_nombre(linea_nombre)
    
    if not linea:
        print(f"⚠️ Línea {linea_nombre} no encontrada, usando configuración global")
        return None
    
    # Obtener configuración de la línea
    config = obtener_config_scoring_linea(linea["id"])
    
    if not config or not config.get("niveles_riesgo"):
        print(f"⚠️ Línea {linea_nombre} sin configuración, usando global")
        return None
    
    # Convertir lista de criterios a diccionario (ScoringService espera dict)
    criterios_lista = config.get("criterios", [])
    criterios_dict = {}
    for c in criterios_lista:
        codigo = c.get("codigo")
        if codigo:
            criterios_dict[codigo] = {
                "nombre": c.get("nombre"),
                "descripcion": c.get("descripcion"),
                "tipo_campo": c.get("tipo_campo"),
                "seccion": c.get("seccion"),
                "peso": c.get("peso", 5),
                "activo": c.get("activo", True),
                "orden": c.get("orden", 0),
                "rangos": c.get("rangos", []),
                # Campos adicionales para agrupar_criterios_por_seccion
                "color_context": c.get("color_context"),
                "seccion_icono": c.get("seccion_icono"),
                "seccion_orden": c.get("seccion_orden")
            }
    
    # Convertir al formato esperado por el sistema actual
    # ESCALA 0-100: Los umbrales ahora están en escala 0-100
    scoring = {
        "criterios": criterios_dict,
        "niveles_riesgo": config.get("niveles_riesgo", []),
        "factores_rechazo_automatico": config.get("factores_rechazo", []),
        # Umbrales en escala 0-100
        "puntaje_minimo_aprobacion": config["config_general"].get("puntaje_minimo_aprobacion", 38),
        "puntaje_minimo_comite": config["config_general"].get("puntaje_revision_manual", 22),
        "umbral_mora_telcos_rechazo": config["config_general"].get("umbral_mora_telcos", 200000),
        "escala_max": 100,  # Escala fija 0-100
        "linea_credito_id": linea["id"],
        "linea_credito_nombre": linea_nombre
    }
    
    return scoring


# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def verificar_tablas_scoring_linea():
    """
    Verifica que existan las tablas necesarias para scoring multi-línea.
    
    Returns:
        bool: True si todas las tablas existen
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    tablas_requeridas = [
        "scoring_config_linea",
        "niveles_riesgo_linea",
        "criterios_scoring_master",
        "criterios_linea_credito",
        "factores_rechazo_linea",
        "secciones_scoring"
    ]
    
    try:
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table'
        """)
        
        tablas_existentes = [row[0] for row in cursor.fetchall()]
        
        faltantes = [t for t in tablas_requeridas if t not in tablas_existentes]
        
        if faltantes:
            print(f"⚠️ Tablas faltantes: {faltantes}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error verificando tablas: {e}")
        return False
    finally:
        conn.close()


def agrupar_criterios_por_seccion(criterios):
    """
    Agrupa criterios por sección para el template de scoring.
    
    Args:
        criterios: Lista de criterios con propiedades seccion, seccion_icono, seccion_orden, color_context
        
    Returns:
        list: Lista de grupos {seccion: {...}, criterios: [...]}
    """
    if not criterios:
        return []
    
    # Agrupar por nombre de sección
    secciones_map = {}
    for c in criterios:
        sec_nombre = c.get("seccion", "Sin Categoría")
        if sec_nombre not in secciones_map:
            # Obtener colores CSS (hex y clase)
            color_info = _color_context_to_css(c.get("color_context"))
            secciones_map[sec_nombre] = {
                "seccion": {
                    "id": sec_nombre.lower().replace(" ", "_"),
                    "nombre": sec_nombre,
                    "icono": c.get("seccion_icono") or "bi-folder",
                    "color": color_info["color_class"],
                    "color_hex": color_info["color_hex"],
                    "orden": int(c.get("seccion_orden") or 999)
                },
                "criterios": []
            }
        # Excluir criterios ocultos (tipo hidden, solo para factores de rechazo)
        if c.get("tipo_campo") == "hidden":
            continue
        
        # Agregar criterio con id para el template
        # Convertir rangos a opciones para selects (el template usa 'opciones')
        rangos = c.get("rangos", [])
        opciones = []
        for r in rangos:
            opciones.append({
                "valor": str(r.get("puntos", "")),
                "texto": r.get("etiqueta") or r.get("descripcion") or f"{r.get('min', '')}-{r.get('max', '')}"
            })
        
        # Mapear tipo_campo: "composite" del admin → "select" para el template del asesor
        tipo_campo_raw = c.get("tipo_campo", "number")
        tipo_campo_template = "select" if tipo_campo_raw in ("composite", "select", "seleccion") else tipo_campo_raw
        
        criterio_para_template = {
            "id": c.get("codigo"),
            "nombre": c.get("nombre"),
            "descripcion": c.get("descripcion"),
            "tipo_campo": tipo_campo_template,
            "peso": c.get("peso", 5),
            "rangos": rangos,
            "opciones": opciones,  # Para selects en el template
            "ayuda": c.get("descripcion", ""),
            "orden": c.get("orden", 0)
        }
        secciones_map[sec_nombre]["criterios"].append(criterio_para_template)
    
    # Ordenar criterios dentro de cada sección
    for sec in secciones_map.values():
        sec["criterios"].sort(key=lambda x: x.get("orden", 0))
    
    # Ordenar secciones por orden, "Sin Categoría" al final
    resultado = sorted(
        secciones_map.values(),
        key=lambda x: (x["seccion"]["nombre"] == "Sin Categoría", x["seccion"]["orden"])
    )
    
    return resultado


def _color_context_to_css(color_context):
    """
    Convierte color_context a valores CSS utilizables.
    Retorna dict con 'color_hex' (para style) y 'color_class' (para clase CSS).
    """
    if not color_context:
        return {"color_hex": "#6c757d", "color_class": "gray"}
    
    # Mapeo de nombres a HEX
    nombre_a_hex = {
        "purple": "#6f42c1",
        "green": "#198754",
        "blue": "#0d6efd",
        "orange": "#fd7e14",
        "red": "#dc3545",
        "teal": "#20c997",
        "yellow": "#ffc107",
        "pink": "#e91e8c",
        "gray": "#6c757d"
    }
    
    # Si es HEX, usarlo directamente
    if color_context.startswith("#"):
        return {"color_hex": color_context, "color_class": "custom"}
    
    # Si es nombre, convertir a HEX
    if color_context.lower() in nombre_a_hex:
        return {
            "color_hex": nombre_a_hex[color_context.lower()],
            "color_class": color_context.lower()
        }
    
    # Default
    return {"color_hex": "#0d6efd", "color_class": "blue"}


def asegurar_criterio_mora_telcos():
    """
    Asegura que el criterio 'mora_sector_telcos' exista en TODAS las líneas
    de crédito activas. Si ya existe, no lo duplica.
    
    Este criterio alimenta la CAPA 5 de degradación por mora telcos
    en scoring_service.py.
    
    Returns:
        int: Cantidad de líneas donde se creó el criterio
    """
    conn = conectar_db()
    cursor = conn.cursor()
    lineas_actualizadas = 0
    
    CRITERIO_CODIGO = "mora_sector_telcos"
    CRITERIO_NOMBRE = "Mora Sector Telcos (COP)"
    CRITERIO_DESC = "MiDecisor → Sectores → Telcos → Saldo en mora. Ingrese el valor en pesos (COP) del saldo en mora del sector Telcos."
    CRITERIO_TIPO = "numerico"
    CRITERIO_PESO = 2
    CRITERIO_SECCION = "Perfil Crediticio"
    CRITERIO_RANGOS = json.dumps([
        {"min": 0, "max": 0, "puntos": 20, "etiqueta": "Sin mora telcos"},
        {"min": 1, "max": 100000, "puntos": 5, "etiqueta": "Mora menor (≤$100K)"},
        {"min": 100001, "max": 200000, "puntos": -5, "etiqueta": "Mora moderada — Degradación aplica"},
        {"min": 200001, "max": 999999999, "puntos": -15, "etiqueta": "Mora alta — Comité directo"}
    ], ensure_ascii=False)
    
    try:
        # 1. Asegurar que existe en catálogo master
        cursor.execute("SELECT id FROM criterios_scoring_master WHERE codigo = ?", (CRITERIO_CODIGO,))
        row = cursor.fetchone()
        
        if row:
            master_id = row[0]
        else:
            cursor.execute("""
                INSERT INTO criterios_scoring_master 
                (codigo, nombre, descripcion, tipo_campo, activo)
                VALUES (?, ?, ?, ?, 1)
            """, (CRITERIO_CODIGO, CRITERIO_NOMBRE, CRITERIO_DESC, CRITERIO_TIPO))
            master_id = cursor.lastrowid
            print(f"  ✅ Criterio '{CRITERIO_CODIGO}' creado en catálogo master (id={master_id})")
        
        # 2. Obtener todas las líneas activas
        cursor.execute("SELECT id, nombre FROM lineas_credito WHERE activo = 1")
        lineas = cursor.fetchall()
        
        for linea_id, linea_nombre in lineas:
            # Verificar si ya existe para esta línea
            cursor.execute("""
                SELECT id FROM criterios_linea_credito 
                WHERE criterio_master_id = ? AND linea_credito_id = ?
            """, (master_id, linea_id))
            
            if cursor.fetchone():
                continue  # Ya existe, no duplicar
            
            # Obtener el mayor orden actual en la sección "Perfil Crediticio"
            cursor.execute("""
                SELECT COALESCE(MAX(orden), 0) + 1 FROM criterios_linea_credito
                WHERE linea_credito_id = ?
            """, (linea_id,))
            siguiente_orden = cursor.fetchone()[0]
            
            cursor.execute("""
                INSERT INTO criterios_linea_credito
                (criterio_master_id, linea_credito_id, peso, activo, orden,
                 seccion, color_context, seccion_icono, seccion_descripcion, seccion_orden,
                 rangos_json, updated_at)
                VALUES (?, ?, ?, 1, ?, ?, 'purple', 'bi-person-badge', 'Perfil crediticio del solicitante', '2',
                        ?, CURRENT_TIMESTAMP)
            """, (master_id, linea_id, CRITERIO_PESO, siguiente_orden,
                  CRITERIO_SECCION, CRITERIO_RANGOS))
            
            lineas_actualizadas += 1
            print(f"  ✅ Criterio '{CRITERIO_CODIGO}' agregado a línea '{linea_nombre}' (id={linea_id})")
        
        conn.commit()
        
        if lineas_actualizadas > 0:
            invalidar_cache_scoring_linea()
            print(f"✅ Criterio mora_sector_telcos creado en {lineas_actualizadas} líneas")
        
        return lineas_actualizadas
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error asegurando criterio mora_telcos: {e}")
        import traceback
        traceback.print_exc()
        return 0
    finally:
        conn.close()


def obtener_secciones_scoring():
    """
    Obtiene las secciones de scoring.
    
    Returns:
        list: Lista de secciones
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, nombre, icono, descripcion, orden
            FROM secciones_scoring
            WHERE activo = 1
            ORDER BY orden
        """)
        
        secciones = []
        for row in cursor.fetchall():
            secciones.append({
                "id": row[0],
                "nombre": row[1],
                "icono": row[2],
                "descripcion": row[3],
                "orden": row[4]
            })
        
        return secciones
        
    except Exception as e:
        print(f"❌ Error obteniendo secciones: {e}")
        return []
    finally:
        conn.close()
