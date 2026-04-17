# Simulador Loansi

Sistema de simulación y evaluación de créditos con arquitectura modular Flask.

## 🏗️ Arquitectura del Sistema

El sistema ha sido refactorizado siguiendo una arquitectura modular para mejorar la mantenibilidad, escalabilidad y testabilidad del código.

### Estructura de Directorios

```
/workspace/
├── app/                          # Paquete principal de la aplicación
│   ├── __init__.py              # Factory de aplicación Flask
│   ├── config.py                # Configuración centralizada
│   ├── extensions.py            # Extensiones Flask (CSRF, etc.)
│   │
│   ├── routes/                  # Blueprints de rutas
│   │   ├── __init__.py         # Registro de blueprints
│   │   ├── auth.py             # Autenticación (login/logout)
│   │   ├── main.py             # Rutas principales (home, dashboard)
│   │   ├── simulador.py        # Simulador de crédito
│   │   ├── scoring_routes.py   # Evaluación de scoring
│   │   ├── admin_routes.py     # Panel de administración
│   │   ├── comite_routes.py    # Comité de crédito
│   │   ├── api_routes.py       # API REST
│   │   └── asesor_routes.py    # Rutas de asesores
│   │
│   ├── services/               # Lógica de negocio
│   │   ├── __init__.py
│   │   ├── scoring_service.py  # Cálculos de scoring
│   │   ├── simulacion_service.py  # Cálculos financieros
│   │   └── seguro_service.py   # Cálculos de seguros
│   │
│   ├── models/                 # Acceso a datos
│   │   └── __init__.py        # Re-exporta funciones de db_helpers
│   │
│   └── utils/                  # Utilidades
│       ├── __init__.py
│       ├── timezone.py         # Zona horaria Colombia
│       ├── formatting.py       # Formateo de datos
│       ├── security.py         # Rate limiting, autenticación
│       ├── backup.py           # Sistema de backups
│       └── logging.py          # Logging personalizado
│
├── templates/                   # Templates Jinja2
│   ├── admin/                  # Templates de administración
│   ├── asesor/                 # Templates de asesores
│   ├── cliente/                # Templates de clientes
│   ├── dashboards/             # Dashboards por rol
│   └── partials/               # Componentes reutilizables
│
├── static/                     # Archivos estáticos
│   ├── css/                    # Estilos CSS
│   └── js/                     # JavaScript
│
├── flask_app.py                # Aplicación Flask (compatibilidad)
├── run.py                      # Punto de entrada principal
├── database.py                 # Esquema de base de datos
├── permisos.py                 # Sistema RBAC de permisos
├── db_helpers.py               # Helpers de base de datos
├── db_helpers_dashboard.py     # Helpers para dashboards
├── db_helpers_estados.py       # Helpers para estados de crédito
├── db_helpers_scoring_linea.py # Helpers para scoring multi-línea
│
├── loansi.db                   # Base de datos SQLite
├── requirements.txt            # Dependencias Python
└── README.md                   # Este archivo
```

## 🚀 Instalación

### Requisitos Previos

- Python 3.9+
- pip (gestor de paquetes Python)

### Instalación

1. Clonar el repositorio:
```bash
git clone <url-del-repositorio>
cd simulador-loansi-cursor
```

2. Crear entorno virtual (recomendado):
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Iniciar la aplicación:
```bash
# Desarrollo
python run.py

# O usando el archivo original
python flask_app.py
```

## 📦 Módulos Principales

### `app/` - Paquete de Aplicación

#### Factory Pattern (`app/__init__.py`)
```python
from app import create_app

app = create_app('development')  # o 'production', 'testing'
```

#### Configuración (`app/config.py`)
- `DevelopmentConfig`: Debug habilitado, logs detallados
- `ProductionConfig`: Optimizado para producción
- `TestingConfig`: Configuración para tests

### `app/routes/` - Blueprints

Cada módulo de rutas es un Blueprint Flask independiente:

- **auth**: Login, logout, manejo de sesiones
- **main**: Página principal, dashboard
- **simulador**: Simulación de créditos, capacidad de pago
- **scoring**: Evaluación de riesgo crediticio
- **admin**: Panel de administración
- **comite**: Comité de crédito
- **api**: Endpoints REST
- **asesor**: Funcionalidades de asesores

### `app/services/` - Lógica de Negocio

#### ScoringService
```python
from app.services import ScoringService

scoring = ScoringService()
resultado = scoring.calcular_scoring(valores, linea_credito="Libranza")
```

#### SimulacionService
```python
from app.services import SimulacionService

simulacion = SimulacionService()
resultado = simulacion.simular_credito(
    monto=5000000,
    plazo=24,
    linea_credito="Libranza"
)
```

#### SeguroService
```python
from app.services import SeguroService

seguro = SeguroService()
calculo = seguro.calcular_seguro_anual(edad=35, monto=5000000, plazo_meses=24)
```

### `app/utils/` - Utilidades

#### Timezone
```python
from app.utils import obtener_hora_colombia, formatear_fecha_colombia
```

#### Formatting
```python
from app.utils import formatear_monto, parse_currency_value
```

#### Security
```python
from app.utils import check_rate_limit, record_failed_attempt
```

## 🔐 Sistema de Permisos (RBAC)

El sistema implementa Control de Acceso Basado en Roles:

### Roles Disponibles
- `admin`: Acceso total
- `admin_tecnico`: Administración técnica
- `gerente`: Gestión ejecutiva
- `supervisor`: Supervisión de equipos
- `auditor`: Auditoría y control
- `comite_credito`: Aprobación de créditos
- `asesor`: Operaciones básicas

### Uso de Permisos
```python
from permisos import requiere_permiso, tiene_permiso

@app.route('/admin/scoring')
@requiere_permiso('cfg_sco_editar')
def editar_scoring():
    pass

# Verificación programática
if tiene_permiso('com_aprobar'):
    # Mostrar botón de aprobar
```

## 📊 Base de Datos

El sistema usa SQLite con las siguientes tablas principales:

- `usuarios`: Gestión de usuarios
- `lineas_credito`: Configuración de productos
- `evaluaciones`: Evaluaciones de scoring
- `simulaciones`: Historial de simulaciones
- `configuracion_sistema`: Configuración general
- `configuracion_scoring`: Parámetros de scoring
- `user_assignments`: Asignaciones de equipo
- `auditoria`: Registro de auditoría

## 🧪 Testing

```bash
# Ejecutar tests (cuando estén implementados)
python -m pytest tests/

# Test de la base de datos
python database.py
```

## 🔄 Migración Gradual

El sistema mantiene compatibilidad con `flask_app.py` mientras se migra gradualmente a la arquitectura modular:

1. **Fase actual**: Módulos creados, `flask_app.py` funcional
2. **Siguiente fase**: Migrar rutas a blueprints
3. **Fase final**: Deprecar funciones duplicadas

## 📝 Convenciones de Código

- **Python**: PEP 8
- **Imports**: Organizados (stdlib, third-party, local)
- **Docstrings**: Google style
- **Templates**: Jinja2 con herencia
- **CSS**: BEM methodology

## 🤝 Contribución

1. Crear branch desde `main`
2. Implementar cambios
3. Escribir/actualizar tests
4. Crear Pull Request

## 📄 Licencia

Proyecto privado - Todos los derechos reservados.

---

**Versión**: 72.9  
**Fecha**: 2026-01-16  
**Arquitectura**: Modular Flask
