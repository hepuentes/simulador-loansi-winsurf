"""
DATABASE.PY - Sistema de Base de Datos SQLite para Loansi
==========================================================
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
import shutil

# Ruta de la base de datos
DB_PATH = Path(__file__).parent / 'loansi.db'
BACKUP_DIR = Path(__file__).parent / 'backups'


# ============================================================================
# ESQUEMA SQL COMPLETO
# ============================================================================

SCHEMA_SQL = """
-- ============================================================================
-- TABLA: usuarios
-- Reemplaza: config.json["USUARIOS"]
-- ============================================================================
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    rol TEXT NOT NULL DEFAULT 'asesor',
    activo BOOLEAN DEFAULT 1,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CHECK (rol IN ('asesor', 'supervisor', 'auditor', 'gerente', 'admin_tecnico', 'comite_credito', 'admin'))
);

-- Índices para usuarios
CREATE INDEX IF NOT EXISTS idx_usuarios_username ON usuarios(username);
CREATE INDEX IF NOT EXISTS idx_usuarios_rol ON usuarios(rol);
CREATE INDEX IF NOT EXISTS idx_usuarios_activo ON usuarios(activo);


-- ============================================================================
-- TABLA: lineas_credito
-- Reemplaza: config.json["LINEAS_CREDITO"]
-- ============================================================================
CREATE TABLE IF NOT EXISTS lineas_credito (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT UNIQUE NOT NULL,
    descripcion TEXT,
    monto_min INTEGER NOT NULL,
    monto_max INTEGER NOT NULL,
    plazo_min INTEGER NOT NULL,
    plazo_max INTEGER NOT NULL,
    tasa_mensual REAL NOT NULL,
    tasa_anual REAL NOT NULL,
    aval_porcentaje REAL DEFAULT 0.0,
    plazo_tipo TEXT DEFAULT 'meses',
    permite_desembolso_neto BOOLEAN DEFAULT 1,
    desembolso_por_defecto TEXT DEFAULT 'completo',
    activo BOOLEAN DEFAULT 1,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CHECK (monto_min > 0),
    CHECK (monto_max >= monto_min),
    CHECK (plazo_min > 0),
    CHECK (plazo_max >= plazo_min),
    CHECK (tasa_mensual > 0),
    CHECK (tasa_anual > 0),
    CHECK (aval_porcentaje >= 0 AND aval_porcentaje <= 1),
    CHECK (plazo_tipo IN ('meses', 'semanas', 'dias')),
    CHECK (desembolso_por_defecto IN ('completo', 'neto'))
);

-- Índices para líneas de crédito
CREATE INDEX IF NOT EXISTS idx_lineas_nombre ON lineas_credito(nombre);
CREATE INDEX IF NOT EXISTS idx_lineas_activo ON lineas_credito(activo);


-- ============================================================================
-- TABLA: costos_asociados
-- Reemplaza: config.json["COSTOS_ASOCIADOS"]
-- ============================================================================
CREATE TABLE IF NOT EXISTS costos_asociados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    linea_credito_id INTEGER NOT NULL,
    nombre_costo TEXT NOT NULL,
    valor REAL NOT NULL,
    activo BOOLEAN DEFAULT 1,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Key
    FOREIGN KEY (linea_credito_id) REFERENCES lineas_credito(id) ON DELETE CASCADE,

    -- Constraints
    CHECK (valor >= 0),

    -- Unique constraint
    UNIQUE(linea_credito_id, nombre_costo)
);

-- Índices para costos asociados
CREATE INDEX IF NOT EXISTS idx_costos_linea ON costos_asociados(linea_credito_id);


-- ============================================================================
-- TABLA: configuracion_sistema
-- Reemplaza: config.json["PARAMETROS_CAPACIDAD_PAGO"] y config.json["COMITE_CREDITO"]
-- ============================================================================
CREATE TABLE IF NOT EXISTS configuracion_sistema (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clave TEXT UNIQUE NOT NULL,
    valor TEXT NOT NULL,  -- JSON serializado
    descripcion TEXT,
    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modificado_por TEXT
);

-- Índices para configuración
CREATE INDEX IF NOT EXISTS idx_config_clave ON configuracion_sistema(clave);


