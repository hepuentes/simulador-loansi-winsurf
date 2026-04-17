"""
EXTENSIONS.PY - Extensiones Flask centralizadas
================================================
"""

from flask_wtf.csrf import CSRFProtect

# CSRF Protection
csrf = CSRFProtect()


def init_extensions(app):
    """Inicializa todas las extensiones de Flask"""
    csrf.init_app(app)
    
    # Registrar manejador de errores CSRF
    from flask_wtf.csrf import CSRFError
    
    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        from flask import jsonify, request, render_template
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'error': 'Token CSRF inválido o expirado',
                'code': 'CSRF_ERROR',
                'message': 'Por favor recarga la página e intenta de nuevo.'
            }), 400
        
        return render_template('cliente/error.html', 
                             mensaje="Tu sesión ha expirado. Por favor recarga la página."), 400
