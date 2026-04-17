"""
Migración: Agregar parámetros de diferencial de género en tasa de interés.
Política de inclusión financiera - descuento en tasa EA para género femenino.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'loansi.db')

def migrar():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Insertar parámetro: activar/desactivar diferencial de género
        cursor.execute("""
            INSERT OR IGNORE INTO parametros_sistema (clave, valor, descripcion)
            VALUES ('diferencial_genero_activo', '1', 
                    'Activar diferencial de tasa por género (1=activo, 0=inactivo)')
        """)
        
        # Insertar parámetro: puntos de descuento para género femenino
        cursor.execute("""
            INSERT OR IGNORE INTO parametros_sistema (clave, valor, descripcion)
            VALUES ('diferencial_genero_femenino', '1.0', 
                    'Descuento en puntos porcentuales de tasa EA para género F (mujeres)')
        """)
        
        # Agregar columna genero a evaluaciones si no existe
        cursor.execute("PRAGMA table_info(evaluaciones)")
        columnas = [col[1] for col in cursor.fetchall()]
        if 'genero' not in columnas:
            cursor.execute("ALTER TABLE evaluaciones ADD COLUMN genero TEXT")
            print("  Columna 'genero' agregada a evaluaciones")
        
        conn.commit()
        print("Migración diferencial de género completada exitosamente")
        
        # Verificar
        cursor.execute("SELECT clave, valor, descripcion FROM parametros_sistema WHERE clave LIKE 'diferencial_genero%'")
        for row in cursor.fetchall():
            print(f"  {row[0]} = {row[1]} ({row[2]})")
        
    except Exception as e:
        conn.rollback()
        print(f"Error en migración: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    migrar()
