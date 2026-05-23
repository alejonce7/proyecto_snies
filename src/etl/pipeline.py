"""
ETL PIPELINE PARA DATOS SNIES
Fase 2: Extraccion, Transformacion y Carga
Maneja formatos ancho (2000-2013) sumando semestres, y largo (2014-2024)
Optimizado con batch processing
"""

import pandas as pd
import duckdb
from pathlib import Path
import sys
import logging
from datetime import datetime
from tqdm import tqdm
import re
import time

sys.path.append(str(Path(__file__).parent.parent))
from quality.diagnostico import (
    leer_archivo_seguro,
    encontrar_columna_codigo_ies,
    encontrar_columna_nombre_ies,
    limpiar_filas_notas
)

# Configuracion
RAW_DATA_PATH = Path("./data/raw")
DB_PATH = Path("./data/database/snies.duckdb")
LOG_PATH = Path("./logs")

def crear_carpetas():
    for path in [RAW_DATA_PATH, DB_PATH.parent, LOG_PATH]:
        path.mkdir(parents=True, exist_ok=True)

crear_carpetas()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH / 'etl.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

CATEGORIA_TO_ID = {
    "inscritos": 1,
    "admitidos": 2,
    "matriculados": 3,
    "primer_curso": 4,
    "graduados": 5,
    "docentes": 6,
    "administrativos": 7
}

BATCH_SIZE = 10000

def conectar_db():
    return duckdb.connect(str(DB_PATH))

def procesar_formato_ancho(conn, df, categoria, nombre_archivo):
    """Procesa archivos en formato ancho (2000-2013) sumando los dos semestres por año - VERSION OPTIMIZADA"""
    
    col_codigo = encontrar_columna_codigo_ies(df)
    col_nombre = encontrar_columna_nombre_ies(df)
    
    if not col_codigo:
        logger.warning(f"  No se encontro columna de codigo para {nombre_archivo}")
        return 0
    
    df = limpiar_filas_notas(df, col_codigo)
    
    # Limpiar codigos
    df[col_codigo] = df[col_codigo].astype(str).str.replace('.0', '', regex=False).str.strip()
    df = df[df[col_codigo].str.isdigit()]
    
    if df.empty:
        return 0
    
    # Identificar columnas de valor
    columnas_valor = {}
    for col in df.columns:
        col_str = str(col)
        match = re.match(r'Total\s+(\d{4})-(\d)', col_str)
        if match:
            año = int(match.group(1))
            if año not in columnas_valor:
                columnas_valor[año] = []
            columnas_valor[año].append(col)
    
    if not columnas_valor:
        logger.warning(f"  No se encontraron columnas de valor en formato ancho")
        return 0
    
    # Sumar valores por año vectorizado
    id_hecho_start = conn.execute("SELECT COALESCE(MAX(id_hecho), 0) FROM hecho_snies").fetchone()[0]
    
    registros = []
    id_hecho = id_hecho_start
    
    for idx, row in df.iterrows():
        codigo = row[col_codigo]
        if not codigo:
            continue
        
        nombre = row[col_nombre] if col_nombre else None
        
        for año, cols in columnas_valor.items():
            valor_total = 0
            for col in cols:
                valor = row[col]
                if pd.notna(valor) and valor != 0:
                    try:
                        valor_total += float(valor)
                    except:
                        pass
            
            if valor_total > 0:
                id_hecho += 1
                registros.append({
                    "id_hecho": id_hecho,
                    "año": año,
                    "codigo_ies": codigo,
                    "nombre_ies": nombre,
                    "valor_numerico": valor_total,
                    "id_categoria": CATEGORIA_TO_ID.get(categoria, 1)
                })
    
    if not registros:
        return 0
    
    # Cargar directamente a DuckDB
    conn.register('temp_ancho', pd.DataFrame(registros))
    
    # Insertar hecho_snies
    conn.execute("""
        INSERT INTO hecho_snies (id_hecho, año, id_categoria, codigo_ies, id_programa, id_departamento, id_municipio, valor_numerico)
        SELECT id_hecho, año, id_categoria, codigo_ies, NULL, NULL, NULL, valor_numerico
        FROM temp_ancho
    """)
    
    # Insertar dim_ies
    conn.execute("""
        INSERT OR REPLACE INTO dim_ies (codigo_ies, nombre_ies, sector, caracter, metodologia, estado)
        SELECT DISTINCT codigo_ies, nombre_ies, NULL, NULL, NULL, 'ACTIVO'
        FROM temp_ancho
        WHERE codigo_ies IS NOT NULL
    """)
    
    conn.unregister('temp_ancho')
    conn.commit()
    
    return len(registros)

