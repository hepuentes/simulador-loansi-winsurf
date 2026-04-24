# Estado del Sistema LOANSI — Recuperación tras pérdida por git
> Generado: 24 de abril de 2026  
> Propósito: Documentar qué se perdió, qué se restauró y el estado actual de configuración para que otra IA pueda continuar el trabajo.

---

## 1. Qué ocurrió (contexto del problema)

Se hizo un `git pull` desde el remoto que **sobreescribió el `loansi.db` local**, que tenía configuración manual avanzada no commiteada. El remoto tenía una versión anterior vacía o parcial de la base de datos.

### Lo que se perdió definitivamente (sin backup recuperable):
- **Proveedores IA** (`ia_proveedores`): tabla con 0 columnas — corrupción completa. Las API keys, modelos, URLs y nombres de los proveedores configurados manualmente se perdieron.
- **Fuentes de extracción por criterio** (`criterios_scoring_master.fuente_extraccion`, `instruccion_extraccion`, `activo_extraccion`): columnas que existían pero quedaron vacías. Las instrucciones IA personalizadas por criterio (escritas manualmente, criterio por criterio) se perdieron.
- **Parámetros del sistema** (`parametros_sistema`): la tabla existía pero tenía la columna `updated_at` en lugar de `ultima_actualizacion`, causando que la página `/admin/parametros-sistema` se viera en blanco (error silencioso en el SELECT).

### Lo que SÍ sobrevivió (datos de scoring principales):
- Todas las evaluaciones (392 registros)
- Criterios master (52), criterios por línea (98), factores de rechazo (84)
- Líneas de crédito (9), scoring config (9), niveles de riesgo (30)
- Usuarios (15), permisos, asignaciones

---

## 2. Lo que se restauró / regeneró

### 2.1 Parámetros del sistema (RESTAURADO)
- **Fix aplicado**: `ALTER TABLE parametros_sistema RENAME COLUMN updated_at TO ultima_actualizacion`
- La función `obtener_parametros_sistema()` en `db_helpers.py` consultaba `ultima_actualizacion` pero la columna se llamaba `updated_at`. Ahora coinciden.
- **Ruta activa**: `/admin/parametros-sistema`

### 2.2 Proveedores IA (PARCIALMENTE RESTAURADO)
- La tabla `ia_proveedores` fue recreada desde cero (drop + create).
- El usuario reingresó manualmente 2 proveedores (ver sección 4.3).
- Las API keys NO estaban en ningún backup — tuvieron que reingresarse.

### 2.3 Instrucciones de extracción IA por criterio (REGENERADO)
- Se creó el script `_configurar_extraccion_ia.py` que generó instrucciones optimizadas para los 47 criterios activos.
- Instrucciones diseñadas para funcionar con cualquier IA (Claude, GPT-4, Gemini).
- Todas bajo 3000 caracteres (máximo del campo en la UI).
- Diferenciación entre criterios numéricos (devuelven número) y de selección (devuelven valor canónico).

---

## 3. Estructura de archivos del proyecto

```
simulador-loansi-winsurf/
├── run.py                          ← Entry point desarrollo (puerto 5000)
├── database.py                     ← Esquema SQL 33+ tablas + conectar_db()
├── db_helpers.py                   ← Queries generales (~2609 líneas)
├── db_helpers_comite.py            ← Queries comité crédito
├── db_helpers_dashboard.py         ← Queries dashboards
├── db_helpers_estados.py           ← Queries estados
├── db_helpers_scoring_linea.py     ← Queries scoring por línea (~1816 líneas)
├── criterios_sistema.py            ← Criterios predefinidos de scoring
├── permisos.py                     ← Decoradores @requiere_permiso, @login_required
├── loansi.db                       ← Base de datos SQLite RAÍZ (NO en instance/)
├── requirements.txt
│
├── app/
│   ├── __init__.py                 ← create_app() + registro de blueprints
│   ├── config.py                   ← Configuración por entorno (Dev/Prod/Test)
│   ├── config_extraccion.py        ← Config de fuentes IA por tipo de documento
│   ├── extensions.py               ← Solo CSRFProtect
│   ├── models/__init__.py          ← FACHADA: re-exports de db_helpers (NO hay ORM)
│   │
│   ├── routes/
│   │   ├── admin_routes.py         ← Admin panel (parámetros, proveedores IA, líneas)
│   │   ├── api_routes.py           ← Endpoints AJAX
│   │   ├── asesor_routes.py
│   │   ├── auth.py                 ← Login/logout
│   │   ├── comite_routes.py
│   │   ├── extraccion_routes.py    ← Subida de documentos + extracción IA
│   │   ├── main.py
│   │   ├── scoring_routes.py       ← Motor scoring + triangulación ingresos
│   │   └── simulador.py
│   │
│   └── services/
│       ├── extractor_service.py    ← Clase ExtractorService (1125+ líneas)
│       ├── interpolation_service.py
│       ├── scoring_service.py
│       ├── seguro_service.py
│       ├── simulacion_service.py
│       ├── pdf_fraud_service.py
│       ├── validacion_cruzada_service.py
│       └── validacion_nomina_service.py
│
├── migrations/
│   ├── add_ia_proveedores.py       ← Crea tabla ia_proveedores
│   ├── add_ia_config.py            ← Inserta config IA en configuracion_sistema
│   ├── add_parametros_sistema.py   ← Crea tabla parametros_sistema
│   ├── add_extraccion_fields.py    ← Agrega columnas extracción a criterios_master
│   ├── add_interpolation_fields.py ← Agrega campos interpolación a niveles_riesgo
│   ├── add_prioridad_proveedores.py← Agrega columna prioridad a ia_proveedores
│   ├── add_diferencial_genero.py
│   ├── update_alertas_extracto_rangos.py
│   └── update_instrucciones_extracto_bancario.py  ← ⚠️ Ver sección 7
│
└── templates/
    ├── scoring.html                ← Monolítico: 2781+ líneas HTML+JS+Jinja2
    ├── parametros_sistema.html
    ├── integraciones.html          ← UI de proveedores IA
    └── admin/ asesor/ cliente/ dashboards/ partials/
```

