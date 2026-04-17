"""
DB_HELPERS_DASHBOARD.PY - Funciones para obtener estadísticas del Dashboard
============================================================================
VERSIÓN MEJORADA con:
- Filtrado por asignaciones de equipo (user_assignments)
- Funciones para obtener lista detallada de usuarios asignados
- Estadísticas por usuario para supervisores/gerentes
- Soporte completo para jerarquía organizacional

"""

import sqlite3
from datetime import datetime, timedelta
from database import conectar_db


# ============================================================================
# FUNCIONES AUXILIARES PARA OBTENER USUARIOS ASIGNADOS
# ============================================================================

def obtener_usuarios_asignados_detalle(manager_username):
    """
    Obtiene lista detallada de usuarios asignados a un manager (supervisor/gerente/auditor).
    Incluye información del usuario y estadísticas básicas.
    
    Args:
        manager_username (str): Username del manager
        
    Returns:
        list: Lista de dicts con info de cada usuario asignado
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        # Obtener usuarios directamente asignados con su información
        cursor.execute("""
            SELECT 
                ua.member_username,
                u.nombre_completo,
                u.rol,
                u.activo,
                ua.fecha_creacion as fecha_asignacion
            FROM user_assignments ua
            LEFT JOIN usuarios u ON ua.member_username = u.username
            WHERE ua.manager_username = ? AND ua.activo = 1
            ORDER BY u.nombre_completo, ua.member_username
        """, (manager_username,))
        
        usuarios = []
        for row in cursor.fetchall():
            username = row[0]
            
            # Obtener estadísticas del usuario
            stats = obtener_stats_usuario_rapido(cursor, username)
            
            usuarios.append({
                'username': username,
                'nombre_completo': row[1] or username,
                'rol': row[2] or 'asesor',
                'activo': bool(row[3]) if row[3] is not None else True,
                'fecha_asignacion': row[4],
                'stats': stats
            })
        
        return usuarios
        
    except Exception as e:
        print(f"❌ Error obteniendo usuarios asignados detalle: {e}")
        return []
    finally:
        conn.close()


def obtener_stats_usuario_rapido(cursor, username):
    """
    Obtiene estadísticas rápidas de un usuario (usa cursor existente).
    
    Args:
        cursor: Cursor de SQLite activo
        username (str): Username del usuario
        
    Returns:
        dict: Estadísticas básicas del usuario
    """
    stats = {
        'evaluaciones_hoy': 0,
        'evaluaciones_semana': 0,
        'evaluaciones_mes': 0,
        'simulaciones_hoy': 0,
        'casos_pendientes': 0,
        'ultima_actividad': None,
        'activo_hoy': False
    }
    
    try:
        inicio_semana = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime('%Y-%m-%d')
        
        # Evaluaciones hoy
        cursor.execute("""
            SELECT COUNT(*) FROM evaluaciones
            WHERE asesor = ? AND DATE(fecha_creacion) = DATE('now', 'localtime')
        """, (username,))
        stats['evaluaciones_hoy'] = cursor.fetchone()[0]
        
        # Evaluaciones semana
        cursor.execute("""
            SELECT COUNT(*) FROM evaluaciones
            WHERE asesor = ? AND DATE(fecha_creacion) >= ?
        """, (username, inicio_semana))
        stats['evaluaciones_semana'] = cursor.fetchone()[0]
        
        # Evaluaciones mes
        cursor.execute("""
            SELECT COUNT(*) FROM evaluaciones
            WHERE asesor = ? AND strftime('%Y-%m', fecha_creacion) = strftime('%Y-%m', 'now')
        """, (username,))
        stats['evaluaciones_mes'] = cursor.fetchone()[0]
        
        # Simulaciones hoy
        cursor.execute("""
            SELECT COUNT(*) FROM simulaciones
            WHERE asesor = ? AND DATE(timestamp) = DATE('now', 'localtime')
        """, (username,))
        stats['simulaciones_hoy'] = cursor.fetchone()[0]
        
        # Casos pendientes comité
        cursor.execute("""
            SELECT COUNT(*) FROM evaluaciones
            WHERE asesor = ? AND estado_comite = 'pending'
        """, (username,))
        stats['casos_pendientes'] = cursor.fetchone()[0]
        
        # Última actividad
        cursor.execute("""
            SELECT MAX(fecha_creacion) FROM evaluaciones WHERE asesor = ?
        """, (username,))
        row = cursor.fetchone()
        stats['ultima_actividad'] = row[0] if row and row[0] else None
        
        # Activo hoy
        stats['activo_hoy'] = stats['evaluaciones_hoy'] > 0 or stats['simulaciones_hoy'] > 0
        
    except Exception as e:
        print(f"⚠️ Error obteniendo stats rápidos para {username}: {e}")
    
    return stats


def obtener_jerarquia_gerente(gerente_username):
    """
    Obtiene la jerarquía completa de un gerente:
    - Supervisores asignados directamente
    - Asesores de cada supervisor
    
    Args:
        gerente_username (str): Username del gerente
        
    Returns:
        dict: {
            'supervisores': [
                {
                    'username': str,
                    'nombre_completo': str,
                    'asesores': [...]
                }
            ],
            'total_supervisores': int,
            'total_asesores': int
        }
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        resultado = {
            'supervisores': [],
            'total_supervisores': 0,
            'total_asesores': 0
        }
        
        # Obtener supervisores asignados al gerente
        cursor.execute("""
            SELECT 
                ua.member_username,
                u.nombre_completo,
                u.rol
            FROM user_assignments ua
            LEFT JOIN usuarios u ON ua.member_username = u.username
            WHERE ua.manager_username = ? AND ua.activo = 1
            ORDER BY u.nombre_completo
        """, (gerente_username,))
        
        supervisores = cursor.fetchall()
        resultado['total_supervisores'] = len(supervisores)
        
        for sup in supervisores:
            sup_username = sup[0]
            sup_data = {
                'username': sup_username,
                'nombre_completo': sup[1] or sup_username,
                'rol': sup[2] or 'supervisor',
                'asesores': [],
                'stats': obtener_stats_usuario_rapido(cursor, sup_username)
            }
            
            # Obtener asesores de este supervisor
            cursor.execute("""
                SELECT 
                    ua.member_username,
                    u.nombre_completo,
                    u.rol
                FROM user_assignments ua
                LEFT JOIN usuarios u ON ua.member_username = u.username
                WHERE ua.manager_username = ? AND ua.activo = 1
                ORDER BY u.nombre_completo
            """, (sup_username,))
            
            asesores = cursor.fetchall()
            for asesor in asesores:
                asesor_data = {
                    'username': asesor[0],
                    'nombre_completo': asesor[1] or asesor[0],
                    'rol': asesor[2] or 'asesor',
                    'stats': obtener_stats_usuario_rapido(cursor, asesor[0])
                }
                sup_data['asesores'].append(asesor_data)
                resultado['total_asesores'] += 1
            
            resultado['supervisores'].append(sup_data)
        
        return resultado
        
    except Exception as e:
        print(f"❌ Error obteniendo jerarquía gerente: {e}")
        return {'supervisores': [], 'total_supervisores': 0, 'total_asesores': 0}
    finally:
        conn.close()