-- ============================================================================
-- TABLA: configuracion_scoring
-- Reemplaza: scoring.json
-- ============================================================================
CREATE TABLE IF NOT EXISTS configuracion_scoring (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    linea_credito TEXT NOT NULL,
    configuracion TEXT NOT NULL,  -- JSON serializado completo
    version INTEGER DEFAULT 1,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modificado_por TEXT,

    -- Unique constraint
    UNIQUE(linea_credito, version)
);

-- Índices para scoring
CREATE INDEX IF NOT EXISTS idx_scoring_linea ON configuracion_scoring(linea_credito);


-- ============================================================================
-- TABLA: evaluaciones
-- Reemplaza: evaluaciones_log.json
-- ============================================================================
CREATE TABLE IF NOT EXISTS evaluaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT UNIQUE NOT NULL,
    asesor TEXT NOT NULL,
    nombre_cliente TEXT,
    cedula TEXT,
    tipo_credito TEXT,
    linea_credito TEXT,
    estado_desembolso TEXT,
    origen TEXT DEFAULT 'Automático',

    -- Scoring
    resultado TEXT NOT NULL,  -- JSON serializado: {score, score_normalizado, nivel, aprobado, rechazo_automatico}
    criterios_evaluados TEXT,  -- JSON serializado: array de criterios
    monto_solicitado INTEGER,

    -- Comité de crédito
    estado_comite TEXT,  -- NULL, 'pending', 'approved', 'rejected'
    decision_admin TEXT,  -- JSON serializado: {accion, admin, timestamp, comentario, monto_aprobado, nivel_riesgo_modificado, justificacion}
    visto_por_asesor BOOLEAN DEFAULT 0,
    fecha_visto_asesor TEXT,
    fecha_envio_comite TEXT,

    -- Campos adicionales
    puntaje_datacredito INTEGER,
    datacredito INTEGER,  -- Alias de puntaje_datacredito

    -- Timestamps
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Keys
    FOREIGN KEY (asesor) REFERENCES usuarios(username),

    -- Constraints
    CHECK (estado_comite IN (NULL, 'pending', 'approved', 'rejected')),
    CHECK (estado_desembolso IN ('Pendiente', 'Desembolsado', 'Rechazado'))
);

-- Índices para evaluaciones (CRÍTICOS para performance)
CREATE INDEX IF NOT EXISTS idx_evaluaciones_asesor ON evaluaciones(asesor);
CREATE INDEX IF NOT EXISTS idx_evaluaciones_timestamp ON evaluaciones(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_evaluaciones_estado_comite ON evaluaciones(estado_comite);
CREATE INDEX IF NOT EXISTS idx_evaluaciones_visto ON evaluaciones(visto_por_asesor);
CREATE INDEX IF NOT EXISTS idx_evaluaciones_cedula ON evaluaciones(cedula);
CREATE INDEX IF NOT EXISTS idx_evaluaciones_cliente ON evaluaciones(nombre_cliente);


-- ============================================================================
-- TABLA: simulaciones
-- Reemplaza: simulaciones_log.json
-- ============================================================================
CREATE TABLE IF NOT EXISTS simulaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    asesor TEXT NOT NULL,
    cliente TEXT,
    cedula TEXT,
    monto INTEGER NOT NULL,
    plazo INTEGER NOT NULL,
    linea_credito TEXT NOT NULL,
    tasa_ea REAL,
    tasa_mensual REAL,
    cuota_mensual INTEGER,
    nivel_riesgo TEXT,
    aval INTEGER DEFAULT 0,
    seguro INTEGER DEFAULT 0,
    plataforma INTEGER DEFAULT 0,
    total_financiar INTEGER,
    caso_origen TEXT,  -- timestamp de la evaluación origen
    modalidad_desembolso TEXT DEFAULT 'completo',

    -- Timestamps
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Keys
    FOREIGN KEY (asesor) REFERENCES usuarios(username),
    FOREIGN KEY (linea_credito) REFERENCES lineas_credito(nombre),

    -- Constraints
    CHECK (monto > 0),
    CHECK (plazo > 0),
    CHECK (modalidad_desembolso IN ('completo', 'neto'))
);