---

## 4. Estado actual de la base de datos

### 4.1 Parámetros del Sistema (`parametros_sistema`) — 10 registros

| clave | valor | categoría | descripción |
|---|---|---|---|
| `smlv` | 1423500 | laboral | Salario Mínimo Legal Vigente 2026 |
| `smlv_2025` | 1423500 | laboral | SMLV vigente 2025 |
| `subsidio_transporte` | 200000 | laboral | Auxilio de transporte 2026 |
| `subsidio_transporte_2025` | 200000 | laboral | Subsidio de transporte 2025 |
| `pct_salud_empleado` | 0.04 | laboral | Porcentaje deducción salud empleado (4%) |
| `pct_pension_empleado` | 0.04 | laboral | Porcentaje deducción pensión empleado (4%) |
| `porcentaje_prestaciones` | 21.83 | laboral | Porcentaje prestaciones sociales |
| `porcentaje_seguridad_social` | 8 | laboral | Porcentaje seguridad social empleado |
| `diferencial_genero_activo` | 1 | scoring | Diferencial de género activo (1=sí, 0=no) |
| `diferencial_genero_femenino` | 1.0 | scoring | Descuento tasa EA para género femenino (pp) |

**Schema de la tabla:**
```sql
CREATE TABLE parametros_sistema (
    clave TEXT PRIMARY KEY,
    valor TEXT,
    descripcion TEXT,
    categoria TEXT,
    tipo TEXT,
    ultima_actualizacion TEXT
)
```

**Ruta UI**: `GET /admin/parametros-sistema`  
**API**: `GET /admin/api/parametros-sistema` → `{success, parametros[]}`  
**API save**: `POST /admin/api/parametros-sistema` → body: `{parametros: [{clave, valor}]}`  
**Helper**: `db_helpers.obtener_parametros_sistema()` → lista de dicts

---

### 4.2 Líneas de Crédito (`lineas_credito`) — 9 líneas

| id | nombre | activa |
|---|---|---|
| — | Loansi Libranza | 1 |
| — | LoansiFlex | 1 |
| — | LoansiFlex Mini | 1 |
| — | LoansiMoto Avanzada | 1 |
| — | LoansiMoto Esencial | 1 |
| — | gravity test | 1 |
| — | gravity test 2 | 1 |
| — | gravity test 3 | 1 |
| — | gravity test 4 | 1 |

**Criterios por línea activa:**
- Loansi Libranza: 22 criterios (22 activos)
- LoansiFlex: 18 criterios (18 activos)
- LoansiFlex Mini: 28 criterios (28 activos)
- LoansiMoto Avanzada: 1 criterio
- LoansiMoto Esencial: 29 criterios (29 activos)

---

### 4.3 Proveedores IA (`ia_proveedores`) — 2 proveedores

| id | nombre | tipo | modelo | activo | prioridad |
|---|---|---|---|---|---|
| 1 | GLM 5 | openai_compatible | GLM-5 | 0 (inactivo) | 0 |
| 2 | Claude Haiku 4.5 | anthropic | claude-haiku-4-5-20251001 | 1 (activo) | 0 |

- `url_base` de GLM 5: `https://aiapi.world/v1`
- `url_base` de Claude: vacía (usa endpoint default de Anthropic)
- Las API keys están en la tabla pero no se documentan aquí por seguridad.

**Schema de la tabla:**
```sql
CREATE TABLE ia_proveedores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    proveedor_tipo TEXT NOT NULL DEFAULT 'anthropic',
    modelo TEXT NOT NULL DEFAULT 'claude-haiku-4-5-20251001',
    api_key TEXT DEFAULT '',
    url_base TEXT DEFAULT '',
    activo INTEGER DEFAULT 0,
    fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,
    prioridad INTEGER DEFAULT 0
)
```