def transformar_y_cargar(conn, df, año, categoria, nombre_archivo):
    """Transforma el DataFrame y carga a las tablas usando DuckDB (mas rapido)"""
    
    if df is None or df.empty:
        logger.warning(f"  DataFrame vacio para {nombre_archivo}")
        return 0
    
    col_codigo = encontrar_columna_codigo_ies(df)
    col_nombre = encontrar_columna_nombre_ies(df)
    
    if not col_codigo:
        logger.warning(f"  No se encontro columna de codigo para {nombre_archivo}")
        return 0
    
    df = limpiar_filas_notas(df, col_codigo)
    
    # Buscar columnas de programa
    col_codigo_programa = None
    col_nombre_programa = None
    col_nivel_academico = None
    
    for col in df.columns:
        col_str = str(col).lower()
        if 'codigo snies' in col_str or 'código snies' in col_str:
            col_codigo_programa = col
        if 'programa academico' in col_str or 'programa académico' in col_str:
            col_nombre_programa = col
        if 'nivel academico' in col_str or 'nivel académico' in col_str:
            col_nivel_academico = col
    
    # Buscar columnas de ubicacion y metadata
    col_departamento = None
    col_municipio = None
    col_sector = None
    col_caracter = None
    col_metodologia_ies = None
    
    for col in df.columns:
        col_str = str(col).lower()
        if 'departamento' in col_str and 'ies' in col_str:
            col_departamento = col
        if 'municipio' in col_str and 'ies' in col_str:
            col_municipio = col
        if 'sector' in col_str:
            col_sector = col
        if 'caracter' in col_str or 'carácter' in col_str:
            col_caracter = col
        if 'metodología' in col_str or 'metodologia' in col_str:
            if 'programa' not in col_str:
                col_metodologia_ies = col
    
    # CORRECCION 4: Verificar que las columnas existen antes de usarlas
    columnas_df = set(df.columns)
    
    if col_departamento and col_departamento not in columnas_df:
        col_departamento = None
    if col_municipio and col_municipio not in columnas_df:
        col_municipio = None
    if col_sector and col_sector not in columnas_df:
        col_sector = None
    if col_caracter and col_caracter not in columnas_df:
        col_caracter = None
    if col_metodologia_ies and col_metodologia_ies not in columnas_df:
        col_metodologia_ies = None
    if col_codigo_programa and col_codigo_programa not in columnas_df:
        col_codigo_programa = None
    if col_nombre_programa and col_nombre_programa not in columnas_df:
        col_nombre_programa = None
    if col_nivel_academico and col_nivel_academico not in columnas_df:
        col_nivel_academico = None
    # Buscar columna de valor numerico
    col_valor = None
    
    variantes_categoria = {
        "inscritos": ["inscripciones", "inscritos", "inscripcion"],
        "admitidos": ["admitidos", "admitdos", "admisiones", "admissiones"],
        "matriculados": ["matriculados", "matriculas"],
        "primer_curso": ["primer curso", "primer_curso", "primer"],
        "graduados": ["graduados"],
        "docentes": ["no. de docentes", "no. docentes", "docentes", "docente", "total docentes", "DOCENTES"],
        "administrativos": ["total", "administrativos"]
    }
    
    columnas_excluir = [
        "sexo", "genero", "género", "id sexo", "id genero",
        "metodologia", "metodología", "sector", "caracter",
        "principal", "seccional", "ies padre", "codigo",
        "auxiliar", "tecnico", "profesional", "directivo", "servicios",
        "id maximo nivel", "maximo nivel", "id tiempo", "tiempo de dedicacion",
        "id tipo contrato", "tipo de contrato", "formacion", "nivel"
    ]
    
    variantes = variantes_categoria.get(categoria, [categoria])
    
    # CORRECCION 2: Logica especifica para docentes
    if categoria == "docentes":
        for col in df.columns:
            col_str = str(col).lower()
            if 'no. de docentes' in col_str or 'no. docentes' in col_str or 'docentes' in col_str:
                if any(excl in col_str for excl in ['genero', 'sexo', 'formacion', 'nivel', 'tiempo', 'contrato']):
                    continue
                col_valor = col
                logger.info(f"  Columna de valor para docentes encontrada: '{col}'")
                break
    
    # Busqueda general si no se encontro antes
    if not col_valor:
        for col in df.columns:
            col_str = str(col).lower()
            if any(excl in col_str for excl in columnas_excluir):
                continue
            for variante in variantes:
                if variante in col_str:
                    col_valor = col
                    logger.info(f"  Columna de valor encontrada: '{col}' (variante: {variante})")
                    break
            if col_valor:
                break
    
    if not col_valor:
        for col in df.columns:
            col_str = str(col).lower()
            if 'id' in col_str:
                continue
            try:
                if pd.api.types.is_numeric_dtype(df[col]):
                    col_valor = col
                    logger.info(f"  Columna numerica encontrada: '{col}'")
                    break
            except:
                pass
    
    if not col_valor:
        logger.warning(f"  No se encontro columna de valor para {nombre_archivo}")
        return 0
       
    # Crear df_clean base
    df_clean = df[[col_codigo, col_valor]].copy()
    df_clean.columns = ['codigo_ies', 'valor_numerico']
    
    # Limpiar codigos
    df_clean['codigo_ies'] = df_clean['codigo_ies'].astype(str).str.replace('.0', '', regex=False).str.strip()
    df_clean = df_clean[df_clean['codigo_ies'].str.isdigit()]
    df_clean['valor_numerico'] = pd.to_numeric(df_clean['valor_numerico'], errors='coerce')
    df_clean = df_clean[df_clean['valor_numerico'] > 0]
    
    if df_clean.empty:
        return 0
    
    # Agregar columnas fijas
    df_clean['año'] = año
    df_clean['id_categoria'] = CATEGORIA_TO_ID.get(categoria, 1)
    
    # Agregar nombre IES (si existe)
    if col_nombre and col_nombre in df.columns:
        df_clean['nombre_ies'] = df[col_nombre].astype(str)
    else:
        df_clean['nombre_ies'] = None
    
    # Agregar programa (si existe)
    if col_codigo_programa and col_codigo_programa in df.columns:
        df_clean['id_programa'] = df[col_codigo_programa].astype(str)
    else:
        df_clean['id_programa'] = None
    
    # Agregar ubicacion (si existe)
    if col_departamento and col_departamento in df.columns:
        df_clean['departamento'] = df[col_departamento].astype(str)
    if col_municipio and col_municipio in df.columns:
        df_clean['municipio'] = df[col_municipio].astype(str)
    
    # Agregar sector y caracter (si existen)
    if col_sector and col_sector in df.columns:
        df_clean['sector'] = df[col_sector].astype(str)
    if col_caracter and col_caracter in df.columns:
        df_clean['caracter'] = df[col_caracter].astype(str)
    
    # Agregar metodologia SOLO si la columna existe
    if col_metodologia_ies and col_metodologia_ies in df.columns:
        df_clean['metodologia_ies'] = df[col_metodologia_ies].astype(str).str.upper().str.strip()
    
    # Obtener max id_hecho
    max_id = conn.execute("SELECT COALESCE(MAX(id_hecho), 0) FROM hecho_snies").fetchone()[0]
    
    # Registrar el DataFrame temporal en DuckDB
    conn.register('temp_df', df_clean)
    
    # Insertar dim_ies (sin usar metodologia_ies si no existe)
    # Verificar si metodologia_ies existe en temp_df
    tiene_metodologia = False
    try:
        result = conn.execute("SELECT COUNT(*) FROM pragma_table_info('temp_df') WHERE name = 'metodologia_ies'").fetchone()
        if result and result[0] > 0:
            tiene_metodologia = True
    except:
        pass
    
    if tiene_metodologia:
        conn.execute("""
            INSERT OR REPLACE INTO dim_ies (codigo_ies, nombre_ies, sector, caracter, metodologia, estado)
            SELECT DISTINCT 
                codigo_ies, 
                nombre_ies, 
                sector, 
                caracter,
                CASE 
                    WHEN metodologia_ies IS NOT NULL THEN
                        CASE 
                            WHEN metodologia_ies LIKE '%PRESENCIAL%' THEN 'PRESENCIAL'
                            WHEN metodologia_ies LIKE '%VIRTUAL%' THEN 'VIRTUAL'
                            WHEN metodologia_ies LIKE '%DISTANCIA%' THEN 'DISTANCIA'
                            WHEN metodologia_ies LIKE '%HIBRIDA%' OR metodologia_ies LIKE '%HÍBRIDA%' THEN 'HIBRIDA'
                            ELSE metodologia_ies
                        END
                    ELSE NULL
                END,
                'ACTIVO'
            FROM temp_df
            WHERE codigo_ies IS NOT NULL
        """)
    else:
        conn.execute("""
            INSERT OR REPLACE INTO dim_ies (codigo_ies, nombre_ies, sector, caracter, metodologia, estado)
            SELECT DISTINCT 
                codigo_ies, 
                nombre_ies, 
                sector, 
                caracter,
                NULL as metodologia,
                'ACTIVO'
            FROM temp_df
            WHERE codigo_ies IS NOT NULL
        """)
    
    # Insertar dim_ubicacion
    conn.execute("""
        INSERT OR IGNORE INTO dim_ubicacion (id_ubicacion, tipo, nombre, nombre_departamento)
        SELECT DISTINCT 
            CASE WHEN departamento IS NOT NULL THEN replace(departamento, ' ', '_') END,
            'departamento', departamento, departamento
        FROM temp_df WHERE departamento IS NOT NULL
        UNION
        SELECT DISTINCT 
            CASE WHEN municipio IS NOT NULL THEN replace(municipio, ' ', '_') END,
            'municipio', municipio, departamento
        FROM temp_df WHERE municipio IS NOT NULL
    """)
    
    # Insertar dim_programa (solo si existe columna id_programa)
    if col_codigo_programa:
        conn.execute("""
            INSERT OR IGNORE INTO dim_programa (id_programa, codigo_ies, nombre_programa, nivel_academico, codigo_snies)
            SELECT DISTINCT 
                id_programa,
                codigo_ies,
                id_programa as nombre_programa,
                NULL as nivel_academico,
                id_programa as codigo_snies
            FROM temp_df
            WHERE id_programa IS NOT NULL
        """)
    
    # Insertar hecho_snies (manejando id_programa que puede ser NULL)
    conn.execute(f"""
        INSERT INTO hecho_snies (id_hecho, año, id_categoria, codigo_ies, id_programa, id_departamento, id_municipio, valor_numerico)
        SELECT 
            {max_id} + ROW_NUMBER() OVER (),
            año, id_categoria, codigo_ies, id_programa,
            replace(departamento, ' ', '_'),
            replace(municipio, ' ', '_'),
            valor_numerico
        FROM temp_df
    """)
    
    # Limpiar
    conn.unregister('temp_df')
    conn.commit()
    
    # Contar registros insertados
    total = conn.execute(f"SELECT COUNT(*) FROM hecho_snies WHERE id_hecho > {max_id}").fetchone()[0]
    
    return total