# ============================================================================
# FUNCIONES DE ESTADÍSTICAS POR ROL
# ============================================================================

def obtener_estadisticas_asesor(username):
    """
    Obtiene estadísticas para un asesor.

    Args:
        username (str): Username del asesor

    Returns:
        dict: Estadísticas del asesor
    """
    conn = conectar_db()
    cursor = conn.cursor()

    inicio_semana = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime('%Y-%m-%d')

    stats = {
        'rol': 'asesor',
        'titulo': 'Mi Panel',
        'icono': 'bi-person-workspace',
        'color': 'primary'
    }

    # Simulaciones de hoy
    cursor.execute("""
        SELECT COUNT(*) FROM simulaciones
        WHERE asesor = ? AND DATE(timestamp) = DATE('now', 'localtime')
    """, (username,))
    stats['simulaciones_hoy'] = cursor.fetchone()[0]

    # Simulaciones esta semana
    cursor.execute("""
        SELECT COUNT(*) FROM simulaciones
        WHERE asesor = ? AND DATE(timestamp) >= ?
    """, (username, inicio_semana))
    stats['simulaciones_semana'] = cursor.fetchone()[0]

    # Total simulaciones
    cursor.execute("""
        SELECT COUNT(*) FROM simulaciones WHERE asesor = ?
    """, (username,))
    stats['simulaciones_total'] = cursor.fetchone()[0]

    # Evaluaciones de hoy
    cursor.execute("""
        SELECT COUNT(*) FROM evaluaciones
        WHERE asesor = ? AND DATE(fecha_creacion) = DATE('now', 'localtime')
    """, (username,))
    stats['evaluaciones_hoy'] = cursor.fetchone()[0]

    # Evaluaciones esta semana
    cursor.execute("""
        SELECT COUNT(*) FROM evaluaciones
        WHERE asesor = ? AND DATE(fecha_creacion) >= ?
    """, (username, inicio_semana))
    stats['evaluaciones_semana'] = cursor.fetchone()[0]

    # Total evaluaciones
    cursor.execute("""
        SELECT COUNT(*) FROM evaluaciones WHERE asesor = ?
    """, (username,))
    stats['evaluaciones_total'] = cursor.fetchone()[0]

    # Casos enviados a comité (pendientes)
    cursor.execute("""
        SELECT COUNT(*) FROM evaluaciones
        WHERE asesor = ? AND estado_comite = 'pending'
    """, (username,))
    stats['casos_pendientes_comite'] = cursor.fetchone()[0]

    # Casos aprobados por comité
    cursor.execute("""
        SELECT COUNT(*) FROM evaluaciones
        WHERE asesor = ? AND estado_comite = 'approved'
    """, (username,))
    stats['casos_aprobados'] = cursor.fetchone()[0]

    # Casos rechazados por comité
    cursor.execute("""
        SELECT COUNT(*) FROM evaluaciones
        WHERE asesor = ? AND estado_comite = 'rejected'
    """, (username,))
    stats['casos_rechazados'] = cursor.fetchone()[0]

    # Casos con respuesta no vistos
    cursor.execute("""
        SELECT COUNT(*) FROM evaluaciones
        WHERE asesor = ?
          AND estado_comite IN ('approved', 'rejected')
          AND (visto_por_asesor = 0 OR visto_por_asesor IS NULL)
    """, (username,))
    stats['casos_nuevos'] = cursor.fetchone()[0]

    # Última actividad
    cursor.execute("""
        SELECT MAX(fecha_creacion) FROM evaluaciones WHERE asesor = ?
    """, (username,))
    row = cursor.fetchone()
    stats['ultima_actividad'] = row[0] if row and row[0] else None

    conn.close()
    return stats