**Ruta UI**: `GET /admin/integraciones`  
**API list**: `GET /admin/api/proveedores-ia`  
**API save**: `POST /admin/api/proveedores-ia`  
**API test**: `POST /admin/api/proveedores-ia/<id>/probar`

El `ExtractorService` lee los proveedores en `__init__` y hace **failover automático** en orden de prioridad.

---

## 5. Criterios de Evaluación — `criterios_scoring_master` (47 activos con extracción)

### Schema de la tabla:
```sql
-- Columnas actuales:
id, codigo, nombre, descripcion, tipo_campo, seccion_id, activo,
created_at, updated_at,
fuente_extraccion TEXT,       -- nueva
instruccion_extraccion TEXT,  -- nueva  
activo_extraccion INTEGER     -- nueva (1=activo, 0=inactivo)
```

### Tipos de campo:
- `number` / `numerico` → valor entero o decimal
- `currency` → valor monetario en COP (entero sin símbolos)
- `percentage` → porcentaje (0-100, decimal permitido)
- `select` → opciones fijas, IA devuelve valor canónico
- `composite` → combinación, IA devuelve valor canónico

### Fuentes de extracción disponibles:
| Código fuente | Descripción |
|---|---|
| `midecisor_pdf` | Reporte MiDecisor / DataCrédito en PDF |
| `cedula_imagen` | Foto/imagen de cédula colombiana |
| `certificado_laboral` | Certificado laboral empleador |
| `soporte_ingresos` | Soporte/comprobante de ingresos |
| `colilla_pago` | Colilla/desprendible de nómina |
| `extracto_bancario` | Extracto bancario (PDF posiblemente protegido) |
| `formulario_manual` | Ingreso manual por el asesor |
| `apitude_adres` | API Apitude → ADRES (régimen de salud) |
| `apitude_judicial` | API Apitude → Rama Judicial (TYBA) |
| `apitude_runt` | API Apitude → RUNT (vehículos/licencias) |
| `apitude_simit` | API Apitude → SIMIT (multas tránsito) |

### Formato de respuesta IA:
- **Numéricos**: solo el número, sin símbolos, sin separadores. Ej: `2500000` (no `$2.500.000`)
- **Selección/Composite**: valor canónico en UPPER_SNAKE_CASE. Ej: `EMPLEADO_INDEFINIDO`, `ALTA`, `SIN_MORAS`
- **Si no se encuentra**: exactamente `NO_ENCONTRADO`

---

### 5.1 Criterios con fuente `midecisor_pdf` (24 criterios)

| código | nombre | tipo_campo | instrucción — qué extraer |
|---|---|---|---|
| `puntaje_datacredito` | Puntaje DataCrédito | number | Score numérico 0-999. Sección "Score DataCrédito" primera página |
| `historial_pagos` | Comportamiento de Pago 12M | number | Contar meses con "N" (al día) en grilla de 12 meses |
| `creditos_cerrados_exitosos` | Créditos Cerrados (TOTAL) | number | Contar obligaciones con estado Terminado/Cerrado/Cancelado |
| `creditos_vigentes_activos` | Créditos Vigentes (TOTAL) | number | Suma de todas las obligaciones vigentes/activas |
| `consultas_recientes` | Consultas Últimos 60 días | number | Filtrar consultas en últimos 60 días y contar |
| `mora_reciente` | Mora Reciente (6 meses) | number | Máximo días en mora en últimos 6 meses |
| `endeudamiento_actual` | Saldo Actual | currency | Saldo total actual de obligaciones vigentes en COP |
| `saldo_vs_cupo` | % deuda (Saldo Total) | percentage | (Saldo Total / Cupo Total) × 100 |
| `proporcion_saldo_cupo` | TDC y Cartera Bancaria Rotativa | number | (Saldos TDC+rotativos / Cupos TDC+rotativos) × 100 |
| `cupo_total_aprobado` | Vlr o Cupo Inicial (Total) | currency | Suma cupos iniciales de todas las obligaciones (históricas) |
| `relacion_deuda` | Cuota Mensual vs. Ingreso Estimado (%) | percentage | (Cuota Mensual Total / Ingreso Estimado) × 100 |
| `ingresos_netos` | Valor Ingreso Estimado | currency | Ingreso mensual estimado en COP |
| `mora_sector_telcos` | Mora Sector Telcos (COP) | numerico | Saldo en mora del sector Telecomunicaciones en COP |
| `criterio_1770482163034` | Mora Sector Financiero | number | Saldo en mora del sector Financiero en COP |
| `criterio_1770482380808` | Mora Sectores Real + Cooperativo | number | Suma saldos mora Real + Cooperativo en COP |
| `criterio_1770482842402` | Consultas Recientes 60 Días (alerta) | composite | `SIN_ALERTA` o `ALERTA_ACTIVA` (≥3 entidades distintas en 60 días) |
| `criterio_1770482988658` | Viabilidad MiDecisor | composite | `ALTA`, `MEDIA` o `BAJA` |
| `comportamiento_sectorial` | Comportamiento Sectorial Mora | select | `SIN_MORAS`, `SOLO_TELCOS`, `SOLO_FINANCIERO`, `SOLO_REAL`, `SOLO_COOPERATIVO`, `MULTIPLES_SECTORES` |
| `criterio_1770494915836` | Moras ≥60 días, últimos 6 meses | number | Contar eventos de mora ≥60 días (códigos 3,4,5 en grilla) |
| `criterio_1770495240743` | 3+ nuevas direcciones en 12 meses | composite | `NO` o `SI` |
| `criterio_1770495908652` | Suplantación ID detectada | composite | `NO_DETECTADA` o `DETECTADA` |
| `criterio_1770496027200` | Listas restrictivas SARLAFT | composite | `SIN_COINCIDENCIAS` o `COINCIDENCIA_DETECTADA` |
| `criterio_1770496114423` | Cartera castigada activa | composite | `NO` o `SI` |

