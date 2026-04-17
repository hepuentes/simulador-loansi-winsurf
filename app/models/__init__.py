"""
MODELS - Módulo de modelos y acceso a datos de Loansi
======================================================

Este módulo organiza todas las funciones de acceso a la base de datos.
Importa desde los módulos db_helpers existentes para mantener compatibilidad.
"""

# Importar desde los módulos existentes (compatibilidad)
import sys
from pathlib import Path

# Agregar directorio raíz al path
BASE_DIR = Path(__file__).parent.parent.parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Re-exportar funciones de configuración
from db_helpers import (
    cargar_configuracion,
    guardar_configuracion,
    cargar_scoring,
    guardar_scoring,
    cargar_evaluaciones,
    guardar_evaluacion,
    actualizar_evaluacion,
    cargar_simulaciones,
    guardar_simulacion,
    obtener_casos_comite,
    contar_casos_nuevos_asesor,
    obtener_usuario,
    crear_usuario,
    eliminar_linea_credito_db,
    eliminar_usuario_db,
    resolve_visible_usernames,
    obtener_evaluacion_por_timestamp,
    obtener_usuarios_completos,
    actualizar_usuario,
    ensure_user_assignments_table,
    get_assigned_usernames,
    get_assigned_usernames_recursive,
    get_all_assignments,
    add_assignment,
    remove_assignment,
    remove_assignment_by_id,
    get_managers_for_assignments,
    get_members_for_assignments,
    obtener_simulaciones_por_asesores,
    obtener_evaluaciones_por_asesores,
)

# Re-exportar funciones de scoring por línea
from db_helpers_scoring_linea import (
    obtener_lineas_credito_scoring,
    obtener_config_scoring_linea,
    guardar_config_scoring_linea,
    obtener_niveles_riesgo_linea,
    guardar_niveles_riesgo_linea,
    obtener_factores_rechazo_linea,
    guardar_factores_rechazo_linea,
    agregar_factor_rechazo_linea,
    eliminar_factor_rechazo,
    obtener_criterios_linea,
    guardar_criterio_linea,
    copiar_config_scoring,
    cargar_scoring_por_linea,
    invalidar_cache_scoring_linea,
    verificar_tablas_scoring_linea,
    crear_config_scoring_linea_defecto,
)

# Re-exportar funciones de estados
from db_helpers_estados import (
    marcar_desembolsado,
    marcar_desistido,
    revertir_estado_final,
    obtener_casos_por_estado_final,
    obtener_estadisticas_estados,
    obtener_resumen_asesor,
    obtener_caso_completo,
)

# Re-exportar funciones de dashboard
from db_helpers_dashboard import (
    obtener_estadisticas_por_rol,
    obtener_resumen_navbar,
    obtener_usuarios_asignados_detalle,
    obtener_jerarquia_gerente,
)

# Re-exportar conexión a DB
from database import conectar_db, DB_PATH

__all__ = [
    # Conexión
    'conectar_db',
    'DB_PATH',
    # Configuración
    'cargar_configuracion',
    'guardar_configuracion',
    # Scoring
    'cargar_scoring',
    'guardar_scoring',
    'cargar_scoring_por_linea',
    'obtener_lineas_credito_scoring',
    'obtener_config_scoring_linea',
    'guardar_config_scoring_linea',
    'obtener_niveles_riesgo_linea',
    'guardar_niveles_riesgo_linea',
    'obtener_factores_rechazo_linea',
    'guardar_factores_rechazo_linea',
    'agregar_factor_rechazo_linea',
    'eliminar_factor_rechazo',
    'obtener_criterios_linea',
    'guardar_criterio_linea',
    'copiar_config_scoring',
    'invalidar_cache_scoring_linea',
    'verificar_tablas_scoring_linea',
    'crear_config_scoring_linea_defecto',
    # Evaluaciones
    'cargar_evaluaciones',
    'guardar_evaluacion',
    'actualizar_evaluacion',
    'obtener_evaluacion_por_timestamp',
    'obtener_evaluaciones_por_asesores',
    # Simulaciones
    'cargar_simulaciones',
    'guardar_simulacion',
    'obtener_simulaciones_por_asesores',
    # Comité
    'obtener_casos_comite',
    'contar_casos_nuevos_asesor',
    # Usuarios
    'obtener_usuario',
    'crear_usuario',
    'eliminar_usuario_db',
    'obtener_usuarios_completos',
    'actualizar_usuario',
    # Asignaciones
    'ensure_user_assignments_table',
    'get_assigned_usernames',
    'get_assigned_usernames_recursive',
    'get_all_assignments',
    'add_assignment',
    'remove_assignment',
    'remove_assignment_by_id',
    'get_managers_for_assignments',
    'get_members_for_assignments',
    'resolve_visible_usernames',
    # Líneas de crédito
    'eliminar_linea_credito_db',
    # Estados
    'marcar_desembolsado',
    'marcar_desistido',
    'revertir_estado_final',
    'obtener_casos_por_estado_final',
    'obtener_estadisticas_estados',
    'obtener_resumen_asesor',
    'obtener_caso_completo',
    # Dashboard
    'obtener_estadisticas_por_rol',
    'obtener_resumen_navbar',
    'obtener_usuarios_asignados_detalle',
    'obtener_jerarquia_gerente',
]