def obtener_estadisticas_supervisor(username=None):
    """
    Obtiene estadísticas para un supervisor (SOLO su equipo asignado).
    Incluye lista detallada de asesores asignados.

    Args:
        username (str): Username del supervisor para filtrar por asignaciones

    Returns:
        dict: Estadísticas del equipo asignado
    """
    conn = conectar_db()
    cursor = conn.cursor()

    inicio_semana = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime('%Y-%m-%d')

    stats = {
        'rol': 'supervisor',
        'titulo': 'Panel de Supervisión',
        'icono': 'bi-people',
        'color': 'purple',
        'sin_asignaciones': False,
        'lista_asesores': []  # NUEVO: Lista detallada de asesores
    }

    # === OBTENER ASESORES ASIGNADOS A ESTE SUPERVISOR ===
    asesores = []
    asesores_data = []
    if username:
        cursor.execute("""
            SELECT 
                ua.member_username,
                u.nombre_completo,
                u.rol,
                u.activo
            FROM user_assignments ua
            LEFT JOIN usuarios u ON ua.member_username = u.username
            WHERE ua.manager_username = ? AND ua.activo = 1
            ORDER BY u.nombre_completo
        """, (username,))
        
        for row in cursor.fetchall():
            asesores.append(row[0])
            asesores_data.append({
                'username': row[0],
                'nombre_completo': row[1] or row[0],
                'rol': row[2] or 'asesor',
                'activo': bool(row[3]) if row[3] is not None else True
            })

    # Si no hay asignaciones, retornar stats vacías con mensaje
    if not asesores:
        stats['asesores_activos'] = 0
        stats['asesores_activos_hoy'] = 0
        stats['simulaciones_equipo_hoy'] = 0
        stats['simulaciones_equipo_semana'] = 0
        stats['evaluaciones_equipo_hoy'] = 0
        stats['evaluaciones_equipo_semana'] = 0
        stats['casos_pendientes_total'] = 0
        stats['top_asesores'] = []
        stats['sin_asignaciones'] = True
        conn.close()
        return stats

    # Placeholder para queries IN
    ph = ','.join('?' * len(asesores))

    # Asesores activos (de los asignados)
    stats['asesores_activos'] = len(asesores)

    # Agregar estadísticas a cada asesor
    for asesor_info in asesores_data:
        asesor_stats = obtener_stats_usuario_rapido(cursor, asesor_info['username'])
        asesor_info['stats'] = asesor_stats
    
    stats['lista_asesores'] = asesores_data

    # Asesores que han trabajado hoy (DE LOS ASIGNADOS)
    cursor.execute(f"""
        SELECT COUNT(DISTINCT asesor) FROM evaluaciones
        WHERE DATE(fecha_creacion) = DATE('now', 'localtime')
          AND asesor IN ({ph})
    """, asesores)
    stats['asesores_activos_hoy'] = cursor.fetchone()[0]

    # Simulaciones del equipo hoy (DE LOS ASIGNADOS)
    cursor.execute(f"""
        SELECT COUNT(*) FROM simulaciones
        WHERE DATE(timestamp) = DATE('now', 'localtime')
          AND asesor IN ({ph})
    """, asesores)
    stats['simulaciones_equipo_hoy'] = cursor.fetchone()[0]

    # Simulaciones del equipo esta semana (DE LOS ASIGNADOS)
    cursor.execute(f"""
        SELECT COUNT(*) FROM simulaciones
        WHERE DATE(timestamp) >= ?
          AND asesor IN ({ph})
    """, [inicio_semana] + asesores)
    stats['simulaciones_equipo_semana'] = cursor.fetchone()[0]

    # Evaluaciones del equipo hoy (DE LOS ASIGNADOS)
    cursor.execute(f"""
        SELECT COUNT(*) FROM evaluaciones
        WHERE DATE(fecha_creacion) = DATE('now', 'localtime')
          AND asesor IN ({ph})
    """, asesores)
    stats['evaluaciones_equipo_hoy'] = cursor.fetchone()[0]

    # Evaluaciones del equipo esta semana (DE LOS ASIGNADOS)
    cursor.execute(f"""
        SELECT COUNT(*) FROM evaluaciones
        WHERE DATE(fecha_creacion) >= ?
          AND asesor IN ({ph})
    """, [inicio_semana] + asesores)
    stats['evaluaciones_equipo_semana'] = cursor.fetchone()[0]

    # Total casos pendientes de comité (DE LOS ASIGNADOS)
    cursor.execute(f"""
        SELECT COUNT(*) FROM evaluaciones
        WHERE estado_comite = 'pending'
          AND asesor IN ({ph})
    """, asesores)
    stats['casos_pendientes_total'] = cursor.fetchone()[0]

    # Top asesores de la semana (SOLO DE LOS ASIGNADOS)
    cursor.execute(f"""
        SELECT COALESCE(u.nombre_completo, e.asesor) as nombre, 
               e.asesor as username,
               COUNT(*) as total
        FROM evaluaciones e
        LEFT JOIN usuarios u ON e.asesor = u.username
        WHERE DATE(e.fecha_creacion) >= ?
          AND e.asesor IN ({ph})
        GROUP BY e.asesor
        ORDER BY total DESC
        LIMIT 5
    """, [inicio_semana] + asesores)
    stats['top_asesores'] = [
        {'nombre': row[0] or 'Sin nombre', 'username': row[1], 'total': row[2]} 
        for row in cursor.fetchall()
    ]

    conn.close()
    return stats


