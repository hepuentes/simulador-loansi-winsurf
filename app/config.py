"""
CONFIG.PY - Configuración centralizada de la aplicación Loansi
===============================================================
"""

import os
from pathlib import Path
from datetime import timedelta

# Directorio base del proyecto
BASE_DIR = Path(__file__).parent.parent.resolve()


class Config:
    """Configuración base de la aplicación"""
    
    # ============================================
    # CONFIGURACIÓN GENERAL
    # ============================================
    SECRET_KEY = os.environ.get('SECRET_KEY', 'loansi_key_super_secreta_2025')
    
    # ============================================
    # BASE DE DATOS
    # ============================================
    DB_PATH = BASE_DIR / 'loansi.db'
    SQLITE_DEBUG = os.environ.get('SQLITE_DEBUG', 'True').lower() == 'true'
    
    # ============================================
    # SESIONES
    # ============================================
    PERMANENT_SESSION_LIFETIME = timedelta(hours=4)
    SESSION_COOKIE_SECURE = False  # True en producción con HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # ============================================
    # CSRF
    # ============================================
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hora
    
    # ============================================
    # RATE LIMITING
    # ============================================
    MAX_LOGIN_ATTEMPTS = 3
    LOCKOUT_DURATION = timedelta(minutes=15)
    ATTEMPT_WINDOW = timedelta(minutes=5)
    CLEANUP_THRESHOLD = 30
    LOGIN_ATTEMPTS_FILE = BASE_DIR / 'login_attempts.json'
    
    # ============================================
    # BACKUPS
    # ============================================
    BACKUP_DIR = BASE_DIR / 'backups'
    MAX_BACKUPS = 7
    
    # ============================================
    # ZONA HORARIA
    # ============================================
    TIMEZONE_OFFSET_HOURS = -5  # Colombia (UTC-5)
    
    # ============================================
    # CONSTANTES DE NEGOCIO
    # ============================================
    # Conversión exacta semanas/mes: 52 semanas ÷ 12 meses = 4.333333...
    SEMANAS_POR_MES = 52.0 / 12.0

    # ============================================
    # PARAMETROS LABORALES COLOMBIA
    # ============================================
    # NOTA PARA HECTOR: Cada enero actualizar smlv y subsidio_transporte.
    # Los porcentajes rara vez cambian.
    PARAMETROS_LABORALES = {
        "anio": 2026,
        "smlv": 1_750_905,              # Decreto 1469 del 29-dic-2025
        "subsidio_transporte": 249_095, # Decreto 1470 del 29-dic-2025
        "pct_salud_empleado": 0.04,     # 4% Ley 100/1993
        "pct_pension_empleado": 0.04,   # 4% Ley 100/1993
        "pct_fsp_4_smlv": 0.01,         # Fondo Solidaridad Pensional >4 SMLV
        "pct_retencion_umbral": 5_470_000,
        # Valores calculados de referencia
        "smlv_065": 1_138_088,   # 0.65 SMLV — umbral mínimo extracto/ingreso_decision
        "smlv_080": 1_400_724,   # 0.80 SMLV — zona advertencia MiDecisor subestimación
        "smlv_150": 2_626_358,   # 1.5 SMLV
        "smlv_200": 3_501_810,   # 2 SMLV — ingreso mínimo LoansiMoto Avanzada
        "salud_emp_valor": 70_036,    # 4% × 1.750.905
        "pension_emp_valor": 70_036,  # 4% × 1.750.905
    }


class DevelopmentConfig(Config):
    """Configuración para desarrollo"""
    DEBUG = True
    SQLITE_DEBUG = True


class ProductionConfig(Config):
    """Configuración para producción"""
    DEBUG = False
    SQLITE_DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    """Configuración para testing"""
    TESTING = True
    DB_PATH = BASE_DIR / 'test_loansi.db'


# Diccionario de configuraciones
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(env_name=None):
    """Obtiene la configuración según el entorno"""
    if env_name is None:
        env_name = os.environ.get('FLASK_ENV', 'default')
    return config_by_name.get(env_name, DevelopmentConfig)