-- Índices para simulaciones
CREATE INDEX IF NOT EXISTS idx_simulaciones_asesor ON simulaciones(asesor);
CREATE INDEX IF NOT EXISTS idx_simulaciones_timestamp ON simulaciones(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_simulaciones_cedula ON simulaciones(cedula);
CREATE INDEX IF NOT EXISTS idx_simulaciones_caso_origen ON simulaciones(caso_origen);


-- ============================================================================
-- TABLA: auditoria
-- Nueva tabla para rastrear cambios importantes
-- ============================================================================
CREATE TABLE IF NOT EXISTS auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    usuario TEXT NOT NULL,
    accion TEXT NOT NULL,
    tabla_afectada TEXT,
    registro_id INTEGER,
    datos_anteriores TEXT,  -- JSON
    datos_nuevos TEXT,  -- JSON
    ip_address TEXT,

    -- Foreign Key
    FOREIGN KEY (usuario) REFERENCES usuarios(username)
);

-- Índices para auditoría
CREATE INDEX IF NOT EXISTS idx_auditoria_timestamp ON auditoria(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_auditoria_usuario ON auditoria(usuario);
CREATE INDEX IF NOT EXISTS idx_auditoria_tabla ON auditoria(tabla_afectada);


-- ============================================================================
-- TABLA: user_assignments
-- Asignaciones de usuarios a supervisores/auditores/gerentes
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    manager_username TEXT NOT NULL,
    member_username TEXT NOT NULL,
    activo BOOLEAN DEFAULT 1,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    UNIQUE(manager_username, member_username)
);

-- Índices para asignaciones
CREATE INDEX IF NOT EXISTS idx_assign_manager ON user_assignments(manager_username);
CREATE INDEX IF NOT EXISTS idx_assign_member ON user_assignments(member_username);
CREATE INDEX IF NOT EXISTS idx_assign_activo ON user_assignments(activo);


-- ============================================================================
-- VISTA: casos_comite (facilita queries)
-- ============================================================================
CREATE VIEW IF NOT EXISTS vista_casos_comite AS
SELECT
    e.id,
    e.timestamp,
    e.asesor,
    e.nombre_cliente,
    e.cedula,
    e.tipo_credito,
    e.monto_solicitado,
    json_extract(e.resultado, '$.score') as score,
    json_extract(e.resultado, '$.nivel') as nivel,
    e.estado_comite,
    e.visto_por_asesor,
    json_extract(e.decision_admin, '$.admin') as admin_decisor,
    json_extract(e.decision_admin, '$.timestamp') as fecha_decision,
    e.fecha_envio_comite
FROM evaluaciones e
WHERE e.estado_comite IS NOT NULL;


-- ============================================================================
-- VISTA: metricas_asesores (para dashboards)
-- ============================================================================
CREATE VIEW IF NOT EXISTS vista_metricas_asesores AS
SELECT
    e.asesor,
    COUNT(DISTINCT e.id) as total_evaluaciones,
    COUNT(DISTINCT CASE WHEN e.estado_comite = 'approved' THEN e.id END) as casos_aprobados,
    COUNT(DISTINCT CASE WHEN e.estado_comite = 'rejected' THEN e.id END) as casos_rechazados,
    COUNT(DISTINCT CASE WHEN e.estado_comite = 'pending' THEN e.id END) as casos_pendientes,
    AVG(CAST(json_extract(e.resultado, '$.score') AS REAL)) as score_promedio,
    COUNT(DISTINCT s.id) as total_simulaciones
FROM evaluaciones e
LEFT JOIN simulaciones s ON e.asesor = s.asesor
GROUP BY e.asesor;