def obtener_estadisticas_comite():
    """
    Obtiene estadísticas para miembros del comité de crédito.

    Returns:
        dict: Estadísticas del comité
    """
    conn = conectar_db()
    cursor = conn.cursor()

    stats = {
        'rol': 'comite_credito',
        'titulo': 'Panel de Comité de Crédito',
        'icono': 'bi-clipboard-check',
        'color': 'dark'
    }

    # Casos pendientes de decisión
    cursor.execute("""
        SELECT COUNT(*) FROM evaluaciones
        WHERE estado_comite = 'pending'
    """)
    stats['casos_pendientes'] = cursor.fetchone()[0]

    # Casos aprobados hoy
    cursor.execute("""
        SELECT COUNT(*) FROM evaluaciones
        WHERE estado_comite = 'approved'
          AND DATE(fecha_modificacion) = DATE('now', 'localtime')
          AND decision_admin IS NOT NULL
    """)
    stats['aprobados_hoy'] = cursor.fetchone()[0]

    # Casos rechazados hoy
    cursor.execute("""
        SELECT COUNT(*) FROM evaluaciones
        WHERE estado_comite = 'rejected'
          AND DATE(fecha_modificacion) = DATE('now', 'localtime')
          AND decision_admin IS NOT NULL
    """)
    stats['rechazados_hoy'] = cursor.fetchone()[0]

    # Total decisiones del mes
    cursor.execute("""
        SELECT COUNT(*) FROM evaluaciones
        WHERE estado_comite IN ('approved', 'rejected')
          AND decision_admin IS NOT NULL
          AND strftime('%Y-%m', fecha_modificacion) = strftime('%Y-%m', 'now')
    """)
    stats['decisiones_mes'] = cursor.fetchone()[0]

    # Distribución por nivel de riesgo (pendientes)
    cursor.execute("""
        SELECT
            COALESCE(nivel_riesgo, 'Sin clasificar') as nivel,
            COUNT(*) as total
        FROM evaluaciones
        WHERE estado_comite = 'pending'
        GROUP BY nivel_riesgo
    """)
    stats['por_riesgo'] = {row[0]: row[1] for row in cursor.fetchall()}

    # Casos más antiguos pendientes
    cursor.execute("""
        SELECT nombre_cliente, fecha_creacion, asesor
        FROM evaluaciones
        WHERE estado_comite = 'pending'
        ORDER BY fecha_creacion ASC
        LIMIT 5
    """)
    stats['casos_antiguos'] = [
        {'cliente': row[0], 'fecha': row[1][:10] if row[1] else 'Sin fecha', 'asesor': row[2]}
        for row in cursor.fetchall()
    ]

    conn.close()
    return stats


