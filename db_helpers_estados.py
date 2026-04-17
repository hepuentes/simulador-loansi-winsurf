"""
DB_HELPERS_ESTADOS.PY - Funciones para gestión de estados de crédito
=====================================================================

Este archivo contiene funciones adicionales para:
1. Marcar créditos como desembolsados (registrados en Finsoftek)
2. Marcar créditos como desistidos (cliente desistió)
3. Consultas de estado para trazabilidad

Se importa en db_helpers.py

Author: Sistema Loansi
Date: 2025-12-31
Version: 1.0
"""

import json
from datetime import datetime
from database import conectar_db


# ============================================================================
# ESTADOS FINALES DEL CRÉDITO
# ============================================================================

# Estados válidos para estado_final
ESTADOS_FINALES_VALIDOS = [
    'pendiente_desembolso',  # Aprobado pero no desembolsado aún
    'desembolsado',          # Registrado en Finsoftek
    'desistido',             # Cliente desistió del crédito
    None                     # Sin estado final (pendiente o rechazado en comité)
]


def marcar_desembolsado(timestamp, usuario_registrador, comentario=None):
    """
    Marca una evaluación aprobada como desembolsada (registrada en Finsoftek).
    
    Args:
        timestamp (str): Timestamp de la evaluación
        usuario_registrador (str): Username de quien registra
        comentario (str): Comentario opcional
        
    Returns:
        dict: {'success': bool, 'message': str, 'data': dict}
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        # Verificar que la evaluación existe y está aprobada
        cursor.execute("""
            SELECT estado_comite, estado_final, nombre_cliente, monto_solicitado
            FROM evaluaciones 
            WHERE timestamp = ?
        """, (timestamp,))
        
        row = cursor.fetchone()
        
        if not row:
            return {'success': False, 'message': 'Evaluación no encontrada'}
        
        estado_comite = row[0]
        estado_final_actual = row[1]
        nombre_cliente = row[2]
        monto = row[3]
        
        # Validar estado
        if estado_comite != 'approved':
            return {
                'success': False, 
                'message': f'Solo se pueden marcar como desembolsados los casos aprobados. Estado actual: {estado_comite}'
            }
        
        if estado_final_actual == 'desembolsado':
            return {'success': False, 'message': 'Este caso ya está marcado como desembolsado'}
        
        if estado_final_actual == 'desistido':
            return {'success': False, 'message': 'Este caso está marcado como desistido, no se puede desembolsar'}
        
        # Actualizar estado
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("""
            UPDATE evaluaciones 
            SET estado_final = 'desembolsado',
                fecha_desembolso = ?,
                registrado_por = ?,
                fecha_modificacion = CURRENT_TIMESTAMP
            WHERE timestamp = ?
        """, (fecha_actual, usuario_registrador, timestamp))
        
        conn.commit()
        
        # Registrar en auditoría
        cursor.execute("""
            INSERT INTO auditoria (usuario, accion, tabla_afectada, registro_id, datos_nuevos)
            VALUES (?, 'DESEMBOLSO_REGISTRADO', 'evaluaciones', 
                    (SELECT id FROM evaluaciones WHERE timestamp = ?),
                    ?)
        """, (
            usuario_registrador,
            timestamp,
            json.dumps({
                'timestamp': timestamp,
                'cliente': nombre_cliente,
                'monto': monto,
                'comentario': comentario
            })
        ))
        
        conn.commit()
        
        return {
            'success': True, 
            'message': f'Crédito marcado como desembolsado para {nombre_cliente}',
            'data': {
                'timestamp': timestamp,
                'estado_final': 'desembolsado',
                'fecha_desembolso': fecha_actual,
                'registrado_por': usuario_registrador
            }
        }
        
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': f'Error: {str(e)}'}
    finally:
        conn.close()


def marcar_desistido(timestamp, usuario_registrador, motivo=None):
    """
    Marca una evaluación como desistida (cliente no quiere el crédito).
    
    Args:
        timestamp (str): Timestamp de la evaluación
        usuario_registrador (str): Username de quien registra
        motivo (str): Razón del desistimiento
        
    Returns:
        dict: {'success': bool, 'message': str, 'data': dict}
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        # Verificar que la evaluación existe
        cursor.execute("""
            SELECT estado_comite, estado_final, nombre_cliente, resultado
            FROM evaluaciones 
            WHERE timestamp = ?
        """, (timestamp,))
        
        row = cursor.fetchone()
        
        if not row:
            return {'success': False, 'message': 'Evaluación no encontrada'}
        
        estado_comite = row[0]
        estado_final_actual = row[1]
        nombre_cliente = row[2]
        resultado = json.loads(row[3]) if row[3] else {}
        
        # Validar que no esté ya desembolsado
        if estado_final_actual == 'desembolsado':
            return {'success': False, 'message': 'Este caso ya fue desembolsado, no se puede marcar como desistido'}
        
        if estado_final_actual == 'desistido':
            return {'success': False, 'message': 'Este caso ya está marcado como desistido'}
        
        # Se puede marcar como desistido si:
        # - Está aprobado (approved) pero no desembolsado
        # - Está aprobado automáticamente (resultado.aprobado = True sin ir a comité)
        # - Está pendiente (pending) en comité
        
        puede_desistir = (
            estado_comite == 'approved' or 
            estado_comite == 'pending' or
            (resultado.get('aprobado') == True and not estado_comite)
        )
        
        if not puede_desistir:
            return {
                'success': False, 
                'message': 'Solo se pueden marcar como desistidos los casos aprobados o pendientes'
            }
        
        # Actualizar estado
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("""
            UPDATE evaluaciones 
            SET estado_final = 'desistido',
                fecha_desistimiento = ?,
                motivo_desistimiento = ?,
                registrado_por = ?,
                fecha_modificacion = CURRENT_TIMESTAMP
            WHERE timestamp = ?
        """, (fecha_actual, motivo, usuario_registrador, timestamp))
        
        conn.commit()
        
        # Registrar en auditoría
        cursor.execute("""
            INSERT INTO auditoria (usuario, accion, tabla_afectada, registro_id, datos_nuevos)
            VALUES (?, 'DESISTIMIENTO_REGISTRADO', 'evaluaciones', 
                    (SELECT id FROM evaluaciones WHERE timestamp = ?),
                    ?)
        """, (
            usuario_registrador,
            timestamp,
            json.dumps({
                'timestamp': timestamp,
                'cliente': nombre_cliente,
                'motivo': motivo
            })
        ))
        
        conn.commit()
        
        return {
            'success': True, 
            'message': f'Crédito marcado como desistido para {nombre_cliente}',
            'data': {
                'timestamp': timestamp,
                'estado_final': 'desistido',
                'fecha_desistimiento': fecha_actual,
                'motivo': motivo,
                'registrado_por': usuario_registrador
            }
        }
        
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': f'Error: {str(e)}'}
    finally:
        conn.close()


