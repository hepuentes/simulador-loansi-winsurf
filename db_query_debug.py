"""
MIGRACION: Corregir criterio_codigo en factores_rechazo_linea
==============================================================
Los factores de rechazo usan codigos antiguos (IDs numericos o nombres
descriptivos) que NO coinciden con los codigos reales del formulario.
Este script corrige el mapeo para TODAS las lineas de credito.
"""
import sqlite3
import json

conn = sqlite3.connect('loansi.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# 1. Construir mapeo: nombre_criterio -> codigo_real (del master)
c.execute("SELECT id, codigo, nombre FROM criterios_scoring_master")
master_rows = c.fetchall()

id_to_codigo = {}
nombre_to_codigo = {}
for m in master_rows:
    id_to_codigo[str(m['id'])] = m['codigo']
    nombre_to_codigo[m['nombre'].lower().strip()] = m['codigo']

# Mapeo manual para casos especiales
MAPEO_ESPECIAL = {
    'edad_minima': 'edad_solicitante',
    'edad_maxima': 'edad_solicitante',
}

# 2. Obtener TODOS los factores de rechazo de TODAS las lineas
c.execute("""
    SELECT id, linea_credito_id, criterio_codigo, criterio_nombre, tipo_factor
    FROM factores_rechazo_linea
    ORDER BY linea_credito_id, orden
""")
factores = c.fetchall()

print(f"Total factores encontrados: {len(factores)}\n")

updates = []
no_match = []

for f in factores:
    fid = f['id']
    linea = f['linea_credito_id']
    codigo_actual = f['criterio_codigo']
    nombre = f['criterio_nombre']
    tipo = f['tipo_factor']
    
    # Determinar codigo correcto
    codigo_nuevo = None
    metodo = None
    
    # 1. Caso especial (edad_minima, edad_maxima)
    if codigo_actual in MAPEO_ESPECIAL:
        codigo_nuevo = MAPEO_ESPECIAL[codigo_actual]
        metodo = "ESPECIAL"
    # 2. Ya es un codigo correcto del master?
    elif codigo_actual in [m['codigo'] for m in master_rows]:
        codigo_nuevo = codigo_actual  # Ya correcto
        metodo = "YA_CORRECTO"
    # 3. Mapear por ID numerico
    elif codigo_actual in id_to_codigo:
        codigo_nuevo = id_to_codigo[codigo_actual]
        metodo = "POR_ID"
    # 4. Mapear por nombre del criterio
    elif nombre.lower().strip() in nombre_to_codigo:
        codigo_nuevo = nombre_to_codigo[nombre.lower().strip()]
        metodo = "POR_NOMBRE"
    
    if codigo_nuevo and codigo_nuevo != codigo_actual:
        updates.append((codigo_nuevo, fid, codigo_actual, nombre, linea, metodo))
        print(f"  [{linea}] '{codigo_actual}' -> '{codigo_nuevo}' ({nombre}) [{metodo}]")
    elif codigo_nuevo == codigo_actual:
        print(f"  [{linea}] '{codigo_actual}' OK ({nombre})")
    else:
        no_match.append((fid, linea, codigo_actual, nombre))
        print(f"  [{linea}] ❌ '{codigo_actual}' SIN MATCH ({nombre})")

# 3. Aplicar actualizaciones
print(f"\n=== RESUMEN ===")
print(f"  Factores a actualizar: {len(updates)}")
print(f"  Sin match: {len(no_match)}")

if updates:
    print("\nAplicando actualizaciones...")
    for codigo_nuevo, fid, codigo_viejo, nombre, linea, metodo in updates:
        c.execute(
            "UPDATE factores_rechazo_linea SET criterio_codigo = ? WHERE id = ?",
            (codigo_nuevo, fid)
        )
    conn.commit()
    print(f"✅ {len(updates)} factores actualizados correctamente")

if no_match:
    print("\n⚠️ Factores sin match (requieren revision manual):")
    for fid, linea, codigo, nombre in no_match:
        print(f"  id={fid} linea={linea} codigo='{codigo}' nombre='{nombre}'")

# 4. Verificar resultado
print("\n=== VERIFICACION POST-MIGRACION (linea 16) ===")
c.execute("""
    SELECT criterio_codigo, criterio_nombre, tipo_factor, operador, valor_umbral
    FROM factores_rechazo_linea
    WHERE linea_credito_id = 16 AND activo = 1
    ORDER BY orden
""")
for f in c.fetchall():
    print(f"  {f['criterio_codigo']}: {f['criterio_nombre']} ({f['tipo_factor']}) {f['operador']} {f['valor_umbral']}")

conn.close()