def obtener_estadisticas_auditor(username=None):
    """
    Obtiene estadísticas para un auditor.
    Si tiene asignaciones, filtra por su jerarquía.
    Si no tiene, ve datos globales.

    Args:
        username (str): Username del auditor

    Returns:
        dict: Estadísticas de auditoría
    """
    conn = conectar_db()
    cursor = conn.cursor()

    stats = {
        'rol': 'auditor',
        'titulo': 'Panel de Auditoría',
        'icono': 'bi-shield-check',
        'color': 'warning',
        'sin_asignaciones': False,
        'scope': 'global'
    }

    # Obtener usuarios asignados (supervisores y sus asesores)
    supervisores_asignados = []
    if username:
        cursor.execute("""
            SELECT member_username FROM user_assignments
            WHERE manager_username = ? AND activo = 1
        """, (username,))
        supervisores_asignados = [row[0] for row in cursor.fetchall()]

    asesores_asignados = []
    if supervisores_asignados:
        ph_supervisores = ','.join('?' * len(supervisores_asignados))
        cursor.execute(f"""
            SELECT member_username FROM user_assignments
            WHERE manager_username IN ({ph_supervisores}) AND activo = 1
        """, supervisores_asignados)
        asesores_asignados = [row[0] for row in cursor.fetchall()]

    # Determinar scope
    usar_filtro = len(asesores_asignados) > 0
    if usar_filtro:
        ph = ','.join('?' * len(asesores_asignados))
        stats['scope'] = 'equipo'
        stats['usuarios_en_scope'] = len(asesores_asignados)
    else:
        stats['scope'] = 'global'

    # Total evaluaciones
    if usar_filtro:
        cursor.execute(f"SELECT COUNT(*) FROM evaluaciones WHERE asesor IN ({ph})", asesores_asignados)
    else:
        cursor.execute("SELECT COUNT(*) FROM evaluaciones")
    stats['total_evaluaciones'] = cursor.fetchone()[0]

    # Total simulaciones
    if usar_filtro:
        cursor.execute(f"SELECT COUNT(*) FROM simulaciones WHERE asesor IN ({ph})", asesores_asignados)
    else:
        cursor.execute("SELECT COUNT(*) FROM simulaciones")
    stats['total_simulaciones'] = cursor.fetchone()[0]

    # Evaluaciones por mes (últimos 6 meses)
    if usar_filtro:
        cursor.execute(f"""
            SELECT strftime('%Y-%m', fecha_creacion) as mes, COUNT(*) as total
            FROM evaluaciones
            WHERE fecha_creacion >= date('now', '-6 months')
              AND asesor IN ({ph})
            GROUP BY mes
            ORDER BY mes DESC
        """, asesores_asignados)
    else:
        cursor.execute("""
            SELECT strftime('%Y-%m', fecha_creacion) as mes, COUNT(*) as total
            FROM evaluaciones
            WHERE fecha_creacion >= date('now', '-6 months')
            GROUP BY mes
            ORDER BY mes DESC
        """)
    stats['evaluaciones_por_mes'] = [{'mes': row[0], 'total': row[1]} for row in cursor.fetchall()]

    # Tasa de aprobación
    if usar_filtro:
        cursor.execute(f"""
            SELECT
                SUM(CASE WHEN estado_comite = 'approved' THEN 1 ELSE 0 END) as aprobados,
                SUM(CASE WHEN estado_comite = 'rejected' THEN 1 ELSE 0 END) as rechazados
            FROM evaluaciones
            WHERE estado_comite IN ('approved', 'rejected')
              AND asesor IN ({ph})
        """, asesores_asignados)
    else:
        cursor.execute("""
            SELECT
                SUM(CASE WHEN estado_comite = 'approved' THEN 1 ELSE 0 END) as aprobados,
                SUM(CASE WHEN estado_comite = 'rejected' THEN 1 ELSE 0 END) as rechazados
            FROM evaluaciones
            WHERE estado_comite IN ('approved', 'rejected')
        """)
    row = cursor.fetchone()
    aprobados = row[0] or 0
    rechazados = row[1] or 0
    total = aprobados + rechazados
    stats['tasa_aprobacion'] = round((aprobados / total * 100), 1) if total > 0 else 0
    stats['total_aprobados'] = aprobados
    stats['total_rechazados'] = rechazados

    # Distribución por asesor (top 10)
    if usar_filtro:
        cursor.execute(f"""
            SELECT COALESCE(u.nombre_completo, e.asesor) as nombre, COUNT(*) as total
            FROM evaluaciones e
            LEFT JOIN usuarios u ON e.asesor = u.username
            WHERE e.asesor IN ({ph})
            GROUP BY e.asesor
            ORDER BY total DESC
            LIMIT 10
        """, asesores_asignados)
    else:
        cursor.execute("""
            SELECT COALESCE(u.nombre_completo, e.asesor) as nombre, COUNT(*) as total
            FROM evaluaciones e
            LEFT JOIN usuarios u ON e.asesor = u.username
            GROUP BY e.asesor
            ORDER BY total DESC
            LIMIT 10
        """)
    stats['distribucion_asesores'] = [
        {'nombre': row[0] or 'Sin nombre', 'total': row[1]}
        for row in cursor.fetchall()
    ]

    conn.close()
    return stats


