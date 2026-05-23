"""
Recarga solo los archivos que fallaron en la ejecucion anterior
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.etl.pipeline import conectar_db, procesar_archivo

# Archivos que fallaron (segun el log)
archivos_fallidos = [
    "articles-391582_recurso.xlsx",  # docentes 2018
    "articles-391583_recurso.xlsx",  # docentes 2017
    "articles-391584_recurso.xlsx",  # docentes 2016
    "articles-391585_recurso.xlsx",  # docentes 2015
    "articles-391586_recurso.xlsx",  # docentes 2014
    "articles-391587_recurso.xlsx",  # docentes 2007
    "articles-391588_recurso.xlsx",  # administrativos 2018
    "articles-391589_recurso.xlsx",  # administrativos 2017
    "articles-391590_recurso.xlsx",  # administrativos 2016
    "articles-391591_recurso.xlsx",  # administrativos 2015
    "articles-391592_recurso.xlsx",  # administrativos 2014
    "articles-401903_recurso.xlsx",  # administrativos 2019
    "articles-401904_recurso.xlsx",  # docentes 2019
    "articles-406664_recurso.xlsx",  # administrativos 2020
    "articles-406665_recurso.xlsx",  # docentes 2020
    "articles-411247_recurso.xlsx",  # administrativos 2021
    "articles-411248_recurso.xlsx",  # docentes 2021
    "articles-416249_recurso.xlsx",  # docentes 2022
    "articles-416250_recurso.xlsx",  # administrativos 2022
    "articles-421535_recurso.xlsx",  # graduados 2023
    "articles-421537_recurso.xlsx",  # administrativos 2023
    "articles-421538_recurso.xlsx",  # inscritos 2023
    "articles-421539_recurso.xlsx",  # matriculados 2023
    "articles-421540_recurso.xlsx",  # admitidos 2023
    "articles-421541_recurso.xlsx",  # primer_curso 2023
    "articles-421822_recurso.xlsx",  # docentes 2023
    "articles-425146_recurso.xlsx",  # graduados 2024
    "articles-425147_recurso.xlsx",  # administrativos 2024
    "articles-425148_recurso.xlsx",  # inscritos 2024
    "articles-425151_recurso.xlsx",  # matriculados 2024
    "articles-425153_recurso.xlsx",  # admitidos 2023 (duplicado)
    "articles-425154_recurso.xlsx",  # admitidos 2024
    "articles-425155_recurso.xlsx",  # primer_curso 2024
    "articles-425156_recurso.xlsx",  # docentes 2024
]

ruta_raw = Path("./data/raw")
conn = conectar_db()

total = 0
for nombre in archivos_fallidos:
    ruta = ruta_raw / nombre
    if ruta.exists():
        print(f"Procesando: {nombre}")
        registros = procesar_archivo(conn, ruta)
        total += registros
    else:
        print(f"No encontrado: {nombre}")

conn.close()
print(f"Total registros cargados: {total}")