---

### 5.2 Criterios con fuente `formulario_manual` (10 criterios)

| código | nombre | tipo_campo | valores canónicos |
|---|---|---|---|
| `criterio_1753285008278` | Sector Económico | select | `INFORMACION_COMUNICACIONES`, `FINANCIERO_SEGUROS`, `INDUSTRIA`, `COMERCIO_RETAIL`, `CONSTRUCCION`, `SERVICIOS_PROFESIONALES`, `GOBIERNO_PUBLICO`, `TRANSPORTE_LOGISTICA`, `AGRICULTURA_PECUARIO`, `OTRO` |
| `criterio_1753285207809` | Destino del Crédito | select | `LIBRE_INVERSION`, `VEHICULO`, `MEJORAS_HOGAR`, `EDUCACION`, `CONSOLIDACION_DEUDAS`, `NEGOCIO_INVERSION`, `VIAJE_RECREACION`, `EMERGENCIA_SALUD`, `OTRO` |
| `criterio_1753285290128` | Tipo de Vivienda | select | `PROPIA_SIN_DEUDA`, `PROPIA_HIPOTECADA`, `ARRIENDO_FORMAL`, `FAMILIAR_ESTABLE`, `ARRIENDO_INFORMAL` |
| `criterio_1771111523949` | Tipo de Vivienda (FlexMini) | composite | mismos 5 valores |
| `criterio_1771336182663` | Tipo de Vivienda (Moto) | composite | mismos 5 valores |
| `verificacion_documental` | Verificación Documental | select | `EXCELENTE`, `BUENA`, `ACEPTABLE`, `MINIMA`, `DEFICIENTE` |
| `coherencia_ingreso_dane` | Coherencia Ingreso vs DANE | currency | `COHERENTE`, `LIGERAMENTE_SUPERIOR`, `LIGERAMENTE_INFERIOR`, `MUY_SUPERIOR`, `MUY_INFERIOR` |
| `criterio_1770764640224` | Medidas Correctivas RNMC (Policía) | composite | `NO_TIENE`, `TIENE_LEVES`, `TIENE_GRAVES`, `SIN_CONSULTA` |
| `criterio_1770764758593` | Procuraduría: Sanción Menor Activa | composite | `SIN_SANCIONES`, `SANCION_ACTIVA_MENOR`, `SANCION_ACTIVA_GRAVE`, `SIN_CONSULTA` |
| `criterio_1770764846265` | Contraloría: Hallazgo Fiscal | composite | `SIN_HALLAZGOS`, `HALLAZGO_NO_VIGENTE`, `HALLAZGO_VIGENTE`, `SIN_CONSULTA` |

---

### 5.3 Criterios con fuente `cedula_imagen` (3 criterios)

| código | nombre | tipo_campo | instrucción |
|---|---|---|---|
| `criterio_1753279578111` | Edad del Cliente | number | Calcular edad en años desde fecha nacimiento en cédula |
| `criterio_1771111580296` | Validación Documento Identidad | composite | `VIGENTE_OK`, `VIGENTE_DUDOSA`, `NO_VIGENTE`, `NO_LEGIBLE` |
| `criterio_1771336049875` | Validación Identidad: Estado Cédula | composite | `VIGENTE_OK`, `VIGENTE_DUDOSA`, `NO_VIGENTE`, `NO_LEGIBLE` |

---

### 5.4 Criterios con fuentes API Apitude (9 criterios)

