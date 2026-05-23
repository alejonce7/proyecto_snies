"""
Extrae todas las columnas de los archivos SNIES por categoria
Guarda un JSON con la estructura de columnas de cada archivo
"""

import sys
import json
from pathlib import Path
from collections import defaultdict
import pandas as pd

# Agregar src al path
sys.path.append(str(Path(__file__).parent.parent))

from src.quality.diagnostico import leer_archivo_seguro

# Configuracion
RUTA_DATOS = Path("./data/raw")
SALIDA_JSON = Path("./reports/columnas_por_categoria.json")
SALIDA_CSV = Path("./reports/columnas_por_categoria.csv")

def extraer_columnas_archivo(ruta_archivo):
    """Extrae metadata y columnas de un archivo"""
    
    df = leer_archivo_seguro(ruta_archivo)
    
    if df is None or df.empty:
        return None
    
    año = df.attrs.get('año', None)
    categoria = df.attrs.get('categoria', None)
    
    if not año or not categoria or categoria == "indeterminado":
        return None
    
    return {
        "archivo": ruta_archivo.name,
        "año": año,
        "categoria": categoria,
        "num_filas": len(df),
        "num_columnas": len(df.columns),
        "columnas": [str(col) for col in df.columns]
    }

def main():
    print("="*70)
    print("EXTRAYENDO COLUMNAS DE ARCHIVOS SNIES")
    print("="*70)
    
    # Buscar archivos
    archivos = list(RUTA_DATOS.glob("*.xlsx")) + list(RUTA_DATOS.glob("*.xlsb"))
    print(f"Archivos encontrados: {len(archivos)}")
    
    # Extraer informacion
    resultados = []
    por_categoria = defaultdict(list)
    
    for i, archivo in enumerate(archivos, 1):
        print(f"[{i}/{len(archivos)}] {archivo.name}")
        
        info = extraer_columnas_archivo(archivo)
        if info:
            resultados.append(info)
            por_categoria[info["categoria"]].append(info)
    
    # Guardar JSON completo
    SALIDA_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(SALIDA_JSON, 'w', encoding='utf-8') as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False, default=str)
    
    # Guardar CSV resumido
    filas_csv = []
    for r in resultados:
        filas_csv.append({
            "archivo": r["archivo"],
            "año": r["año"],
            "categoria": r["categoria"],
            "num_columnas": r["num_columnas"],
            "columnas": " | ".join(r["columnas"][:20])
        })
    
    df_csv = pd.DataFrame(filas_csv)
    df_csv.to_csv(SALIDA_CSV, index=False, encoding='utf-8-sig')
    
    # Mostrar resumen
    print("\n" + "="*70)
    print("RESUMEN POR CATEGORIA")
    print("="*70)
    
    for categoria, archivos_cat in por_categoria.items():
        print(f"\n{categoria.upper()}: {len(archivos_cat)} archivos")
        print("   Años:", sorted([a["año"] for a in archivos_cat]))
        
        todas_columnas = set()
        for a in archivos_cat:
            todas_columnas.update(a["columnas"])
        
        print(f"   Columnas unicas totales: {len(todas_columnas)}")
        print(f"   Primeras 10 columnas: {list(todas_columnas)[:10]}")
    
    print("\n" + "="*70)
    print(f"Reportes guardados:")
    print(f"   - {SALIDA_JSON}")
    print(f"   - {SALIDA_CSV}")
    print("="*70)
    
    return resultados

if __name__ == "__main__":
    resultados = main()
    
    if resultados:
        print(f"\nTotal archivos procesados: {len(resultados)}")
    else:
        print("No se pudo extraer informacion de ningun archivo")