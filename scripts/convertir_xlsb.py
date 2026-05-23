# scripts/convertir_xlsb.py
from pathlib import Path
from pyxlsb import open_workbook
import pandas as pd

ruta = Path("./data/raw")
archivos_xlsb = list(ruta.glob("*.xlsb"))

for xlsb_file in archivos_xlsb:
    print(f"Convirtiendo: {xlsb_file.name}")
    xlsx_file = xlsb_file.with_suffix('.xlsx')
    
    with open_workbook(xlsb_file) as wb:
        for sheetname in wb.sheets:
            data = []
            for row in wb.get_sheet(sheetname):
                data.append([cell.v for cell in row])
            if data:
                df = pd.DataFrame(data)
                df.to_excel(xlsx_file, index=False, header=False)
                break
    
    # Opcional: mover o eliminar el xlsb original
    # xlsb_file.rename(ruta / f"procesado_{xlsb_file.name}")