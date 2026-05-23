"""
Script independiente para cargar el archivo de docentes 2007
Formato especial: columnas por año-semestre
"""

import sys
from pathlib import Path

# Agregar la ruta src al path
sys.path.append(str(Path(__file__).parent.parent / "src"))

# pyrefly: ignore [missing-import]
from quality.diagnostico import leer_archivo_seguro

import pandas as pd
import duckdb
import re


# Configuracion
DB_PATH = Path("./data/database/snies.duckdb")
RUTA_ARCHIVO = Path("./data/raw/articles-391587_recurso.xlsx")

# Mapeo de categorias
CATEGORIA_TO_ID = {
    "inscritos": 1,
    "admitidos": 2,
    "matriculados": 3,
    "primer_curso": 4,
    "graduados": 5,
    "docentes": 6,
    "administrativos": 7
}

def conectar_db():
    return duckdb.connect(str(DB_PATH))

def cargar_docentes_2007():
    """Carga el archivo de docentes 2007"""
    
    print("="*70)
    print("CARGANDO DOCENTES 2007")
    print("="*70)
    
    # Verificar que el archivo existe
    if not RUTA_ARCHIVO.exists():
        print(f"Error: No se encuentra el archivo {RUTA_ARCHIVO}")
        return 0
    
    # Leer archivo usando la funcion del diagnostico
    print(f"Leyendo archivo: {RUTA_ARCHIVO}")
    df = leer_archivo_seguro(RUTA_ARCHIVO)
    
    if df is None or df.empty:
        print("Error: No se pudo leer el archivo")
        return 0
    
    print(f"Dimensiones: {df.shape[0]} filas, {df.shape[1]} columnas")
    print(f"Columnas: {list(df.columns)[:15]}...")
    
    # Identificar columnas de valor (formato: "2007-1", "2007-2", etc.)
    columnas_valor = []
    for col in df.columns:
        col_str = str(col)
        match = re.match(r'(\d{4})-(\d)', col_str)
        if match:
            año = int(match.group(1))
            semestre = int(match.group(2))
            columnas_valor.append({
                'columna': col,
                'año': año,
                'semestre': semestre
            })
    
    print(f"Columnas de valor encontradas: {len(columnas_valor)}")
    
    # Identificar columnas de metadata por posicion (segun el JSON)
    # Las columnas estan en orden: Codigo, Nombre, Principal, Sector, Caracter, etc.
    col_codigo = df.columns[0]  # "Código de la Institución"
    col_nombre = df.columns[1]  # "Institución de Educación Superior (IES)"
    col_departamento = None
    col_municipio = None
    
    # Buscar departamento y municipio
    for col in df.columns:
        col_str = str(col).lower()
        if 'departamento' in col_str and 'domicilio' in col_str:
            col_departamento = col
        if 'municipio' in col_str and 'domicilio' in col_str:
            col_municipio = col
    
    print(f"Columna codigo: {col_codigo}")
    print(f"Columna nombre: {col_nombre}")
    print(f"Columna departamento: {col_departamento}")
    print(f"Columna municipio: {col_municipio}")
    
    # Limpiar codigos
    df[col_codigo] = df[col_codigo].astype(str).str.replace('.0', '', regex=False).str.strip()
    df = df[df[col_codigo].str.isdigit()]
    
    if df.empty:
        print("No hay datos validos despues de limpiar codigos")
        return 0
    
    # Generar registros
    conn = conectar_db()
    id_hecho_start = conn.execute("SELECT COALESCE(MAX(id_hecho), 0) FROM hecho_snies").fetchone()[0]
    
    registros = []
    id_hecho = id_hecho_start
    
    for idx, row in df.iterrows():
        codigo = row[col_codigo]
        if not codigo or codigo == 'nan':
            continue
        
        nombre = row[col_nombre] if col_nombre else None
        departamento = row[col_departamento] if col_departamento else None
        municipio = row[col_municipio] if col_municipio else None
        
        for col_valor in columnas_valor:
            valor = row[col_valor['columna']]
            if pd.isna(valor) or valor == 0:
                continue
            try:
                valor_float = float(valor)
            except:
                continue
            
            id_hecho += 1
            registros.append({
                "id_hecho": id_hecho,
                "año": col_valor['año'],
                "id_categoria": 6,  # docentes
                "codigo_ies": codigo,
                "nombre_ies": nombre,
                "departamento": departamento,
                "municipio": municipio,
                "valor_numerico": valor_float
            })
    
    print(f"Registros generados: {len(registros)}")
    
    if not registros:
        print("No se generaron registros")
        return 0
    
    # Cargar a la base de datos
    df_registros = pd.DataFrame(registros)
    conn.register('temp_docentes', df_registros)
    
    # Insertar dim_ies
    conn.execute("""
        INSERT OR REPLACE INTO dim_ies (codigo_ies, nombre_ies, sector, caracter, metodologia, estado)
        SELECT DISTINCT codigo_ies, nombre_ies, NULL, NULL, NULL, 'ACTIVO'
        FROM temp_docentes
        WHERE codigo_ies IS NOT NULL
    """)
    print("dim_ies actualizada")
    
    # Insertar dim_ubicacion
    conn.execute("""
        INSERT OR IGNORE INTO dim_ubicacion (id_ubicacion, tipo, nombre, nombre_departamento)
        SELECT DISTINCT replace(departamento, ' ', '_'), 'departamento', departamento, departamento
        FROM temp_docentes WHERE departamento IS NOT NULL
        UNION
        SELECT DISTINCT replace(municipio, ' ', '_'), 'municipio', municipio, departamento
        FROM temp_docentes WHERE municipio IS NOT NULL
    """)
    print("dim_ubicacion actualizada")
    
    # Insertar hecho_snies
    conn.execute("""
        INSERT INTO hecho_snies (id_hecho, año, id_categoria, codigo_ies, id_departamento, id_municipio, valor_numerico)
        SELECT id_hecho, año, id_categoria, codigo_ies,
               replace(departamento, ' ', '_'), replace(municipio, ' ', '_'), valor_numerico
        FROM temp_docentes
    """)
    print("hecho_snies actualizada")
    
    conn.unregister('temp_docentes')
    conn.commit()
    conn.close()
    
    print("="*70)
    print(f"Carga completada: {len(registros)} registros")
    print("="*70)
    
    return len(registros)

if __name__ == "__main__":
    cargar_docentes_2007()