def obtener_estadisticas_gerente(username=None):
    """
    Obtiene estadísticas ejecutivas para gerentes (SOLO su equipo jerárquico).
    Incluye lista detallada de supervisores y asesores.

    Args:
        username (str): Username del gerente

    Returns:
        dict: Estadísticas ejecutivas del equipo jerárquico
    """
    conn = conectar_db()
    cursor = conn.cursor()

    stats = {
        'rol': 'gerente',
        'titulo': 'Panel Ejecutivo',
        'icono': 'bi-briefcase',
        'color': 'success',
        'sin_asignaciones': False,
        'jerarquia': None  # NUEVO: Estructura jerárquica completa
    }

    # === OBTENER JERARQUÍA COMPLETA ===
    if username:
        stats['jerarquia'] = obtener_jerarquia_gerente(username)
    
    # Obtener supervisores asignados
    supervisores_asignados = []
    if username:
        cursor.execute("""
            SELECT member_username FROM user_assignments
            WHERE manager_username = ? AND activo = 1
        """, (username,))
        supervisores_asignados = [row[0] for row in cursor.fetchall()]

    # Obtener asesores de esos supervisores
    asesores_asignados = []
    if supervisores_asignados:
        ph_supervisores = ','.join('?' * len(supervisores_asignados))
        cursor.execute(f"""
            SELECT member_username FROM user_assignments
            WHERE manager_username IN ({ph_supervisores}) AND activo = 1
        """, supervisores_asignados)
        asesores_asignados = [row[0] for row in cursor.fetchall()]

    # Si no hay asignaciones, retornar stats vacías
    if not asesores_asignados:
        stats['total_simulaciones'] = 0
        stats['total_evaluaciones'] = 0
        stats['usuarios_activos'] = 0
        stats['evaluaciones_mes'] = 0
        stats['evaluaciones_mes_anterior'] = 0
        stats['crecimiento'] = 0
        stats['total_comite'] = 0
        stats['aprobados_comite'] = 0
        stats['pendientes_comite'] = 0
        stats['actividad_semanal'] = []
        stats['sin_asignaciones'] = True
        stats['supervisores_asignados'] = 0
        stats['asesores_en_jerarquia'] = 0
        conn.close()
        return stats

    ph = ','.join('?' * len(asesores_asignados))

    # Info de jerarquía
    stats['supervisores_asignados'] = len(supervisores_asignados)
    stats['asesores_en_jerarquia'] = len(asesores_asignados)

    # Métricas generales (del equipo jerárquico)
    cursor.execute(f"SELECT COUNT(*) FROM simulaciones WHERE asesor IN ({ph})", asesores_asignados)
    stats['total_simulaciones'] = cursor.fetchone()[0]

    cursor.execute(f"SELECT COUNT(*) FROM evaluaciones WHERE asesor IN ({ph})", asesores_asignados)
    stats['total_evaluaciones'] = cursor.fetchone()[0]

    cursor.execute(f"SELECT COUNT(*) FROM usuarios WHERE activo = 1 AND username IN ({ph})", asesores_asignados)
    stats['usuarios_activos'] = cursor.fetchone()[0]

    # Actividad del mes actual
    cursor.execute(f"""
        SELECT COUNT(*) FROM evaluaciones
        WHERE strftime('%Y-%m', fecha_creacion) = strftime('%Y-%m', 'now')
          AND asesor IN ({ph})
    """, asesores_asignados)
    stats['evaluaciones_mes'] = cursor.fetchone()[0]

    # Comparativa con mes anterior
    cursor.execute(f"""
        SELECT COUNT(*) FROM evaluaciones
        WHERE strftime('%Y-%m', fecha_creacion) = strftime('%Y-%m', date('now', '-1 month'))
          AND asesor IN ({ph})
    """, asesores_asignados)
    stats['evaluaciones_mes_anterior'] = cursor.fetchone()[0]

    # Crecimiento
    if stats['evaluaciones_mes_anterior'] > 0:
        stats['crecimiento'] = round(
            ((stats['evaluaciones_mes'] - stats['evaluaciones_mes_anterior']) /
             stats['evaluaciones_mes_anterior'] * 100), 1
        )
    else:
        stats['crecimiento'] = 0

    # Métricas de conversión comité
    cursor.execute(f"""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN estado_comite = 'approved' THEN 1 ELSE 0 END) as aprobados,
            SUM(CASE WHEN estado_comite = 'pending' THEN 1 ELSE 0 END) as pendientes
        FROM evaluaciones
        WHERE asesor IN ({ph})
    """, asesores_asignados)
    row = cursor.fetchone()
    stats['total_comite'] = row[0] or 0
    stats['aprobados_comite'] = row[1] or 0
    stats['pendientes_comite'] = row[2] or 0

    # Actividad por día de la semana (últimas 4 semanas)
    cursor.execute(f"""
        SELECT
            CASE strftime('%w', fecha_creacion)
                WHEN '0' THEN 'Dom'
                WHEN '1' THEN 'Lun'
                WHEN '2' THEN 'Mar'
                WHEN '3' THEN 'Mié'
                WHEN '4' THEN 'Jue'
                WHEN '5' THEN 'Vie'
                WHEN '6' THEN 'Sáb'
            END as dia,
            COUNT(*) as total
        FROM evaluaciones
        WHERE fecha_creacion >= date('now', '-28 days')
          AND asesor IN ({ph})
        GROUP BY strftime('%w', fecha_creacion)
        ORDER BY strftime('%w', fecha_creacion)
    """, asesores_asignados)
    stats['actividad_semanal'] = [{'dia': row[0], 'total': row[1]} for row in cursor.fetchall()]

    conn.close()
    return stats