def revertir_estado_final(timestamp, usuario_registrador, motivo=None):
    """
    Revierte el estado final de una evaluación (quita desembolsado o desistido).
    Solo para correcciones administrativas.
    
    Args:
        timestamp (str): Timestamp de la evaluación
        usuario_registrador (str): Username de quien registra
        motivo (str): Razón de la reversión
        
    Returns:
        dict: {'success': bool, 'message': str}
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        # Verificar que la evaluación existe
        cursor.execute("""
            SELECT estado_final, nombre_cliente
            FROM evaluaciones 
            WHERE timestamp = ?
        """, (timestamp,))
        
        row = cursor.fetchone()
        
        if not row:
            return {'success': False, 'message': 'Evaluación no encontrada'}
        
        estado_final_actual = row[0]
        nombre_cliente = row[1]
        
        if not estado_final_actual:
            return {'success': False, 'message': 'Este caso no tiene estado final que revertir'}
        
        # Guardar estado anterior para auditoría
        estado_anterior = estado_final_actual
        
        # Revertir estado
        cursor.execute("""
            UPDATE evaluaciones 
            SET estado_final = NULL,
                fecha_desembolso = NULL,
                fecha_desistimiento = NULL,
                motivo_desistimiento = NULL,
                registrado_por = NULL,
                fecha_modificacion = CURRENT_TIMESTAMP
            WHERE timestamp = ?
        """, (timestamp,))
        
        conn.commit()
        
        # Registrar en auditoría
        cursor.execute("""
            INSERT INTO auditoria (usuario, accion, tabla_afectada, registro_id, datos_anteriores, datos_nuevos)
            VALUES (?, 'ESTADO_REVERTIDO', 'evaluaciones', 
                    (SELECT id FROM evaluaciones WHERE timestamp = ?),
                    ?, ?)
        """, (
            usuario_registrador,
            timestamp,
            json.dumps({'estado_final': estado_anterior}),
            json.dumps({'motivo_reversion': motivo})
        ))
        
        conn.commit()
        
        return {
            'success': True, 
            'message': f'Estado revertido para {nombre_cliente}. Estado anterior: {estado_anterior}'
        }
        
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': f'Error: {str(e)}'}
    finally:
        conn.close()


# ============================================================================
# CONSULTAS DE ESTADOS
# ============================================================================

def obtener_casos_por_estado_final(estado_final, filtros=None):
    """
    Obtiene casos filtrados por estado final.
    
    Args:
        estado_final (str): 'desembolsado', 'desistido', 'pendiente_desembolso', None
        filtros (dict): Filtros adicionales (asesor, fecha_desde, fecha_hasta)
        
    Returns:
        list: Lista de casos
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    query = """
        SELECT timestamp, asesor, nombre_cliente, cedula,
               tipo_credito, monto_solicitado, resultado,
               estado_comite, decision_admin,
               estado_final, fecha_desembolso, fecha_desistimiento,
               motivo_desistimiento, registrado_por
        FROM evaluaciones
        WHERE 1=1
    """
    
    params = []
    
    if estado_final is None:
        # Casos sin estado final (pendientes en proceso)
        query += " AND estado_final IS NULL"
    elif estado_final == 'pendiente_desembolso':
        # Aprobados pero no desembolsados
        query += " AND estado_comite = 'approved' AND (estado_final IS NULL OR estado_final = 'pendiente_desembolso')"
    else:
        query += " AND estado_final = ?"
        params.append(estado_final)
    
    if filtros:
        if 'asesor' in filtros:
            query += " AND asesor = ?"
            params.append(filtros['asesor'])
        
        if 'fecha_desde' in filtros:
            query += " AND timestamp >= ?"
            params.append(filtros['fecha_desde'])
        
        if 'fecha_hasta' in filtros:
            query += " AND timestamp <= ?"
            params.append(filtros['fecha_hasta'])
    
    query += " ORDER BY timestamp DESC"
    
    cursor.execute(query, params)
    
    casos = []
    for row in cursor.fetchall():
        caso = {
            'timestamp': row[0],
            'asesor': row[1],
            'nombre_cliente': row[2],
            'cedula': row[3],
            'tipo_credito': row[4],
            'monto_solicitado': row[5],
            'resultado': json.loads(row[6]) if row[6] else {},
            'estado_comite': row[7],
            'decision_admin': json.loads(row[8]) if row[8] else None,
            'estado_final': row[9],
            'fecha_desembolso': row[10],
            'fecha_desistimiento': row[11],
            'motivo_desistimiento': row[12],
            'registrado_por': row[13]
        }
        casos.append(caso)
    
    conn.close()
    return casos