| código | nombre | fuente | tipo_campo | valores/instrucción |
|---|---|---|---|---|
| `criterio_1770763566060` | Validación ADRES (régimen salud) | apitude_adres | composite | `CONTRIBUTIVO_COTIZANTE`, `CONTRIBUTIVO_BENEFICIARIO`, `SUBSIDIADO`, `NO_AFILIADO`, `DESCONOCIDO` |
| `criterio_1770764034375` | Procesos Ejecutivos Activos (TYBA) | apitude_judicial | composite | `NO_TIENE`, `TIENE_ACTIVOS`, `SIN_DATOS` |
| `criterio_1770764394797` | Embargos Judiciales Activos (TYBA) | apitude_judicial | composite | `NO_TIENE`, `TIENE_ACTIVOS`, `SIN_DATOS` |
| `criterio_1770764531834` | Cobro Coactivo SIMIT Activo | apitude_simit | composite | `NO_TIENE`, `TIENE_ACTIVO`, `SIN_DATOS` |
| `criterio_1770848283587` | Multas SIMIT Pendientes | apitude_simit | composite | `SIN_MULTAS`, `MULTAS_LEVES`, `MULTAS_MODERADAS`, `MULTAS_GRAVES` |
| `criterio_1771113165792` | Multas SIMIT Pendientes (valor) | apitude_simit | number | Valor total multas pendientes en COP, 0 si ninguna |
| `criterio_1770838350341` | Monto Sugerido vs. Valor Vehículo | apitude_runt | number | (Monto solicitado / Valor Fasecolda) × 100 |
| `criterio_1770838448463` | Valor Vehículo (COP) | number | Valor Fasecolda del vehículo en COP |
| `criterio_1771336901970` | Experiencia con Motos | apitude_runt | composite | `SIN_EXPERIENCIA`, `NOVATO`, `INTERMEDIO`, `EXPERIMENTADO`, `SIN_DATOS` |

---

### 5.5 Criterios con fuentes laborales (2 criterios)

| código | nombre | fuente | tipo_campo | instrucción |
|---|---|---|---|---|
| `criterio_1753284665359` | Tipo de Empleo | soporte_ingresos | composite | `EMPLEADO_INDEFINIDO`, `EMPLEADO_TERMINO_FIJO`, `CONTRATISTA_EMPRESA`, `INDEPENDIENTE_FORMAL`, `INDEPENDIENTE_INFORMAL`, `OCASIONAL` |
| `criterio_1753284395108` | Antigüedad Laboral (meses) | certificado_laboral | composite | Número de meses desde fecha ingreso hasta hoy |

---

### 5.6 Criterios SIN extracción configurada (5 criterios — placeholders de prueba)

| código | nombre | tipo_campo |
|---|---|---|
| `criterio_1769115669009` | Nuevo Criterio 22 | numerico |
| `criterio_1770236073581` | test Nuevo Criterio compuesto | composite |
| `criterio_1770240321710` | Nuevo Criterio test | number |
| `criterio_1770421846004` | Nuevo Criterio penalizacion | number |
| `criterio_1770483509306` | mietras llego para guardar | number |

> Estos criterios parecen ser de prueba. Si no están siendo usados en ninguna línea de crédito, se recomienda eliminarlos.

---

## 6. Factores de Rechazo/Penalización — `factores_rechazo_linea` (84 factores)

### Schema de la tabla:
```sql
CREATE TABLE factores_rechazo_linea (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    linea_credito_id INTEGER NOT NULL,
    criterio_codigo TEXT NOT NULL,
    criterio_nombre TEXT NOT NULL,
    operador TEXT NOT NULL,         -- '<', '>', '=', '!='
    valor_umbral REAL NOT NULL,
    mensaje_rechazo TEXT,
    activo INTEGER DEFAULT 1,
    orden INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tipo_factor TEXT DEFAULT 'numerico',   -- 'numerico' o 'seleccion'
    opciones_json TEXT DEFAULT NULL        -- para tipo seleccion
)
```

### Factores por línea:

#### Loansi Libranza (7 factores)
| criterio_codigo | operador | umbral | descripción |
|---|---|---|---|
| `dti` | > | 60.0 | DTI superior al 60% |
| `edad_maxima` | > | 70.0 | Edad máxima 70 años |
| `edad_minima` | < | 18.0 | Edad mínima 18 años |
| `mora_activa_financiero` | > | 60.0 | Mora activa financiera >60 días |
| `mora_telcos` | > | 200000.0 | Mora en telcos superior a $200,000 |
| `mora_telcos_dias` | > | 90.0 | Mora en telcos >90 días |
| `score_datacredito` | < | 350.0 | Score DataCrédito inferior a 350 |

#### LoansiFlex (11 factores)
| criterio_codigo | operador | umbral | descripción |
|---|---|---|---|
| `1` | < | 350.0 | Score DataCrédito inferior a 350 |
| `12` | > | 0.0 | Moras ≥60 días |
| `16` | > | 0.0 | Cartera castigada activa |
| `3` | < | 1750905.0 | Ingreso inferior a 1 SMLV |
| `4` | > | 50.0 | Cuota/Ingreso excesiva >50% |
| `7` | > | 0.0 | Mora Sector Financiero >0 |
| `9` | > | 100.0 | Sobre-endeudamiento total |
| `edad_maxima` | > | 65.0 | Edad máxima 65 años |
| `edad_minima` | < | 21.0 | Edad mínima 21 años |
| `verificacion_sarlaft` | = | 1.0 | Verificación SARLAFT |
| `vigencia_id` | = | 2.0 | Vigencia ID — selección |

