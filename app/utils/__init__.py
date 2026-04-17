"""
UTILS - Módulo de utilidades de la aplicación Loansi
=====================================================
"""

from .timezone import (
    obtener_hora_colombia,
    obtener_hora_colombia_naive,
    formatear_fecha_colombia,
    parsear_timestamp_naive
)

from .formatting import (
    formatear_monto,
    formatear_con_miles,
    parse_currency_value
)

from .finance import (
    calcular_cuota,
    calcular_edad_desde_fecha,
    calcular_seguro_proporcional_fecha,
    calcular_seguro_anual,
    obtener_aval_dinamico,
    obtener_tasa_por_nivel_riesgo,
    SEMANAS_POR_MES
)

from .security import (
    cargar_login_attempts,
    guardar_login_attempts,
    check_rate_limit,
    record_failed_attempt,
    clear_attempts,
    cleanup_old_attempts
)

from .backup import (
    crear_backup_con_rotacion,
    recuperar_desde_backup_mas_reciente
)

from .logging import log_db_operation

__all__ = [
    # Timezone
    'obtener_hora_colombia',
    'obtener_hora_colombia_naive',
    'formatear_fecha_colombia',
    'parsear_timestamp_naive',
    # Formatting
    'formatear_monto',
    'formatear_con_miles',
    'parse_currency_value',
    # Security
    'cargar_login_attempts',
    'guardar_login_attempts',
    'check_rate_limit',
    'record_failed_attempt',
    'clear_attempts',
    'cleanup_old_attempts',
    # Backup
    'crear_backup_con_rotacion',
    'recuperar_desde_backup_mas_reciente',
    # Logging
    'log_db_operation',
    # Finance
    'calcular_cuota',
    'calcular_edad_desde_fecha',
    'calcular_seguro_proporcional_fecha',
    'calcular_seguro_anual',
    'obtener_aval_dinamico',
    'obtener_tasa_por_nivel_riesgo',
    'SEMANAS_POR_MES',
]
