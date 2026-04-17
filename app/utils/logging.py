"""
LOGGING.PY - Utilidades de logging para la aplicación
======================================================
"""

from datetime import datetime
import os

# Modo debug para SQLite (puede cambiarse desde config)
SQLITE_DEBUG = os.environ.get('SQLITE_DEBUG', 'True').lower() == 'true'


def log_db_operation(operation, details="", level="INFO"):
    """
    Logger específico para operaciones de base de datos.
    Facilita debugging en producción.

    Args:
        operation (str): Nombre de la operación (ej: "CARGAR_EVALUACIONES")
        details (str): Detalles adicionales
        level (str): INFO, WARNING, ERROR
    """
    if not SQLITE_DEBUG and level == "INFO":
        return

    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = {"INFO": "🔵", "WARNING": "⚠️", "ERROR": "❌"}.get(level, "ℹ️")

    message = f"{prefix} [{timestamp}] SQLite-{operation}"
    if details:
        message += f": {details}"

    print(message)  # Va a logs de la aplicación


def log_security_event(event_type, details="", user=None, ip=None):
    """
    Logger para eventos de seguridad.

    Args:
        event_type (str): Tipo de evento (LOGIN_FAILED, ACCESS_DENIED, etc.)
        details (str): Detalles del evento
        user (str): Usuario relacionado
        ip (str): Dirección IP
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    message = f"🔒 [{timestamp}] SECURITY-{event_type}"
    if user:
        message += f" | User: {user}"
    if ip:
        message += f" | IP: {ip}"
    if details:
        message += f" | {details}"

    print(message)


def log_audit(action, user, table=None, record_id=None, details=None):
    """
    Logger para auditoría de acciones.

    Args:
        action (str): Acción realizada
        user (str): Usuario que realizó la acción
        table (str): Tabla afectada
        record_id: ID del registro afectado
        details (str): Detalles adicionales
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    message = f"📝 [{timestamp}] AUDIT | {action} | User: {user}"
    if table:
        message += f" | Table: {table}"
    if record_id:
        message += f" | ID: {record_id}"
    if details:
        message += f" | {details}"

    print(message)