#### LoansiFlex Mini (13 factores)
| criterio_codigo | tipo | umbral/opciones | descripción |
|---|---|---|---|
| `1` | numerico/= | -10.0 | Consultas Recientes 60 Días alerta |
| `11` | numerico/> | 100.0 | % deuda total >100% |
| `2` | numerico/< | 350.0 | Puntaje DataCrédito <350 |
| `4` | numerico/< | 1750905.0 | Ingreso < SMLV |
| `5` | numerico/> | 50.0 | Cuota/Ingreso >50% |
| `8` | numerico/> | 0.0 | Mora Sector Financiero >0 |
| `cartera_castigada_activa` | seleccion/= | — | Crédito castigado detectado (-15 pts) |
| `contraloria_hallazgo_fiscal_no_vigente` | seleccion/= | — | Hallazgo fiscal histórico (-5 pts) |
| `edad_maxima` | numerico/> | 65.0 | Edad máxima 65 años |
| `edad_minima` | numerico/< | 21.0 | Edad mínima 21 años |
| `listas_restrictivas_sarlaft` | seleccion/= | — | En listas restrictivas — RECHAZO (-50 pts) |
| `procuraduria_sancion_menor_activa_multa_suspension` | seleccion/= | — | Sanción menor activa (-10 pts) |
| `validacion_documento_identidad_estado` | seleccion/= | — | Documento no vigente (-50 pts) |

#### LoansiMoto Avanzada (7 factores)
| criterio_codigo | operador | umbral | descripción |
|---|---|---|---|
| `consultas_3meses` | > | 8.0 | Exceso consultas >8 en 3 meses |
| `dti` | > | 50.0 | DTI >50% |
| `edad` | < | 18.0 | Edad mínima 18 años |
| `edad` | > | 65.0 | Edad máxima 65 años |
| `mora_sector_financiero` | > | 30.0 | Mora activa financiero |
| `mora_sector_telcos` | > | 200000.0 | Mora telcos >$200.000 |
| `score_datacredito` | < | 400.0 | Score <400 |

#### LoansiMoto Esencial (13 factores)
| criterio_codigo | tipo | umbral | descripción |
|---|---|---|---|
| `3` | numerico/= | -10.0 | Viabilidad MiDecisor |
| `4` | numerico/< | 1750905.0 | Ingreso < SMLV |
| `criterio_1770482163034` | numerico/> | 0.0 | Mora Sector Financiero >0 |
| `criterio_1770482842402` | seleccion/= | — | Consultas alerta 60 días (-10 pts) |
| `criterio_1770496027200` | seleccion/= | 1.0 | Listas SARLAFT — RECHAZO (-50 pts) |
| `criterio_1770496114423` | seleccion/= | — | Cartera castigada (-15 pts) |
| `criterio_1770764531834` | seleccion/= | — | Cobro coactivo SIMIT (-20 pts) |
| `criterio_1770764846265` | seleccion/= | — | Hallazgo fiscal (-5 pts) |
| `criterio_1771336049875` | seleccion/> | 0.0 | Validación Cédula — No vigente (-50 pts) |
| `edad_maxima` | numerico/> | 65.0 | Edad máxima 65 años |
| `edad_minima` | numerico/< | 21.0 | Edad mínima 21 años |
| `puntaje_datacredito` | numerico/< | 400.0 | Score <400 |
| `relacion_deuda` | numerico/> | 50.0 | Cuota/Ingreso >50% |
| `saldo_vs_cupo` | numerico/> | 90.0 | % deuda >90% |

#### gravity test / gravity test 2-4 (8 factores cada uno — iguales)
| criterio_codigo | operador | umbral | descripción |
|---|---|---|---|
| `consultas_3meses` | > | 8.0 | Exceso consultas |
| `dti` | > | 50.0 | DTI >50% |
| `edad` | < | 18.0 | Edad mínima |
| `edad` | > | 65.0 | Edad máxima |
| `mora_sector_financiero` | > | 30.0 | Mora activa financiero |
| `mora_telcos` | > | 200000.0 | Mora telcos |
| `mora_telcos_dias` | > | 90.0 | Mora telcos días |
| `score_datacredito` | < | 400.0 | Score mínimo |

> **Nota sobre códigos legacy**: Factores con `criterio_codigo` numérico (1, 2, 3...) o alias cortos (`edad`, `dti`, `score_datacredito`) son configuraciones anteriores a la estandarización de códigos. El sistema los procesa igual.

---

## 7. Servicio de Extracción IA — `extractor_service.py`

### Clase principal: `ExtractorService`

**Métodos clave:**