def procesar_archivo(conn, ruta_archivo):
    """Procesa un archivo, detectando si es formato ancho o largo con logging de tiempo"""
    
    tiempo_total_inicio = time.time()
    
    logger.info(f"Procesando: {ruta_archivo.name}")
    
    tiempo_lectura_inicio = time.time()
    df = leer_archivo_seguro(ruta_archivo)
    tiempo_lectura = time.time() - tiempo_lectura_inicio
    logger.info(f"  Tiempo lectura: {tiempo_lectura:.2f}s")
    
    if df is None or df.empty:
        logger.warning(f"  No se pudo leer el archivo")
        return 0
    
    año = df.attrs.get('año', None)
    categoria = df.attrs.get('categoria', None)
    
    if not año:
        logger.warning(f"  No se pudo detectar el año")
        return 0
    
    if not categoria or categoria == "indeterminado":
        logger.warning(f"  No se pudo detectar categoria para año {año}")
        return 0
    
    # Detectar si es formato ancho (2000-2013)
    es_formato_ancho = False
    for col in df.columns:
        if re.match(r'Total \d{4}-\d', str(col)):
            es_formato_ancho = True
            break
    
    tiempo_transform_inicio = time.time()
    
    if es_formato_ancho:
        logger.info(f"  Detectado formato ancho para {categoria}")
        registros = procesar_formato_ancho(conn, df, categoria, ruta_archivo.name)
    else:
        logger.info(f"  Detectado formato largo para {categoria} {año}")
        registros = transformar_y_cargar(conn, df, año, categoria, ruta_archivo.name)
    
    tiempo_transform = time.time() - tiempo_transform_inicio
    logger.info(f"  Tiempo transformacion/carga: {tiempo_transform:.2f}s")
    
    tiempo_total = time.time() - tiempo_total_inicio
    logger.info(f"  Tiempo total archivo: {tiempo_total:.2f}s")
    logger.info(f"  Cargados {registros} registros")
    
    return registros

