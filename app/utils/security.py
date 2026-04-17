"""
SECURITY.PY - Utilidades de seguridad y rate limiting
======================================================
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path

# Configuración de rate limiting
MAX_LOGIN_ATTEMPTS = 3
LOCKOUT_DURATION = timedelta(minutes=15)
ATTEMPT_WINDOW = timedelta(minutes=5)
CLEANUP_THRESHOLD = 30

# Archivo para persistir intentos de login
BASE_DIR = Path(__file__).parent.parent.parent.resolve()
LOGIN_ATTEMPTS_FILE = BASE_DIR / 'login_attempts.json'


def cargar_login_attempts():
    """
    Carga intentos de login desde archivo JSON.
    Limpia automáticamente registros antiguos (> 15 minutos).

    Returns:
        dict: {ip_address: [timestamp_str1, timestamp_str2, ...]}
    """
    try:
        if os.path.exists(LOGIN_ATTEMPTS_FILE):
            with open(LOGIN_ATTEMPTS_FILE, "r") as f:
                attempts = json.load(f)

            # Limpiar registros antiguos
            now = datetime.now()
            cleaned = {}
            for ip, timestamps in attempts.items():
                # Filtrar solo intentos recientes
                recent = []
                for ts_str in timestamps:
                    try:
                        ts = datetime.fromisoformat(ts_str)
                        if now - ts < LOCKOUT_DURATION:
                            recent.append(ts_str)
                    except (ValueError, TypeError):
                        continue
                if recent:
                    cleaned[ip] = recent

            # Guardar versión limpia si cambió
            if cleaned != attempts:
                with open(LOGIN_ATTEMPTS_FILE, "w") as f:
                    json.dump(cleaned, f)

            return cleaned
        return {}
    except (json.JSONDecodeError, IOError):
        return {}


def guardar_login_attempts(attempts):
    """
    Guarda intentos de login en archivo JSON.
    Realiza limpieza automática si el archivo crece demasiado.

    Args:
        attempts: Diccionario de intentos
    """
    try:
        # Limpiar si hay muchos registros
        if len(attempts) > CLEANUP_THRESHOLD:
            now = datetime.now()
            cleaned = {}
            for ip, timestamps in attempts.items():
                recent = [
                    ts for ts in timestamps
                    if (now - datetime.fromisoformat(ts)) < LOCKOUT_DURATION
                ]
                if recent:
                    cleaned[ip] = recent
            attempts = cleaned

        with open(LOGIN_ATTEMPTS_FILE, "w") as f:
            json.dump(attempts, f, indent=2)
    except IOError:
        pass  # Silenciosamente ignorar errores de escritura


def check_rate_limit(ip_address):
    """
    Verifica si una IP está bloqueada por exceso de intentos.

    Args:
        ip_address: Dirección IP a verificar

    Returns:
        dict: {'is_locked': bool, 'remaining_time': int (segundos), 'attempts_left': int}
    """
    attempts = cargar_login_attempts()
    
    if ip_address not in attempts:
        return {
            'is_locked': False,
            'remaining_time': 0,
            'attempts_left': MAX_LOGIN_ATTEMPTS
        }
    
    ip_attempts = attempts[ip_address]
    now = datetime.now()
    
    # Contar intentos recientes (dentro de la ventana)
    recent_attempts = []
    for ts_str in ip_attempts:
        try:
            ts = datetime.fromisoformat(ts_str)
            if now - ts < ATTEMPT_WINDOW:
                recent_attempts.append(ts)
        except (ValueError, TypeError):
            continue
    
    # Verificar si está bloqueado
    if len(recent_attempts) >= MAX_LOGIN_ATTEMPTS:
        # Calcular tiempo restante de bloqueo
        oldest_attempt = min(recent_attempts)
        lockout_end = oldest_attempt + LOCKOUT_DURATION
        remaining = (lockout_end - now).total_seconds()
        
        if remaining > 0:
            return {
                'is_locked': True,
                'remaining_time': int(remaining),
                'attempts_left': 0
            }
    
    return {
        'is_locked': False,
        'remaining_time': 0,
        'attempts_left': MAX_LOGIN_ATTEMPTS - len(recent_attempts)
    }


def record_failed_attempt(ip_address):
    """
    Registra un intento fallido de login para una IP.

    Args:
        ip_address: Dirección IP del intento
    """
    attempts = cargar_login_attempts()
    
    if ip_address not in attempts:
        attempts[ip_address] = []
    
    attempts[ip_address].append(datetime.now().isoformat())
    guardar_login_attempts(attempts)


def clear_attempts(ip_address):
    """
    Limpia los intentos de una IP después de login exitoso.

    Args:
        ip_address: Dirección IP a limpiar
    """
    attempts = cargar_login_attempts()
    
    if ip_address in attempts:
        del attempts[ip_address]
        guardar_login_attempts(attempts)


def cleanup_old_attempts():
    """
    Limpia todos los intentos antiguos del archivo.
    Llamar periódicamente para mantenimiento.
    """
    attempts = cargar_login_attempts()
    now = datetime.now()
    
    cleaned = {}
    for ip, timestamps in attempts.items():
        recent = []
        for ts_str in timestamps:
            try:
                ts = datetime.fromisoformat(ts_str)
                if now - ts < LOCKOUT_DURATION:
                    recent.append(ts_str)
            except (ValueError, TypeError):
                continue
        if recent:
            cleaned[ip] = recent
    
    guardar_login_attempts(cleaned)
    return len(attempts) - len(cleaned)  # Cantidad de IPs limpiadas
