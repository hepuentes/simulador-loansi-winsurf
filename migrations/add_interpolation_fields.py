"""
Migración: Agregar campos de interpolación a niveles_riesgo_linea

Nuevos campos:
- tasa_ea_at_min: Tasa E.A. cuando score = score_min (la peor del nivel)
- tasa_ea_at_max: Tasa E.A. cuando score = score_max (la mejor del nivel)  
- aval_at_min: Aval cuando score = score_min
- aval_at_max: Aval cuando score = score_max
- interpolacion_activa: Si se usa interpolación o valor fijo

También crea tabla de reglas de degradación por moras telcos.
"""

import sqlite3
import os
import sys

# Agregar directorio raíz al path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

DB_PATH = os.path.join(BASE_DIR, "loansi.db")


def migrar():
    """Ejecuta la migración para agregar campos de interpolación."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        print("🔄 Iniciando migración de interpolación...")
        
        # 1. Agregar campos de interpolación a niveles_riesgo_linea
        campos_nuevos = [
            ("tasa_ea_at_min", "REAL", None),      # Tasa en score_min
            ("tasa_ea_at_max", "REAL", None),      # Tasa en score_max
            ("aval_at_min", "REAL", None),         # Aval en score_min
            ("aval_at_max", "REAL", None),         # Aval en score_max
            ("interpolacion_activa", "INTEGER", "1"),  # 1=interpolación, 0=valor fijo
        ]
        
        # Verificar qué campos ya existen
        cursor.execute("PRAGMA table_info(niveles_riesgo_linea)")
        columnas_existentes = {col[1] for col in cursor.fetchall()}
        
        for campo, tipo, default in campos_nuevos:
            if campo not in columnas_existentes:
                default_str = f"DEFAULT {default}" if default else ""
                cursor.execute(f"""
                    ALTER TABLE niveles_riesgo_linea 
                    ADD COLUMN {campo} {tipo} {default_str}
                """)
                print(f"  ✅ Campo '{campo}' agregado")
            else:
                print(f"  ⏭️ Campo '{campo}' ya existe")
        
        # 2. Migrar datos existentes: copiar tasa_ea y aval_porcentaje a los nuevos campos
        cursor.execute("""
            UPDATE niveles_riesgo_linea 
            SET tasa_ea_at_min = tasa_ea,
                tasa_ea_at_max = tasa_ea,
                aval_at_min = aval_porcentaje,
                aval_at_max = aval_porcentaje,
                interpolacion_activa = 0
            WHERE tasa_ea_at_min IS NULL
        """)
        filas_actualizadas = cursor.rowcount
        print(f"  ✅ {filas_actualizadas} niveles migrados con valores actuales")
        
        # 3. Crear tabla de reglas de degradación
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reglas_degradacion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                linea_credito_id INTEGER,
                tipo_regla TEXT NOT NULL,           -- 'mora_telcos', 'consultas', 'mora_pagada', etc.
                descripcion TEXT,
                umbral_min REAL,                    -- Valor mínimo del rango
                umbral_max REAL,                    -- Valor máximo del rango (NULL = sin límite)
                accion TEXT NOT NULL,               -- 'penalizar_puntos', 'degradar_nivel', 'evaluar_manual'
                valor_accion REAL,                  -- Puntos a restar o niveles a degradar
                orden INTEGER DEFAULT 0,
                activo INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (linea_credito_id) REFERENCES lineas_credito(id)
            )
        """)
        print("  ✅ Tabla 'reglas_degradacion' creada/verificada")
        
        # 4. Insertar reglas de degradación por defecto para moras telcos
        cursor.execute("SELECT COUNT(*) FROM reglas_degradacion WHERE tipo_regla = 'mora_telcos'")
        if cursor.fetchone()[0] == 0:
            reglas_telcos = [
                # (tipo, descripcion, min, max, accion, valor, orden)
                ('mora_telcos', 'Sin impacto - monto menor', 0, 100000, 'sin_impacto', 0, 1),
                ('mora_telcos', 'Penalización leve', 100001, 200000, 'penalizar_puntos', 5, 2),
                ('mora_telcos', 'Degradar 1 nivel', 200001, 500000, 'degradar_nivel', 1, 3),
                ('mora_telcos', 'Degradar 2 niveles o evaluar', 500001, 1000000, 'degradar_nivel', 2, 4),
                ('mora_telcos', 'Tratamiento como mora financiera', 1000001, None, 'mora_financiera', 0, 5),
            ]
            
            for tipo, desc, min_val, max_val, accion, valor, orden in reglas_telcos:
                cursor.execute("""
                    INSERT INTO reglas_degradacion 
                    (linea_credito_id, tipo_regla, descripcion, umbral_min, umbral_max, 
                     accion, valor_accion, orden, activo)
                    VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (tipo, desc, min_val, max_val, accion, valor, orden))
            
            print("  ✅ Reglas de degradación por moras telcos insertadas")
        
        # 5. Insertar otras reglas de degradación
        cursor.execute("SELECT COUNT(*) FROM reglas_degradacion WHERE tipo_regla = 'consultas_excesivas'")
        if cursor.fetchone()[0] == 0:
            otras_reglas = [
                ('consultas_excesivas', 'Más de 5 consultas en 30 días', 5, None, 'penalizar_puntos', 5, 1),
                ('mora_pagada_reciente', 'Mora pagada hace menos de 6 meses', 0, 6, 'degradar_nivel', 1, 1),
                ('sin_historial', 'Primera vez sin historial crediticio', None, None, 'degradar_nivel', 1, 1),
                ('multiples_empleadores', 'Más de 3 empleadores en último año', 3, None, 'penalizar_puntos', 10, 1),
                ('direccion_inestable', 'Más de 2 cambios de dirección en 12 meses', 2, None, 'penalizar_puntos', 5, 1),
            ]
            
            for tipo, desc, min_val, max_val, accion, valor, orden in otras_reglas:
                cursor.execute("""
                    INSERT INTO reglas_degradacion 
                    (linea_credito_id, tipo_regla, descripcion, umbral_min, umbral_max, 
                     accion, valor_accion, orden, activo)
                    VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (tipo, desc, min_val, max_val, accion, valor, orden))
            
            print("  ✅ Otras reglas de degradación insertadas")
        
        # 6. Crear tabla de configuración de escalas por línea
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS escalas_score_linea (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                linea_credito_id INTEGER NOT NULL,
                nivel_nombre TEXT NOT NULL,         -- 'rechazo', 'alto', 'medio', 'moderado', 'bajo'
                score_min REAL NOT NULL,
                score_max REAL NOT NULL,
                orden INTEGER DEFAULT 0,
                activo INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (linea_credito_id) REFERENCES lineas_credito(id),
                UNIQUE(linea_credito_id, nivel_nombre)
            )
        """)
        print("  ✅ Tabla 'escalas_score_linea' creada/verificada")
        
        conn.commit()
        print("\n✅ Migración completada exitosamente")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error en migración: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


def verificar_migracion():
    """Verifica que la migración se aplicó correctamente."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Verificar campos en niveles_riesgo_linea
        cursor.execute("PRAGMA table_info(niveles_riesgo_linea)")
        columnas = {col[1] for col in cursor.fetchall()}
        
        campos_requeridos = {'tasa_ea_at_min', 'tasa_ea_at_max', 'aval_at_min', 'aval_at_max', 'interpolacion_activa'}
        faltan = campos_requeridos - columnas
        
        if faltan:
            print(f"❌ Faltan campos: {faltan}")
            return False
        
        # Verificar tablas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('reglas_degradacion', 'escalas_score_linea')")
        tablas = {row[0] for row in cursor.fetchall()}
        
        if 'reglas_degradacion' not in tablas:
            print("❌ Falta tabla 'reglas_degradacion'")
            return False
            
        print("✅ Migración verificada correctamente")
        return True
        
    finally:
        conn.close()


if __name__ == "__main__":
    migrar()
    verificar_migracion()