def obtener_estadisticas_estados():
    """
    Obtiene estadísticas de estados finales.
    
    Returns:
        dict: Estadísticas por estado
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    estadisticas = {}
    
    # Total por estado final
    cursor.execute("""
        SELECT 
            COALESCE(estado_final, 'sin_estado') as estado,
            COUNT(*) as total,
            SUM(monto_solicitado) as monto_total
        FROM evaluaciones
        WHERE estado_comite = 'approved'
        GROUP BY estado_final
    """)
    
    for row in cursor.fetchall():
        estadisticas[row[0]] = {
            'total': row[1],
            'monto_total': row[2] or 0
        }
    
    # Pendientes de desembolso (aprobados sin estado final)
    cursor.execute("""
        SELECT COUNT(*), SUM(monto_solicitado)
        FROM evaluaciones
        WHERE estado_comite = 'approved' 
        AND (estado_final IS NULL OR estado_final = 'pendiente_desembolso')
    """)
    
    row = cursor.fetchone()
    estadisticas['pendiente_desembolso'] = {
        'total': row[0] or 0,
        'monto_total': row[1] or 0
    }
    
    # Total desembolsados
    cursor.execute("""
        SELECT COUNT(*), SUM(monto_solicitado)
        FROM evaluaciones
        WHERE estado_final = 'desembolsado'
    """)
    
    row = cursor.fetchone()
    estadisticas['desembolsado'] = {
        'total': row[0] or 0,
        'monto_total': row[1] or 0
    }
    
    # Total desistidos
    cursor.execute("""
        SELECT COUNT(*), SUM(monto_solicitado)
        FROM evaluaciones
        WHERE estado_final = 'desistido'
    """)
    
    row = cursor.fetchone()
    estadisticas['desistido'] = {
        'total': row[0] or 0,
        'monto_total': row[1] or 0
    }
    
    conn.close()
    return estadisticas


def obtener_resumen_asesor(username):
    """
    Obtiene resumen de estados para un asesor específico.
    
    Args:
        username (str): Username del asesor
        
    Returns:
        dict: Resumen de estados
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_evaluaciones,
            SUM(CASE WHEN estado_comite = 'pending' THEN 1 ELSE 0 END) as pendientes_comite,
            SUM(CASE WHEN estado_comite = 'approved' THEN 1 ELSE 0 END) as aprobados,
            SUM(CASE WHEN estado_comite = 'rejected' THEN 1 ELSE 0 END) as rechazados,
            SUM(CASE WHEN estado_final = 'desembolsado' THEN 1 ELSE 0 END) as desembolsados,
            SUM(CASE WHEN estado_final = 'desistido' THEN 1 ELSE 0 END) as desistidos,
            SUM(CASE WHEN estado_comite = 'approved' AND estado_final IS NULL THEN 1 ELSE 0 END) as pendientes_desembolso
        FROM evaluaciones
        WHERE asesor = ?
    """, (username,))
    
    row = cursor.fetchone()
    
    resumen = {
        'total_evaluaciones': row[0] or 0,
        'pendientes_comite': row[1] or 0,
        'aprobados': row[2] or 0,
        'rechazados': row[3] or 0,
        'desembolsados': row[4] or 0,
        'desistidos': row[5] or 0,
        'pendientes_desembolso': row[6] or 0
    }
    
    conn.close()
    return resumen


# ============================================================================
# FUNCIÓN PARA OBTENER CASO CON TODOS LOS DATOS
# ============================================================================

def obtener_caso_completo(timestamp):
    """
    Obtiene todos los datos de un caso incluyendo estados finales.
    
    Args:
        timestamp (str): Timestamp de la evaluación
        
    Returns:
        dict: Datos completos del caso o None
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT timestamp, asesor, nombre_cliente, cedula,
               tipo_credito, linea_credito, monto_solicitado, resultado,
               estado_comite, decision_admin, visto_por_asesor,
               fecha_envio_comite, puntaje_datacredito,
               criterios_detalle, valores_criterios, nivel_riesgo,
               estado_final, fecha_desembolso, fecha_desistimiento,
               motivo_desistimiento, registrado_por,
               fecha_creacion, fecha_modificacion
        FROM evaluaciones
        WHERE timestamp = ?
    """, (timestamp,))
    
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return None
    
    caso = {
        'timestamp': row[0],
        'asesor': row[1],
        'nombre_cliente': row[2],
        'cedula': row[3],
        'tipo_credito': row[4],
        'linea_credito': row[5],
        'monto_solicitado': row[6],
        'resultado': json.loads(row[7]) if row[7] else {},
        'estado_comite': row[8],
        'decision_admin': json.loads(row[9]) if row[9] else None,
        'visto_por_asesor': bool(row[10]),
        'fecha_envio_comite': row[11],
        'puntaje_datacredito': row[12],
        'criterios_detalle': json.loads(row[13]) if row[13] else [],
        'valores_criterios': json.loads(row[14]) if row[14] else {},
        'nivel_riesgo': row[15],
        'estado_final': row[16],
        'fecha_desembolso': row[17],
        'fecha_desistimiento': row[18],
        'motivo_desistimiento': row[19],
        'registrado_por': row[20],
        'fecha_creacion': row[21],
        'fecha_modificacion': row[22]
    }
    
    conn.close()
    return caso
