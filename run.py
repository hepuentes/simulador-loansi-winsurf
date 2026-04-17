"""
RUN.PY - Punto de entrada principal de la aplicación Loansi
============================================================

Este script inicia la aplicación Flask usando el patrón Application Factory.

Uso:
    python run.py                    # Desarrollo (debug mode)
    python run.py --production       # Producción
    FLASK_ENV=production python run.py  # Usando variable de entorno
"""

import os
import sys
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Agregar directorio raíz al path
BASE_DIR = Path(__file__).parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Importar factory de la aplicación
from app import create_app


def main():
    """Función principal para iniciar la aplicación"""
    # Determinar entorno
    env = os.environ.get('FLASK_ENV', 'development')
    
    # Verificar argumentos de línea de comandos
    if '--production' in sys.argv:
        env = 'production'
    elif '--testing' in sys.argv:
        env = 'testing'
    
    # Crear aplicación
    app = create_app(env)
    
    # Configuración del servidor
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = env == 'development'
    
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║                      LOANSI - Sistema de Créditos                ║
║                                                                  ║
║  Versión: 72.9 (Arquitectura Modular)                            ║
║  Entorno: {env:<54}║
║  URL: http://{host}:{port:<48}║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    # Iniciar servidor
    app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True
    )


if __name__ == '__main__':
    main()