| método | descripción |
|---|---|
| `__init__()` | Lee proveedores activos de `ia_proveedores`, configura failover |
| `obtener_criterios_activos(fuente, linea_id)` | Lista criterios con `activo_extraccion=1` para una fuente. Para select/composite enriquece con opciones del rango |
| `desbloquear_pdf(pdf_bytes, cedula)` | Intenta abrir PDF protegido con contraseñas de bancos colombianos |
| `construir_prompt(criterios, fuente)` | Genera prompt completo para la IA con todos los criterios a extraer |
| `extraer_desde_documento(archivo_bytes, fuente, cedula, mime_type, ingreso_declarado, linea_id)` | Extracción principal: desbloquea PDF → llama IA → parsea JSON |
| `extraer_multiples(archivos_dict, cedula, ingreso_declarado, linea_id)` | Procesa múltiples documentos y combina resultados |
| `extraer_datos_cedula(imagen_bytes, mime_type, lado)` | Extrae datos personales de imagen de cédula (nombre, documento, fecha nacimiento) |
| `_llamar_ia(...)` | Orquesta llamada con failover automático entre proveedores |
| `_llamar_anthropic(...)` | Llamada a API Anthropic Claude |
| `_llamar_openai_compatible(...)` | Llamada a API compatible OpenAI (GLM, Gemini, etc.) |
| `_parsear_json_respuesta(texto)` | Parsea respuesta IA, limpia markdown, repara JSON truncado |

### Flujo de extracción:
```
PDF/imagen subido
    → desbloquear_pdf() si PDF protegido (pikepdf)
    → construir_prompt() con criterios activos para esa fuente
    → _llamar_ia() con failover
        → proveedor 1 (activo)
        → proveedor 2 si falla (failover)
    → _parsear_json_respuesta()
    → mapeado a campos del formulario de scoring
```

### Archivos relacionados:
- `app/config_extraccion.py` — configuración de fuentes, tipos MIME permitidos, max_tokens por tipo
- `app/routes/extraccion_routes.py` — endpoints HTTP para subida y procesamiento
- `migrations/update_instrucciones_extracto_bancario.py` — ⚠️ instrucciones especializadas para extractos bancarios (Bancolombia, Nequi, MOVII, Nu, Falabella)
- `migrations/simplificar_instrucciones_extraccion.py` — versión simplificada de instrucciones
- `migrations/update_alertas_extracto_rangos.py` — rangos de alertas para extractos

---

## 8. Sistema de Scoring — `scoring_service.py`

### Parámetros laborales en `app/config.py`:
```python
PARAMETROS_LABORALES = {
    "anio": 2026,
    "smlv": 1_423_500,
    "subsidio_transporte": 200_000,
    "pct_salud_empleado": 0.04,
    "pct_pension_empleado": 0.04,
    "pct_fsp_4_smlv": 0.01,
    "pct_retencion_umbral": 5_470_000,
}
```
> Estos están tanto en `config.py` como en la tabla `parametros_sistema`. La tabla es la fuente de verdad en runtime; `config.py` son los valores por defecto de respaldo.

### Escala dual:
- Puntaje base: 0-45 puntos
- Puntaje normalizado: 0-100 puntos
- Umbrales de aprobación deben ser consistentes entre `scoring_service.py`, `criterios_sistema.py` y `scoring_routes.py`

---

## 9. Configuración técnica — `configuracion_sistema` (21 registros)

Tabla de clave-valor para configuración global. Claves relevantes de IA:

| clave | valor actual |
|---|---|
| `ia_activo` | "0" (desactivado globalmente) |
| `ia_api_key` | "" (vacía — se usa `ia_proveedores` en su lugar) |
| `ia_modelo` | "claude-haiku-4-5-20251001" |
| `ia_proveedor` | "anthropic" |
| `ia_url_base` | "https://api.anthropic.com" |

> El sistema migró de `configuracion_sistema` (clave única global) a `ia_proveedores` (múltiples proveedores con failover). La tabla `configuracion_sistema` conserva los valores por compatibilidad hacia atrás.

---

## 10. Reglas de Degradación (`reglas_degradacion`) — 10 reglas activas

Estas reglas ajustan automáticamente la tasa de interés según criterios específicos (ej: mora en telcos eleva la tasa).

```sql
CREATE TABLE reglas_degradacion (
    id, nombre, descripcion, criterio_codigo,
    condicion_tipo, condicion_valor,
    impacto_tasa_ea, activo, created_at
)
```

---

## 11. Migraciones disponibles

Todos los scripts están en `migrations/`. Se ejecutan manualmente con `python migrations/nombre.py`.

| archivo | propósito |
|---|---|
| `add_ia_proveedores.py` | Crea tabla `ia_proveedores` y migra datos desde `configuracion_sistema` |
| `add_ia_config.py` | Inserta valores iniciales IA en `configuracion_sistema` |
| `add_parametros_sistema.py` | Crea tabla `parametros_sistema` con valores SMLV 2025 |
| `add_extraccion_fields.py` | Agrega `fuente_extraccion`, `instruccion_extraccion`, `activo_extraccion` a `criterios_scoring_master` |
| `add_interpolation_fields.py` | Agrega campos de interpolación a `niveles_riesgo_linea` + crea `reglas_degradacion` y `escalas_score_linea` |
| `add_prioridad_proveedores.py` | Agrega columna `prioridad` a `ia_proveedores` |
| `add_diferencial_genero.py` | Agrega parámetros de diferencial de género |
| `update_instrucciones_extracto_bancario.py` | ⚠️ Instrucciones IA especializadas para extractos de Bancolombia, Nequi, MOVII, Nu, Banco Falabella |
| `simplificar_instrucciones_extraccion.py` | Versión alternativa simplificada de instrucciones |
| `update_alertas_extracto_rangos.py` | Rangos y alertas para análisis de extractos |

