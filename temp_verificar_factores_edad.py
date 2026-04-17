import sqlite3

conn = sqlite3.connect('loansi.db')
cursor = conn.cursor()

# Verificar factores de rechazo que usan edad
cursor.execute("""
    SELECT DISTINCT criterio_nombre, criterio_codigo 
    FROM factores_rechazo_linea 
    WHERE criterio_codigo LIKE '%edad%' 
       OR criterio_nombre LIKE '%edad%'
    ORDER BY criterio_nombre
""")

print('Criterios de edad en factores de rechazo:')
for row in cursor.fetchall():
    print(f'  - {row[0]} (código: {row[1]})')

# Verificar si hay algún criterio que diferencie por tipo de solicitante
cursor.execute("""
    SELECT DISTINCT criterio_nombre, criterio_codigo 
    FROM factores_rechazo_linea 
    WHERE criterio_codigo LIKE '%solicitante%' 
       OR criterio_nombre LIKE '%solicitante%'
       OR criterio_codigo LIKE '%tipo%'
       OR criterio_nombre LIKE '%tipo%'
    ORDER BY criterio_nombre
""")

print('\nCriterios relacionados con tipo de solicitante:')
for row in cursor.fetchall():
    print(f'  - {row[0]} (código: {row[1]})')

conn.close()