-- ============================================================================
-- TABLA: parametros_sistema
-- Parametros globales del sistema (SMLV, subsidio transporte, porcentajes)
-- ============================================================================
CREATE TABLE IF NOT EXISTS parametros_sistema (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL,
    descripcion TEXT,
    ultima_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


# ============================================================================
# FUNCIONES HELPER
# ============================================================================

def crear_backup_json(ruta_json):
    """
    Crea backup de un archivo JSON antes de migrar.

    Args:
        ruta_json (Path): Ruta del archivo JSON a respaldar
    """
    if not ruta_json.exists():
        print(f"⚠️ Archivo no existe: {ruta_json}")
        return False

    # Crear directorio de backups si no existe
    BACKUP_DIR.mkdir(exist_ok=True)

    # Nombre del backup con timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_nombre = f"{ruta_json.stem}_backup_{timestamp}.json"
    backup_ruta = BACKUP_DIR / backup_nombre

    # Copiar archivo
    shutil.copy2(ruta_json, backup_ruta)
    print(f"✅ Backup creado: {backup_ruta}")
    return True


def conectar_db():
    """
    Conecta a la base de datos SQLite.

    Returns:
        sqlite3.Connection: Conexión a la DB
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Para acceder por nombre de columna

    # Habilitar foreign keys (deshabilitadas por defecto en SQLite)
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def crear_base_datos():
    """
    Crea la base de datos con el esquema completo.

    Returns:
        bool: True si se creó exitosamente
    """
    try:
        print("🔨 Creando base de datos SQLite...")

        conn = conectar_db()
        cursor = conn.cursor()

        # Ejecutar el esquema completo
        cursor.executescript(SCHEMA_SQL)

        conn.commit()
        conn.close()

        print(f"✅ Base de datos creada: {DB_PATH}")
        return True

    except Exception as e:
        print(f"❌ Error al crear base de datos: {e}")
        return False


def verificar_integridad_db():
    """
    Verifica la integridad de la base de datos.

    Returns:
        bool: True si la DB está OK
    """
    try:
        conn = conectar_db()
        cursor = conn.cursor()

        # Verificar integridad
        cursor.execute("PRAGMA integrity_check")
        resultado = cursor.fetchone()[0]

        conn.close()

        if resultado == "ok":
            print("✅ Integridad de DB verificada: OK")
            return True
        else:
            print(f"❌ Problema de integridad: {resultado}")
            return False

    except Exception as e:
        print(f"❌ Error al verificar integridad: {e}")
        return False


def listar_tablas():
    """
    Lista todas las tablas en la base de datos.

    Returns:
        list: Lista de nombres de tablas
    """
    try:
        conn = conectar_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            ORDER BY name
        """)

        tablas = [row[0] for row in cursor.fetchall()]
        conn.close()

        return tablas

    except Exception as e:
        print(f"❌ Error al listar tablas: {e}")
        return []


def contar_registros_tabla(tabla):
    """
    Cuenta registros en una tabla.

    Args:
        tabla (str): Nombre de la tabla

    Returns:
        int: Número de registros
    """
    # SEGURIDAD: Whitelist de tablas válidas para prevenir SQL injection
    TABLAS_VALIDAS = {
        'usuarios', 'lineas_credito', 'costos_asociados',
        'configuracion_sistema', 'configuracion_scoring',
        'evaluaciones', 'simulaciones', 'auditoria',
        'user_assignments', 'permisos', 'rol_permisos', 'usuario_permisos'
    }
    
    if tabla not in TABLAS_VALIDAS:
        print(f"❌ Tabla no válida: {tabla}")
        return 0
    
    try:
        conn = conectar_db()
        cursor = conn.cursor()

        cursor.execute(f"SELECT COUNT(*) FROM {tabla}")
        count = cursor.fetchone()[0]

        conn.close()
        return count

    except Exception as e:
        print(f"❌ Error al contar registros en {tabla}: {e}")
        return 0


# ============================================================================
# FUNCIÓN DE TESTING
# ============================================================================

def test_database():
    """
    Testing básico de la base de datos.
    """
    print("\n" + "="*70)
    print("TESTING DE BASE DE DATOS")
    print("="*70 + "\n")

    # 1. Crear base de datos
    if not crear_base_datos():
        print("❌ FALLO: No se pudo crear la base de datos")
        return False

    # 2. Verificar integridad
    if not verificar_integridad_db():
        print("❌ FALLO: Problema de integridad")
        return False

    # 3. Listar tablas
    tablas = listar_tablas()
    print(f"\n📊 Tablas creadas ({len(tablas)}):")
    for tabla in tablas:
        print(f"   ✓ {tabla}")

    # 4. Verificar tablas esperadas
    tablas_esperadas = [
        'usuarios', 'lineas_credito', 'costos_asociados',
        'configuracion_sistema', 'configuracion_scoring',
        'evaluaciones', 'simulaciones', 'auditoria'
    ]

    tablas_faltantes = set(tablas_esperadas) - set(tablas)
    if tablas_faltantes:
        print(f"\n⚠️ ADVERTENCIA: Tablas faltantes: {tablas_faltantes}")
    else:
        print("\n✅ Todas las tablas fueron creadas correctamente")

    print("\n" + "="*70)
    print("✅ TESTING COMPLETADO")
    print("="*70 + "\n")

    return True


# ============================================================================
# MAIN (Para testing standalone)
# ============================================================================

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                  SISTEMA DE BASE DE DATOS - LOANSI               ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    test_database()