def obtener_estadisticas_admin():
    """
    Obtiene estadísticas completas para administradores.

    Returns:
        dict: Estadísticas de administración
    """
    conn = conectar_db()
    cursor = conn.cursor()

    stats = {
        'rol': 'admin',
        'titulo': 'Panel de Administración',
        'icono': 'bi-shield-lock',
        'color': 'danger'
    }

    # Totales generales
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE activo = 1")
    stats['total_usuarios'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM simulaciones")
    stats['total_simulaciones'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM evaluaciones")
    stats['total_evaluaciones'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM lineas_credito WHERE activo = 1")
    stats['lineas_activas'] = cursor.fetchone()[0]

    # Usuarios por rol
    cursor.execute("""
        SELECT rol, COUNT(*) FROM usuarios
        WHERE activo = 1
        GROUP BY rol
    """)
    stats['usuarios_por_rol'] = {row[0]: row[1] for row in cursor.fetchall()}

    # Actividad hoy
    cursor.execute("""
        SELECT COUNT(*) FROM simulaciones
        WHERE DATE(timestamp) = DATE('now', 'localtime')
    """)
    stats['simulaciones_hoy'] = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM evaluaciones
        WHERE DATE(fecha_creacion) = DATE('now', 'localtime')
    """)
    stats['evaluaciones_hoy'] = cursor.fetchone()[0]

    # Casos de comité
    cursor.execute("""
        SELECT estado_comite, COUNT(*) FROM evaluaciones
        WHERE estado_comite IS NOT NULL AND estado_comite != ''
        GROUP BY estado_comite
    """)
    stats['casos_comite'] = {row[0]: row[1] for row in cursor.fetchall()}

    # Pendientes comité
    cursor.execute("""
        SELECT COUNT(*) FROM evaluaciones WHERE estado_comite = 'pending'
    """)
    stats['pendientes_comite'] = cursor.fetchone()[0]

    # Sistema
    stats['version_sistema'] = 'v72.8'
    stats['fecha_actual'] = datetime.now().strftime('%d/%m/%Y %H:%M')

    conn.close()
    return stats


def obtener_estadisticas_admin_tecnico():
    """
    Obtiene estadísticas para admin técnico.

    Returns:
        dict: Estadísticas técnicas
    """
    stats = obtener_estadisticas_admin()
    stats['rol'] = 'admin_tecnico'
    stats['titulo'] = 'Panel Técnico'
    stats['icono'] = 'bi-gear-wide-connected'
    stats['color'] = 'info'
    return stats


def obtener_estadisticas_por_rol(rol, username=None):
    """
    Obtiene estadísticas según el rol del usuario.

    Args:
        rol (str): Rol del usuario
        username (str): Username (requerido para filtrar por asignaciones)

    Returns:
        dict: Estadísticas personalizadas según rol
    """
    try:
        if rol == 'admin':
            return obtener_estadisticas_admin()
        elif rol == 'admin_tecnico':
            return obtener_estadisticas_admin_tecnico()
        elif rol == 'supervisor':
            return obtener_estadisticas_supervisor(username)
        elif rol == 'auditor':
            return obtener_estadisticas_auditor(username)
        elif rol == 'gerente':
            return obtener_estadisticas_gerente(username)
        elif rol == 'comite_credito':
            return obtener_estadisticas_comite()
        else:
            # Asesor u otro rol
            if username:
                return obtener_estadisticas_asesor(username)
            return {
                'rol': 'asesor',
                'titulo': 'Mi Panel',
                'icono': 'bi-person-workspace',
                'color': 'primary',
                'evaluaciones_hoy': 0,
                'simulaciones_hoy': 0
            }
    except Exception as e:
        print(f"❌ Error en obtener_estadisticas_por_rol: {e}")
        import traceback
        traceback.print_exc()
        return {
            'rol': rol or 'asesor',
            'titulo': 'Panel',
            'icono': 'bi-house',
            'color': 'secondary',
            'error': str(e),
            'evaluaciones_hoy': 0,
            'simulaciones_hoy': 0,
            'casos_pendientes': 0
        }


def obtener_resumen_navbar(rol, username=None):
    """
    Obtiene un resumen compacto para mostrar en el navbar.

    Args:
        rol (str): Rol del usuario
        username (str): Username

    Returns:
        dict: Resumen compacto con lista 'items'
    """
    try:
        conn = conectar_db()
        cursor = conn.cursor()

        resumen = {'items': []}

        if rol in ['admin', 'admin_tecnico']:
            # Pendientes de comité
            cursor.execute("""
                SELECT COUNT(*) FROM evaluaciones
                WHERE estado_comite = 'pending'
            """)
            pendientes = cursor.fetchone()[0]
            if pendientes > 0:
                resumen['items'].append({
                    'icono': 'bi-hourglass-split',
                    'valor': pendientes,
                    'texto': 'Pendientes comité',
                    'color': 'warning'
                })

            # Evaluaciones hoy
            cursor.execute("""
                SELECT COUNT(*) FROM evaluaciones
                WHERE DATE(fecha_creacion) = DATE('now', 'localtime')
            """)
            evals_hoy = cursor.fetchone()[0]
            resumen['items'].append({
                'icono': 'bi-graph-up',
                'valor': evals_hoy,
                'texto': 'Evaluaciones hoy',
                'color': 'info'
            })

        elif rol == 'supervisor':
            # === FILTRAR POR ASIGNACIONES ===
            asesores = []
            if username:
                cursor.execute("""
                    SELECT member_username FROM user_assignments
                    WHERE manager_username = ? AND activo = 1
                """, (username,))
                asesores = [r[0] for r in cursor.fetchall()]

            if asesores:
                ph = ','.join('?' * len(asesores))
                # Asesores que han trabajado hoy (del equipo)
                cursor.execute(f"""
                    SELECT COUNT(DISTINCT asesor) FROM evaluaciones
                    WHERE DATE(fecha_creacion) = DATE('now', 'localtime')
                      AND asesor IN ({ph})
                """, asesores)
                activos = cursor.fetchone()[0]

                # Evaluaciones equipo hoy
                cursor.execute(f"""
                    SELECT COUNT(*) FROM evaluaciones
                    WHERE DATE(fecha_creacion) = DATE('now', 'localtime')
                      AND asesor IN ({ph})
                """, asesores)
                evals = cursor.fetchone()[0]
            else:
                activos = 0
                evals = 0

            resumen['items'].append({
                'icono': 'bi-people',
                'valor': activos,
                'texto': 'Asesores activos',
                'color': 'success'
            })

            resumen['items'].append({
                'icono': 'bi-clipboard-check',
                'valor': evals,
                'texto': 'Evaluaciones hoy',
                'color': 'primary'
            })

        elif rol == 'gerente':
            # === FILTRAR POR JERARQUÍA ===
            supervisores = []
            asesores = []
            if username:
                cursor.execute("""
                    SELECT member_username FROM user_assignments
                    WHERE manager_username = ? AND activo = 1
                """, (username,))
                supervisores = [r[0] for r in cursor.fetchall()]
                
                if supervisores:
                    ph_sup = ','.join('?' * len(supervisores))
                    cursor.execute(f"""
                        SELECT member_username FROM user_assignments
                        WHERE manager_username IN ({ph_sup}) AND activo = 1
                    """, supervisores)
                    asesores = [r[0] for r in cursor.fetchall()]

            # Mostrar cantidad de supervisores
            resumen['items'].append({
                'icono': 'bi-people-fill',
                'valor': len(supervisores),
                'texto': 'Supervisores',
                'color': 'purple'
            })

            if asesores:
                ph = ','.join('?' * len(asesores))
                # Evaluaciones del mes
                cursor.execute(f"""
                    SELECT COUNT(*) FROM evaluaciones
                    WHERE strftime('%Y-%m', fecha_creacion) = strftime('%Y-%m', 'now')
                      AND asesor IN ({ph})
                """, asesores)
                evals_mes = cursor.fetchone()[0]
                
                resumen['items'].append({
                    'icono': 'bi-graph-up-arrow',
                    'valor': evals_mes,
                    'texto': 'Evals. mes',
                    'color': 'success'
                })

        elif rol == 'comite_credito':
            # Casos esperando
            cursor.execute("""
                SELECT COUNT(*) FROM evaluaciones
                WHERE estado_comite = 'pending'
            """)
            pendientes = cursor.fetchone()[0]
            resumen['items'].append({
                'icono': 'bi-inbox-fill',
                'valor': pendientes,
                'texto': 'Por decidir',
                'color': 'danger' if pendientes > 5 else 'warning'
            })

        elif rol == 'auditor':
            # Total evaluaciones mes
            cursor.execute("""
                SELECT COUNT(*) FROM evaluaciones
                WHERE strftime('%Y-%m', fecha_creacion) = strftime('%Y-%m', 'now')
            """)
            mes = cursor.fetchone()[0]
            resumen['items'].append({
                'icono': 'bi-file-earmark-text',
                'valor': mes,
                'texto': 'Evaluaciones mes',
                'color': 'info'
            })

        else:
            # Asesor
            if username:
                # Mis evaluaciones hoy
                cursor.execute("""
                    SELECT COUNT(*) FROM evaluaciones
                    WHERE asesor = ? AND DATE(fecha_creacion) = DATE('now', 'localtime')
                """, (username,))
                evals_hoy = cursor.fetchone()[0]
                resumen['items'].append({
                    'icono': 'bi-clipboard-check',
                    'valor': evals_hoy,
                    'texto': 'Mis evaluaciones hoy',
                    'color': 'primary'
                })

                # Casos nuevos (no vistos)
                cursor.execute("""
                    SELECT COUNT(*) FROM evaluaciones
                    WHERE asesor = ?
                      AND estado_comite IN ('approved', 'rejected')
                      AND (visto_por_asesor = 0 OR visto_por_asesor IS NULL)
                """, (username,))
                nuevos = cursor.fetchone()[0]
                if nuevos > 0:
                    resumen['items'].append({
                        'icono': 'bi-bell-fill',
                        'valor': nuevos,
                        'texto': 'Respuestas nuevas',
                        'color': 'danger'
                    })

        conn.close()
        return resumen

    except Exception as e:
        print(f"❌ Error en obtener_resumen_navbar: {e}")
        return {'items': []}