> **IMPORTANTE para recuperación**: El archivo `update_instrucciones_extracto_bancario.py` puede contener configuraciones de extracto bancario que el usuario tenía previamente y que no están en `criterios_scoring_master` sino en una lógica separada. Revisar ese archivo con prioridad.

---

## 12. Lo que aún podría estar pendiente de recuperar

Con base en el historial de pérdidas y lo restaurado:

1. **Configuración específica de extractos bancarios**: El archivo `update_instrucciones_extracto_bancario.py` (17KB) sugiere que había instrucciones muy detalladas por banco (Bancolombia, Nequi, MOVII, Nu, Falabella). Revisar si esas instrucciones están aplicadas en la DB actual o solo en el script.

2. **Instrucciones de extracción originales**: Las instrucciones actuales en `criterios_scoring_master.instruccion_extraccion` fueron regeneradas automáticamente (no son las originales del usuario). El usuario puede querer afinarlas.

3. **Niveles de riesgo con interpolación**: La tabla `niveles_riesgo_linea` tiene columnas de interpolación (`tasa_ea_at_min`, `tasa_ea_at_max`, `aval_at_min`, `aval_at_max`, `interpolacion_activa`). Verificar si los valores están configurados o en blanco.

4. **Escalas de score por línea** (`escalas_score_linea`): Actualmente **0 registros**. Puede que estuviera configurado antes.

5. **Proveedores IA adicionales**: El usuario pudo haber tenido más de 2 proveedores configurados (GLM y Claude). La tabla ahora tiene solo 2.

6. **Configuración comité de crédito** (`comite_config`, `comite_alertas_config`): Actualmente 9 y 3 registros respectivamente. No se ha verificado si está completa.

---

## 13. Comandos útiles para diagnóstico

```bash
# Ver estado de la DB
python -c "import sqlite3; c=sqlite3.connect('loansi.db'); cur=c.cursor(); cur.execute(\"SELECT name FROM sqlite_master WHERE type='table'\"); [print(r[0]) for r in cur.fetchall()]"

# Ver criterios con extracción configurada
python -c "import sqlite3; c=sqlite3.connect('loansi.db'); c.row_factory=sqlite3.Row; cur=c.cursor(); cur.execute('SELECT codigo, nombre, fuente_extraccion, activo_extraccion FROM criterios_scoring_master WHERE activo_extraccion=1 ORDER BY fuente_extraccion'); [print(dict(r)) for r in cur.fetchall()]"

# Ver proveedores IA
python -c "import sqlite3; c=sqlite3.connect('loansi.db'); c.row_factory=sqlite3.Row; cur=c.cursor(); cur.execute('SELECT id, nombre, proveedor_tipo, modelo, activo, prioridad FROM ia_proveedores'); [print(dict(r)) for r in cur.fetchall()]"

# Ver parámetros sistema
python -c "import sqlite3; c=sqlite3.connect('loansi.db'); c.row_factory=sqlite3.Row; cur=c.cursor(); cur.execute('SELECT * FROM parametros_sistema ORDER BY categoria, clave'); [print(dict(r)) for r in cur.fetchall()]"

# Arrancar servidor desarrollo
python run.py
# URL: http://127.0.0.1:5000

# Hacer backup de la DB antes de cambios
copy loansi.db loansi_backup_FECHA.db
```

---

## 14. Reglas del proyecto (para la IA que continúe)

- **NO hay SQLAlchemy**. Todo acceso a DB usa `sqlite3` puro con `conectar_db()` de `database.py`.
- **NO hay ORM**: `db.Model`, `db.session`, `db.Column` — NO EXISTEN en este proyecto.
- Los `db_helpers*.py` están en la **RAÍZ** del proyecto, no en `app/`.
- `app/models/__init__.py` es una **fachada** que solo re-exporta funciones de `db_helpers`.
- Responder **siempre en español** al usuario.
- Patrón de imports en routes:
  ```python
  import sys
  from pathlib import Path
  BASE_DIR = Path(__file__).parent.parent.parent.resolve()
  if str(BASE_DIR) not in sys.path:
      sys.path.insert(0, str(BASE_DIR))
  from db_helpers import funcion_necesaria
  ```
- Decoradores de permisos: `@requiere_permiso("nombre_permiso")` de `permisos.py`
- Flash messages: categorías `success`, `danger`, `warning`, `info`
- Bootstrap 5.3.2 únicamente (no mezclar versiones)
- Texto de UI siempre en **español colombiano**
