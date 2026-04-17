"""
APP - Factory de la aplicación Flask Loansi
============================================

Este módulo implementa el patrón Application Factory para Flask.
Permite crear instancias de la aplicación con diferentes configuraciones.

CORREGIDO: 2026-01-18 - Agregado alias formatear_fecha para compatibilidad con templates
"""

import os
import sys
from pathlib import Path
from flask import Flask, session, g

# Agregar directorio raíz al path para importaciones
BASE_DIR = Path(__file__).parent.parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def create_app(config_name=None):
    """
    Factory de la aplicación Flask.

    Args:
        config_name: Nombre de la configuración ('development', 'production', 'testing')

    Returns:
        Flask: Instancia configurada de la aplicación
    """
    # Configurar logging básico (compatible con PythonAnywhere)
    import logging
    logging.basicConfig(
        level=logging.ERROR,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Crear instancia de Flask
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / 'templates'),
        static_folder=str(BASE_DIR / 'static')
    )

    # Cargar configuración
    from .config import get_config
    config = get_config(config_name)
    app.config.from_object(config)

    # Configuración adicional
    app.config['PERMANENT_SESSION_LIFETIME'] = config.PERMANENT_SESSION_LIFETIME

    # Inicializar extensiones
    from .extensions import init_extensions
    init_extensions(app)

    # Registrar filtros Jinja2
    register_jinja_filters(app)

    # Registrar context processors
    register_context_processors(app)

    # Registrar manejadores de errores
    register_error_handlers(app)

    # Registrar blueprints (rutas)
    from .routes import register_blueprints
    register_blueprints(app)

    # Inicializar sistema de permisos
    try:
        from permisos import inicializar_permisos
        inicializar_permisos(app)
    except Exception as e:
        print(f"⚠️ Error inicializando permisos: {e}")

    # Asegurar criterio mora_sector_telcos en todas las líneas
    try:
        from db_helpers_scoring_linea import asegurar_criterio_mora_telcos
        asegurar_criterio_mora_telcos()
    except Exception as e:
        print(f"⚠️ Error asegurando criterio mora_telcos: {e}")

    print(f"✅ Aplicación Loansi creada con configuración: {config_name or 'default'}")

    return app


def register_jinja_filters(app):
    """Registra filtros personalizados para Jinja2"""
    from .utils.formatting import formatear_monto, formatear_con_miles, formatear_numero_resultado, formatear_valor_criterio
    from .utils.timezone import formatear_fecha_colombia

    @app.template_filter('formato_moneda')
    def formato_moneda_filter(valor):
        return formatear_monto(valor)

    @app.template_filter('formato_miles')
    def formato_miles_filter(numero):
        return formatear_con_miles(numero)

    @app.template_filter('formato_fecha')
    def formato_fecha_filter(fecha):
        return formatear_fecha_colombia(fecha)
    
    # =====================================================
    # CRÍTICO: Alias para compatibilidad con templates
    # Algunos templates usan 'formatear_fecha' en lugar de 'formato_fecha'
    # =====================================================
    @app.template_filter('formatear_fecha')
    def formatear_fecha_filter(fecha):
        return formatear_fecha_colombia(fecha)

    @app.template_filter('tojson_safe')
    def tojson_safe_filter(obj):
        """Serializa a JSON de forma segura para templates"""
        import json
        return json.dumps(obj, ensure_ascii=False)

    @app.template_filter('formato_numero')
    def formato_numero_filter(valor, decimales=None):
        """Formatea número con coma decimal y separador de miles"""
        return formatear_numero_resultado(valor, decimales)

    @app.template_filter('formato_valor')
    def formato_valor_filter(valor, es_moneda=False, es_porcentaje=False):
        """Formatea valor de criterio (moneda, porcentaje o número)"""
        return formatear_valor_criterio(valor, es_moneda, es_porcentaje)


def register_context_processors(app):
    """Registra context processors para templates"""

    @app.context_processor
    def inject_navbar_stats():
        """Inyecta estadísticas del navbar en todos los templates"""
        if session.get('autorizado'):
            try:
                from db_helpers_dashboard import obtener_resumen_navbar
                rol = session.get('rol', 'asesor')
                username = session.get('username')
                navbar_stats = obtener_resumen_navbar(rol, username)
                return {'navbar_stats': navbar_stats}
            except Exception as e:
                print(f"⚠️ Error obteniendo navbar stats: {e}")
        return {'navbar_stats': {'items': []}}

    @app.context_processor
    def inject_user_info():
        """Inyecta información del usuario en todos los templates"""
        return {
            'user_autorizado': session.get('autorizado', False),
            'user_nombre': session.get('nombre_completo', session.get('username', '')),
            'user_rol': session.get('rol', 'asesor'),
            'user_username': session.get('username', '')
        }

    @app.context_processor
    def inject_theme():
        """Inyecta configuración de tema"""
        return {
            'theme': session.get('theme', 'light')
        }


def register_error_handlers(app):
    """Registra manejadores de errores HTTP"""
    from flask import render_template, jsonify, request

    @app.errorhandler(400)
    def bad_request_error(error):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Solicitud incorrecta',
                'code': 'BAD_REQUEST'
            }), 400
        return render_template('cliente/error.html',
                             mensaje='Solicitud incorrecta'), 400

    @app.errorhandler(403)
    def forbidden_error(error):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Acceso denegado',
                'code': 'FORBIDDEN'
            }), 403
        return render_template('cliente/error.html',
                             mensaje='No tienes permiso para acceder a esta página'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Recurso no encontrado',
                'code': 'NOT_FOUND'
            }), 404
        return render_template('cliente/error.html',
                             mensaje='Página no encontrada'), 404

    @app.errorhandler(500)
    def internal_error(error):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Error interno del servidor',
                'code': 'INTERNAL_ERROR'
            }), 500
        return render_template('cliente/error.html',
                             mensaje='Error interno del servidor'), 500


# ============================================================================
# VERSIÓN DEL SISTEMA
# ============================================================================
__version__ = '75.11'
__version_date__ = '2026-01-18'