def ejecutar_etl():
    """Ejecuta el ETL completo con estadisticas de tiempo"""
    
    inicio_total = time.time()
    
    logger.info("="*70)
    logger.info("INICIANDO ETL SNIES")
    logger.info("="*70)
    
    conn = conectar_db()
    archivos = list(RAW_DATA_PATH.glob("*.xlsx")) + list(RAW_DATA_PATH.glob("*.xlsb"))
    
    logger.info(f"Archivos encontrados: {len(archivos)} en {RAW_DATA_PATH}")
    
    total_registros = 0
    tiempos_por_archivo = []
    
    for i, archivo in enumerate(tqdm(archivos, desc="Procesando archivos"), 1):
        inicio_archivo = time.time()
        try:
            registros = procesar_archivo(conn, archivo)
            total_registros += registros
        except Exception as e:
            logger.error(f"Error procesando {archivo.name}: {e}")
        
        tiempo_archivo = time.time() - inicio_archivo
        tiempos_por_archivo.append(tiempo_archivo)
        
        # Mostrar estimacion cada 10 archivos
        if i % 10 == 0:
            tiempo_promedio = sum(tiempos_por_archivo) / len(tiempos_por_archivo)
            archivos_restantes = len(archivos) - i
            tiempo_restante = tiempo_promedio * archivos_restantes
            logger.info(f"  Progreso: {i}/{len(archivos)} archivos")
            logger.info(f"  Tiempo promedio: {tiempo_promedio:.1f}s/archivo")
            logger.info(f"  Tiempo restante estimado: {tiempo_restante/60:.1f} minutos")
    
    conn.close()
    
    tiempo_total = time.time() - inicio_total
    
    logger.info("="*70)
    logger.info(f"ETL COMPLETADO")
    logger.info(f"Total registros cargados: {total_registros}")
    logger.info(f"Tiempo total: {tiempo_total/60:.2f} minutos")
    if tiempos_por_archivo:
        logger.info(f"Tiempo promedio por archivo: {sum(tiempos_por_archivo)/len(tiempos_por_archivo):.2f} segundos")
    logger.info("="*70)
    
    return total_registros

def ejecutar_para_año_futuro(año, ruta_archivo):
    """Ejecuta ETL para un año nuevo (2025, 2026) - DEMO ROBUSTEZ"""
    
    logger.info("="*70)
    logger.info(f"PROCESANDO AÑO FUTURO: {año}")
    logger.info("="*70)
    
    conn = conectar_db()
    ruta = Path(ruta_archivo)
    
    if not ruta.exists():
        logger.error(f"Archivo no encontrado: {ruta}")
        return 0
    
    registros = procesar_archivo(conn, ruta)
    conn.close()
    
    logger.info(f"Año {año} procesado. Registros cargados: {registros}")
    return registros

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='ETL SNIES')
    parser.add_argument('--modo', choices=['historico', 'futuro'], default='historico')
    parser.add_argument('--año', type=int, help='Año a procesar (para modo futuro)')
    parser.add_argument('--archivo', type=str, help='Ruta del archivo (para modo futuro)')
    
    args = parser.parse_args()
    
    if args.modo == 'historico':
        ejecutar_etl()
    else:
        if not args.año or not args.archivo:
            print("Para modo futuro necesita: --año YYYY --archivo ruta")
        else:
            ejecutar_para_año_futuro(args.año, args.archivo)