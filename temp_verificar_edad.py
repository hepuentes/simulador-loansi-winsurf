import sqlite3

conn = sqlite3.connect('loansi.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT linea_credito_id, nombre, edad_minima, edad_maxima 
    FROM scoring_config_linea scl 
    JOIN lineas_credito lc ON scl.linea_credito_id = lc.id 
    ORDER BY linea_credito_id
""")

print('Línea | Nombre                 | Edad Mín | Edad Máx')
print('-' * 60)

for row in cursor.fetchall():
    print(f'{row[0]:5} | {row[1]:20} | {row[2]:8} | {row[3]:8}')

conn.close()
