"""
DIAGNÓSTICO DE CALIDAD DATOS SNIES
Para archivos con nombres genéricos tipo "articles-425148_recurso.xlsx"
Infere año y categoría desde el contenido de cada archivo
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
from collections import defaultdict
import re
import warnings
warnings.filterwarnings('ignore')

# Para archivos xlsb
try:
    from pyxlsb import open_workbook
    HAS_XLSB = True
except ImportError:
    HAS_XLSB = False

# ============================================================
# CONFIGURACIÓN
# ============================================================
CARPETA_DATOS = Path("./data/raw")  
REPORTE_SALIDA = Path("./reports/calidad_datos")

# Patrones para detectar año en los datos
PATRONES_AÑO = [r'\b(200[0-9]|201[0-9]|202[0-6])\b']

# Palabras clave para detectar categoría SNIES desde columnas o datos
KEYWORDS_CATEGORIAS = {
    "inscritos": [
        "INSCRITOS", 
        "ESTUDIANTES INSCRITOS", 
        "ESTUDIANTES INSCRITOS EN INSTITUCIONES DE EDUCACIÓN SUPERIOR","INSCRIPCIONES"
    ],
    "admitidos": [
        "ADMITIDOS","ADMISIONES", 
        "ESTUDIANTES ADMITIDOS", 
        "ESTUDIANTES ADMITIDOS EN INSTITUCIONES DE EDUCACIÓN SUPERIOR"
    ],
    "primer_curso": [
        "PRIMER CURSO", 
        "MATRICULADOS EN PRIMER CURSO", 
        "ESTUDIANTES MATRICULADOS EN PRIMER CURSO"
    ],
    "matriculados": [
        "MATRICULADOS", 
        "ESTUDIANTES MATRICULADOS", 
        "ESTUDIANTES MATRICULADOS EN INSTITUCIONES DE EDUCACIÓN SUPERIOR"
    ],
    "graduados": [
        "GRADUADOS", 
        "ESTUDIANTES GRADUADOS", 
        "ESTUDIANTES GRADUADOS EN INSTITUCIONES DE EDUCACIÓN SUPERIOR"
    ],
    "docentes": [
        "DOCENTES", "DOCENTE",
        "DOCENTES EN INSTITUCIONES DE EDUCACIÓN SUPERIOR"
    ],
    "administrativos": [
        "ADMINISTRATIVOS", 
        "PERSONAL ADMINISTRATIVO", 
        "PERSONAL ADMINISTRATIVO EN INSTITUCIONES DE EDUCACIÓN SUPERIOR"
    ]
}

# Columnas que ayudan a identificar cada categoría
COLUMNAS_ID_CATEGORIA = {
    "inscritos": ["inscritos", "aspirantes", "preinscritos", "solicitudes"],
    "admitidos": ["admitidos", "aceptados", "cupo"],
    "matriculados": ["matriculados", "estudiantes", "alumnos", "total_estudiantes"],
    "graduados": ["graduados", "egresados", "titulados"],
    "docentes": ["docentes", "profesores", "academicos"],
    "administrativos": ["administrativos", "personal_administrativo", "funcionarios"]
}

# ============================================================
# FUNCIONES DE LECTURA
# ============================================================

def leer_archivo_seguro(ruta_archivo):
    """Lee archivo buscando la tabla en cualquier hoja y cualquier fila"""
    try:
        extension = ruta_archivo.suffix.lower()
        
        if extension == '.xlsx':
            xl = pd.ExcelFile(ruta_archivo)
            for sheet_name in xl.sheet_names:
                df_raw = pd.read_excel(ruta_archivo, sheet_name=sheet_name, header=None)
                df = buscar_tabla_en_dataframe(df_raw, sheet_name, ruta_archivo.name)
                if df is not None:
                    return df
            return None
            
        elif extension == '.xlsb' and HAS_XLSB:
            with open_workbook(ruta_archivo) as wb:
                for sheetname in wb.sheets:
                    data = []
                    for row in wb.get_sheet(sheetname):
                        data.append([cell.v for cell in row])
                    if data:
                        df_raw = pd.DataFrame(data)
                        df = buscar_tabla_en_dataframe(df_raw, sheetname, ruta_archivo.name)
                        if df is not None:
                            return df
            return None
        else:
            return None
            
    except Exception as e:
        return None

def buscar_tabla_en_dataframe(df_raw, sheet_name, archivo_nombre):
    """Busca la fila donde comienza la tabla en un DataFrame"""
    
    # Palabras clave para encabezados
    palabras_clave = [
        'CÓDIGO DE', 'CODIGO DE', 'Código de', 'IES PADRE',
        'Institución de Educación Superior', 'Sector IES', 'Carácter'
    ]
    
    for idx in range(min(100, len(df_raw))):
        try:
            # Obtener texto de la fila
            valores = []
            for celda in df_raw.iloc[idx]:
                if pd.isna(celda):
                    valores.append('')
                else:
                    valores.append(str(celda))
            
            texto_fila = ' '.join(valores)
            
            # Buscar encabezados
            es_encabezado = False
            for palabra in palabras_clave:
                if palabra.lower() in texto_fila.lower():
                    es_encabezado = True
                    break
            
            # También buscar si tiene al menos 3 columnas con texto no vacío
            cols_no_vacias = sum(1 for v in valores if len(v.strip()) > 0)
            if cols_no_vacias >= 5:
                es_encabezado = True
            
            if es_encabezado and cols_no_vacias >= 3:
                
                
                # Extraer año de filas superiores
                año = None
                for i in range(min(10, idx)):
                    texto_superior = ''
                    for celda in df_raw.iloc[i]:
                        if pd.notna(celda):
                            texto_superior += str(celda) + ' '
                    años = re.findall(r'\b(200[0-9]|201[0-9]|202[0-6])\b', texto_superior)
                    if años:
                        año = int(años[0])
                       
                        break
                
                # Extraer categoría de filas superiores
                categoria = extraer_categoria_desde_filas_superiores(df_raw, idx)
                
                # Crear DataFrame con columnas
                nuevas_columnas = []
                for celda in df_raw.iloc[idx]:
                    if pd.isna(celda):
                        nuevas_columnas.append('')
                    else:
                        col_name = str(celda).replace('\n', ' ').strip()
                        nuevas_columnas.append(col_name)
                
                df = df_raw.iloc[idx + 1:].copy()
                df.columns = nuevas_columnas
                
                # Eliminar columnas sin nombre
                df = df.loc[:, [c for c in df.columns if str(c).strip() != '']]
                
                # Eliminar filas vacías
                df = df.dropna(how='all').reset_index(drop=True)
                
                if len(df) > 0 and len(df.columns) > 0:
                    if año:
                        df.attrs['año'] = año
                    if categoria:
                        df.attrs['categoria'] = categoria
                    return df
                    
        except Exception as e:
            continue
    
    return None

def extraer_año_desde_filas_superiores(df_raw, fila_inicio_tabla):
    """Extrae el año desde las filas superiores a la tabla"""
    for idx in range(min(15, fila_inicio_tabla)):
        try:
            texto = ''
            for celda in df_raw.iloc[idx]:
                if pd.notna(celda):
                    texto += str(celda) + ' '
            años = re.findall(r'\b(200[0-9]|201[0-9]|202[0-6])\b', texto)
            if años:
                return int(años[0])
        except:
            continue
    return None



def extraer_categoria_desde_filas_superiores(df_raw, fila_inicio_tabla):
    """Extrae la categoría desde las filas superiores a la tabla"""
    for idx in range(min(15, fila_inicio_tabla)):
        try:
            texto = ''
            for celda in df_raw.iloc[idx]:
                if pd.notna(celda):
                    texto += str(celda).upper() + ' '
            
            # Buscar coincidencia exacta con las categorías
            for categoria, keywords in KEYWORDS_CATEGORIAS.items():
                for kw in keywords:
                    if kw.upper() in texto:
                        print(f"      📂 Categoría detectada: {categoria} (coincidió con '{kw}')")
                        return categoria
        except:
            continue
    return None

def inferir_año_desde_dataframe(df):
    """Infiera el año desde los datos del DataFrame"""
    años_encontrados = set()
    
    # Convertir todas las celdas a string para búsqueda
    try:
        # Buscar en las primeras 1000 filas (por rendimiento)
        sample = df.head(1000).astype(str)
        
        for col in sample.columns:
            for valor in sample[col].head(100):
                if pd.isna(valor):
                    continue
                valor_str = str(valor)
                for patron in PATRONES_AÑO:
                    matches = re.findall(patron, valor_str)
                    for match in matches:
                        if len(match) == 2:  # Año corto (ej. "24")
                            año_completo = 2000 + int(match) if int(match) > 10 else 2000 + int(match)
                            if 2013 <= año_completo <= 2026:
                                años_encontrados.add(año_completo)
                        else:
                            año = int(match)
                            if 2013 <= año <= 2026:
                                años_encontrados.add(año)
        
        # También buscar en nombres de columnas
        for col in df.columns:
            col_str = str(col).lower()
            for patron in PATRONES_AÑO:
                matches = re.findall(patron, col_str)
                for match in matches:
                    if len(match) == 2:
                        año = 2000 + int(match)
                    else:
                        año = int(match)
                    if 2013 <= año <= 2026:
                        años_encontrados.add(año)
    except:
        pass
    
    # Retornar el año más común o None
    if años_encontrados:
        return min(años_encontrados)  # Priorizar el más temprano
    return None

def inferir_categoria_desde_dataframe(df):
    """Infiera la categoría SNIES desde el contenido y columnas"""
    puntajes = defaultdict(int)
    
    # Analizar nombres de columnas
    for col in df.columns:
        col_lower = str(col).upper()
        for categoria, keywords in KEYWORDS_CATEGORIAS.items():
            for kw in keywords:
                kw_upper = kw.upper()
                if kw_upper in col_lower:
                    puntajes[categoria] += 3
    
    # Analizar contenido (primeras 100 filas, primeras 5 columnas)
    try:
        sample = df.head(100).astype(str)
        
        for col in list(sample.columns)[:5]:
            for idx in range(min(20, len(sample))):
                valor = sample[col].iloc[idx]
                if pd.isna(valor) or valor == 'nan':
                    continue
                valor_upper = valor.upper()
                for categoria, keywords in KEYWORDS_CATEGORIAS.items():
                    for kw in keywords:
                        kw_upper = kw.upper()
                        if kw_upper in valor_upper:
                            puntajes[categoria] += 1
                            break
    except Exception:
        pass
    
    if puntajes:
        mejor_categoria = max(puntajes, key=puntajes.get)
        if puntajes[mejor_categoria] >= 1:
            return mejor_categoria
    
    return "indeterminado"

def encontrar_columna_codigo_ies(df):
    """Encuentra columna que contiene códigos de institución"""
    columnas = list(df.columns)
    
    # Patrones específicos para código (excluir nombre)
    patrones_codigo = [
        'código de la institución', 'codigo de la institución',
        'código', 'codigo', 'cod_ies', 'codigo_ies'
    ]
    
    for col in columnas:
        col_str = str(col).lower().strip()
        # No puede contener palabras de nombre
        if any(p in col_str for p in ['institución de educación superior',  'institucion nombre']):
            continue
        for patron in patrones_codigo:
            if patron.lower() in col_str:
                return col
    return None

def encontrar_columna_nombre_ies(df):
    """Encuentra columna que contiene nombres de institución"""
    columnas = list(df.columns)
    
    # Patrones específicos para nombre
    patrones_nombre = [
        'institución de educación superior',
        'nombre institución', 'institucion_nombre', 'nombre_ies'
    ]
    
    for col in columnas:
        col_str = str(col).lower().strip()
        for patron in patrones_nombre:
            if patron.lower() in col_str:
                return col
    
    # Fallback: buscar columna que contenga 'institución' pero no 'código'
    for col in columnas:
        col_str = str(col).lower().strip()
        if ('institución' in col_str or 'institucion' in col_str) and 'código' not in col_str and 'codigo' not in col_str:
            return col
    
    return None

def limpiar_filas_notas(df, col_codigo):
    """Elimina filas que contienen notas, aclaraciones o metadatos al final"""
    
    if col_codigo is None or col_codigo not in df.columns:
        return df
    
    # Palabras que indican que una fila es una nota o metadato
    palabras_nota = [
        'fuente:', 'fecha de corte', 'información suministrada', 'acreditación',
        'para el año', 'a partir de', 'pertenece al sector', 'snies', 'men',
        'nota:', 'fuente', 'corte', 'ministerio', 'educación', 'acreditada',
        'personería jurídica', 'reportaron', 'unidad de medida', 'notas',
        'aclaración', 'importante:', 'observación', 'la información',
        'universidad internacional', 'sector oficial', 'corte 31'
    ]
    
    filas_eliminar = []
    
    for idx in range(len(df)):
        try:
            # Revisar la columna de código
            valor = df[col_codigo].iloc[idx]
            
            # Si es nulo, marcar para eliminar
            if pd.isna(valor):
                filas_eliminar.append(idx)
                continue
            
            valor_str = str(valor).lower().strip()
            
            # Si contiene palabras de nota
            es_nota = False
            for palabra in palabras_nota:
                if palabra in valor_str:
                    es_nota = True
                    break
            
            if es_nota:
                filas_eliminar.append(idx)
                continue
            
            # Si tiene más de 20 caracteres y no es número
            if len(valor_str) > 20 and not valor_str.replace('.', '').isdigit():
                filas_eliminar.append(idx)
                continue
            
            # Si el valor comienza con letras (no es código numérico)
            if valor_str and valor_str[0].isalpha() and not valor_str[:3].isdigit():
                filas_eliminar.append(idx)
                continue
                
        except Exception as e:
            filas_eliminar.append(idx)
    
    # Eliminar filas
    if filas_eliminar:
        df = df.drop(index=filas_eliminar).reset_index(drop=True)
    
    return df
# ============================================================
# CLASE PRINCIPAL DE DIAGNÓSTICO
# ============================================================

class DiagnosticoCalidadSNIES:
    def __init__(self, carpeta_datos):
        self.carpeta = Path(carpeta_datos)
        self.archivos = list(self.carpeta.glob("*.xlsx")) + list(self.carpeta.glob("*.xlsb"))
        self.reporte = {
            "timestamp": datetime.now().isoformat(),
            "resumen": {},
            "archivos_analizados": [],
            "problemas_calidad": [],
            "inconsistencias_columnas": [],
            "codigos_institucion": {},
            "cambios_estructurales": []
        }
    
    def ejecutar(self):

        for idx, archivo in enumerate(self.archivos, 1):
            print(f"[{idx}/{len(self.archivos)}] {archivo.name}")
            self.analizar_archivo(archivo)
        
        self.generar_resumen() 
        self.exportar_reportes()
        return self.reporte
    
    def analizar_archivo(self, ruta):
        """Analiza un archivo individual"""
        df = leer_archivo_seguro(ruta)
        
        if df is None or df.empty:
            self.reporte["problemas_calidad"].append({
                "archivo": ruta.name,
                "tipo": "no_se_pudo_leer",
                "descripcion": "No se pudo leer el archivo o está vacío"
            })
            return
        
        # Limpiar nombres de columnas
        df.columns = [str(col).strip() if pd.notna(col) else f"col_{i}" for i, col in enumerate(df.columns)]
        
        # Usar metadata extraída
        año = df.attrs.get('año', None)
        categoria = df.attrs.get('categoria', None)
        
        if not año:
            año = inferir_año_desde_dataframe(df)
        if not categoria:
            categoria = inferir_categoria_desde_dataframe(df)
        
        # Análisis de columnas
        columnas = list(df.columns)
        columnas_lower = [str(c).lower().strip() for c in columnas]
        
        # Encontrar columnas clave
        col_codigo = encontrar_columna_codigo_ies(df)
        col_nombre = encontrar_columna_nombre_ies(df)


        # LIMPIAR FILAS DE NOTAS
        if col_codigo:
            df = limpiar_filas_notas(df, col_codigo)
        
        
        # Detectar problemas específicos
        problemas_archivo = []
        
        # 1. Verificar columnas críticas
        if not col_codigo:
            problemas_archivo.append("No se encontró columna de código de institución")
        if not col_nombre:
            problemas_archivo.append("No se encontró columna de nombre de institución")
        
        # 2. Detectar nulos excesivos (corregido)
        for col in columnas[:10]:  # Revisar primeras 10 columnas
            try:
                pct_nulos = (df[col].isna().sum() / len(df)) * 100
                if pct_nulos > 50:
                    problemas_archivo.append(f"Columna '{col}' tiene {pct_nulos:.1f}% nulos")
            except:
                pass  # Ignorar columnas problemáticas
        
        # 3. Detectar tipos inconsistentes en códigos
        # 3. Detectar tipos inconsistentes en códigos
        if col_codigo:
            try:
                # Filtrar SOLO códigos válidos
                codigos_validos = df[col_codigo].dropna()
                
                # Convertir a string y limpiar
                codigos_validos = codigos_validos.astype(str)
                
                # Eliminar los que tienen palabras clave de notas
                palabras_nota = ['fuente', 'fecha', 'corte', 'snies', 'ministerio', 'educación', 'acreditación']
                mascara_notas = codigos_validos.str.lower().str.contains('|'.join(palabras_nota), na=False)
                codigos_validos = codigos_validos[~mascara_notas]
                
                # Mantener solo los que son numéricos (con o sin decimales)
                codigos_validos = codigos_validos[codigos_validos.str.match(r'^[\d\.]+$', na=False)]
                
                # Eliminar los que tienen más de 10 dígitos
                codigos_validos = codigos_validos[codigos_validos.str.len() <= 10]
                
                # Eliminar los que tienen puntos decimales .0 (convertir a enteros)
                codigos_validos = codigos_validos.str.replace(r'\.0$', '', regex=True)
                
                # Si después de filtrar no quedan códigos, no reportar problema
                if len(codigos_validos) > 0:
                    # Verificar longitudes
                    longitudes = codigos_validos.str.len().unique()
                    if len(longitudes) > 2:
                        problemas_archivo.append(f"Longitudes inconsistentes en códigos: {sorted(longitudes)}")
            except Exception as e:
                pass
        
        # Guardar información del archivo
        info_archivo = {
            "nombre_archivo": ruta.name,
            "año_inferido": año,
            "categoria_inferida": categoria,
            "num_filas": int(df.shape[0]),
            "num_columnas": int(df.shape[1]),
            "columnas": columnas[:30],  # primeras 30 columnas
            "columna_codigo_ies": col_codigo,
            "columna_nombre_ies": col_nombre,
            "problemas_detectados": problemas_archivo,
            "tipos_de_datos": {str(col): str(df[col].dtype) for col in columnas[:15] if str(col) != 'nan'}
        }
        
        self.reporte["archivos_analizados"].append(info_archivo)
        
        # Registrar problemas
        for problema in problemas_archivo:
            self.reporte["problemas_calidad"].append({
                "archivo": ruta.name,
                "año": año,
                "categoria": categoria,
                "problema": problema
            })
        
        # Guardar códigos de institución
        if col_codigo:
            try:
                # Limpiar y filtrar códigos
                codigos_limpios = df[col_codigo].dropna().astype(str)
                
                # Eliminar notas
                palabras_nota = ['fuente', 'fecha', 'corte', 'snies', 'ministerio', 'educación']
                for palabra in palabras_nota:
                    codigos_limpios = codigos_limpios[~codigos_limpios.str.lower().str.contains(palabra, na=False)]
                
                # Mantener solo numéricos
                codigos_limpios = codigos_limpios[codigos_limpios.str.match(r'^[\d\.]+$', na=False)]
                
                # Limitar longitud
                codigos_limpios = codigos_limpios[codigos_limpios.str.len() <= 10]
                
                # Limpiar .0 al final
                codigos_limpios = codigos_limpios.str.replace(r'\.0$', '', regex=True)
                
                if len(codigos_limpios) > 0:
                    codigos_muestra = codigos_limpios.head(20).tolist()
                    self.reporte["codigos_institucion"][ruta.name] = {
                        "columna": col_codigo,
                        "cantidad_codigos": int(codigos_limpios.nunique()),
                        "muestra": codigos_muestra,
                        "longitudes_tipicas": list(codigos_limpios.str.len().value_counts().head(3).to_dict().keys())
                    }
            except:
                pass
    
    def detectar_inconsistencias_columnas(self):
        """Detecta cambios en nombres de columnas para la misma categoría entre diferentes años"""
        inconsistencias = []
        
        # Agrupar archivos por categoría
        por_categoria = defaultdict(list)
        for archivo in self.reporte["archivos_analizados"]:
            cat = archivo.get("categoria_inferida")
            año = archivo.get("año_inferido")
            if cat and cat != "indeterminado" and año:
                por_categoria[cat].append({
                    "año": año,
                    "archivo": archivo["nombre_archivo"],
                    "columnas": archivo.get("columnas", [])
                })
        
        # Analizar cada categoría
        for categoria, archivos in por_categoria.items():
            archivos_ordenados = sorted(archivos, key=lambda x: x["año"])
            
            for i in range(1, len(archivos_ordenados)):
                prev = archivos_ordenados[i-1]
                curr = archivos_ordenados[i]
                
                cols_prev = set(prev["columnas"])
                cols_curr = set(curr["columnas"])
                
                # Columnas nuevas
                nuevas = cols_curr - cols_prev
                for col in nuevas:
                    inconsistencias.append({
                        "tipo": "columna_nueva",
                        "categoria": categoria,
                        "año": curr["año"],
                        "archivo": curr["archivo"],
                        "columna": col,
                        "descripcion": f"Columna '{col}' aparece en {curr['año']} pero no en {prev['año']}"
                    })
                
                # Columnas eliminadas
                eliminadas = cols_prev - cols_curr
                for col in eliminadas:
                    inconsistencias.append({
                        "tipo": "columna_eliminada",
                        "categoria": categoria,
                        "año": curr["año"],
                        "archivo": curr["archivo"],
                        "columna": col,
                        "descripcion": f"Columna '{col}' existía en {prev['año']} pero desapareció en {curr['año']}"
                    })
                
                # Posibles renombres (columnas con nombres similares)
                for col_prev in cols_prev:
                    for col_curr in cols_curr:
                        if col_prev != col_curr:
                            # Normalizar para comparar
                            col_prev_norm = col_prev.lower().replace(' ', '').replace('_', '').replace('-', '')
                            col_curr_norm = col_curr.lower().replace(' ', '').replace('_', '').replace('-', '')
                            if col_prev_norm == col_curr_norm:
                                inconsistencias.append({
                                    "tipo": "posible_renombre",
                                    "categoria": categoria,
                                    "año": curr["año"],
                                    "archivo": curr["archivo"],
                                    "columna_anterior": col_prev,
                                    "columna_actual": col_curr,
                                    "descripcion": f"Posible renombre: '{col_prev}' → '{col_curr}'"
                                })
        
        return inconsistencias
    
    def detectar_inconsistencias_codigos(self):
        """Detecta inconsistencias en códigos de institución entre archivos"""
        inconsistencias = []
        
        # Agrupar códigos por año y categoría
        codigos_por_año = defaultdict(lambda: defaultdict(set))
        
        for archivo in self.reporte["archivos_analizados"]:
            año = archivo.get("año_inferido")
            categoria = archivo.get("categoria_inferida")
            if not año or not categoria:
                continue
            
            # Obtener códigos reales desde el archivo original (si están guardados)
            if archivo["nombre_archivo"] in self.reporte["codigos_institucion"]:
                info = self.reporte["codigos_institucion"][archivo["nombre_archivo"]]
                for codigo in info.get("muestra", []):
                    if codigo and codigo.isdigit():
                        codigos_por_año[categoria][año].add(codigo)
        
        # Detectar cambios
        for categoria, años_dict in codigos_por_año.items():
            años_ordenados = sorted(años_dict.keys())
            
            for i in range(1, len(años_ordenados)):
                año_prev = años_ordenados[i-1]
                año_curr = años_ordenados[i]
                
                codigos_prev = años_dict[año_prev]
                codigos_curr = años_dict[año_curr]
                
                # Códigos que desaparecieron
                desaparecidos = codigos_prev - codigos_curr
                if desaparecidos:
                    inconsistencias.append({
                        "tipo": "codigos_desaparecidos",
                        "categoria": categoria,
                        "año_anterior": año_prev,
                        "año_actual": año_curr,
                        "codigos": list(desaparecidos)[:10],
                        "descripcion": f"{len(desaparecidos)} códigos dejaron de aparecer"
                    })
                
                # Códigos nuevos
                nuevos = codigos_curr - codigos_prev
                if nuevos:
                    inconsistencias.append({
                        "tipo": "codigos_nuevos",
                        "categoria": categoria,
                        "año_anterior": año_prev,
                        "año_actual": año_curr,
                        "codigos": list(nuevos)[:10],
                        "descripcion": f"{len(nuevos)} códigos nuevos aparecen"
                    })
        
        return inconsistencias
    
    def detectar_cambios_estructura(self):
        """Detecta cambios estructurales entre años (número de filas, columnas, etc.)"""
        cambios = []
        
        # Agrupar por categoría
        por_categoria = defaultdict(list)
        for archivo in self.reporte["archivos_analizados"]:
            cat = archivo.get("categoria_inferida")
            año = archivo.get("año_inferido")
            if cat and cat != "indeterminado" and año:
                por_categoria[cat].append({
                    "año": año,
                    "archivo": archivo["nombre_archivo"],
                    "num_filas": archivo["num_filas"],
                    "num_columnas": archivo["num_columnas"]
                })
        
        # Analizar cada categoría
        for categoria, archivos in por_categoria.items():
            archivos_ordenados = sorted(archivos, key=lambda x: x["año"])
            
            for i in range(1, len(archivos_ordenados)):
                prev = archivos_ordenados[i-1]
                curr = archivos_ordenados[i]
                
                # Cambio significativo en número de filas (>50%)
                if prev["num_filas"] > 0:
                    cambio_filas = abs(curr["num_filas"] - prev["num_filas"]) / prev["num_filas"]
                    if cambio_filas > 0.5:
                        cambios.append({
                            "tipo": "cambio_significativo_filas",
                            "categoria": categoria,
                            "año_anterior": prev["año"],
                            "año_actual": curr["año"],
                            "archivo": curr["archivo"],
                            "valor_anterior": prev["num_filas"],
                            "valor_actual": curr["num_filas"],
                            "descripcion": f"Cambio de {prev['num_filas']} a {curr['num_filas']} filas ({cambio_filas*100:.0f}%)"
                        })
                
                # Cambio en número de columnas
                if prev["num_columnas"] != curr["num_columnas"]:
                    cambios.append({
                        "tipo": "cambio_num_columnas",
                        "categoria": categoria,
                        "año_anterior": prev["año"],
                        "año_actual": curr["año"],
                        "archivo": curr["archivo"],
                        "valor_anterior": prev["num_columnas"],
                        "valor_actual": curr["num_columnas"],
                        "descripcion": f"Cambio de {prev['num_columnas']} a {curr['num_columnas']} columnas"
                    })
        
        return cambios

    def generar_resumen(self):
        """Genera resumen estadístico"""
        archivos_con_problemas = len([a for a in self.reporte["archivos_analizados"] if a["problemas_detectados"]])
        
        # Agrupar por año inferido
        por_año = defaultdict(int)
        por_categoria = defaultdict(int)
        
        for a in self.reporte["archivos_analizados"]:
            if a["año_inferido"]:
                por_año[a["año_inferido"]] += 1
            if a["categoria_inferida"]:
                por_categoria[a["categoria_inferida"]] += 1
        
        self.reporte["resumen"] = {
            "total_archivos": len(self.archivos),
            "archivos_leidos": len(self.reporte["archivos_analizados"]),
            "archivos_con_problemas": archivos_con_problemas,
            "total_problemas": len(self.reporte["problemas_calidad"]),
            "distribucion_por_año": dict(por_año),
            "distribucion_por_categoria": dict(por_categoria),
            "archivos_sin_año": len([a for a in self.reporte["archivos_analizados"] if not a["año_inferido"]]),
            "archivos_sin_categoria": len([a for a in self.reporte["archivos_analizados"] if a["categoria_inferida"] == "indeterminado"])
        }
        '''
        print("\n" + "="*70)
        print("📊 RESUMEN DEL DIAGNÓSTICO")
        print("="*70)
        print(f"✅ Archivos leídos: {self.reporte['resumen']['archivos_leidos']}/{self.reporte['resumen']['total_archivos']}")
        print(f"⚠️ Archivos con problemas: {self.reporte['resumen']['archivos_con_problemas']}")
        print(f"🔴 Total problemas detectados: {self.reporte['resumen']['total_problemas']}")
        print(f"\n📅 Distribución por año inferido:")
        for año, count in sorted(por_año.items()):
            print(f"   {año}: {count} archivo(s)")
        print(f"\n📂 Distribución por categoría:")
        '''
        for cat, count in por_categoria.items():
            print(f"   {cat}: {count} archivo(s)")
    def generar_reporte_inconsistencias(self):
        """Genera el reporte completo de inconsistencias"""
        
        inconsistencias = {
            "inconsistencias_columnas": self.detectar_inconsistencias_columnas(),
            "inconsistencias_codigos": self.detectar_inconsistencias_codigos(),
            "cambios_estructura": self.detectar_cambios_estructura(),
            "resumen": {}
        }
        
        inconsistencias["resumen"] = {
            "total_inconsistencias_columnas": len(inconsistencias["inconsistencias_columnas"]),
            "total_inconsistencias_codigos": len(inconsistencias["inconsistencias_codigos"]),
            "total_cambios_estructura": len(inconsistencias["cambios_estructura"]),
            "categorias_afectadas": list(set([
                c.get("categoria") for c in inconsistencias["inconsistencias_columnas"] if c.get("categoria")
            ]))
        }
        
        return inconsistencias

    def exportar_reportes(self):
        """Exporta reportes a archivos"""
        REPORTE_SALIDA.mkdir(exist_ok=True)
        
        # ... (código existente) ...
        
        # Reporte de inconsistencias
        inconsistencias = self.generar_reporte_inconsistencias()
        
        # Guardar JSON completo
        with open(REPORTE_SALIDA / "inconsistencias_completas.json", 'w', encoding='utf-8') as f:
            json.dump(inconsistencias, f, indent=2, ensure_ascii=False, default=str)
        
        # Exportar como CSV cada tipo
        if inconsistencias["inconsistencias_columnas"]:
            df_cols = pd.DataFrame(inconsistencias["inconsistencias_columnas"])
            df_cols.to_csv(REPORTE_SALIDA / "inconsistencias_columnas.csv", index=False, encoding='utf-8-sig')
        
        if inconsistencias["inconsistencias_codigos"]:
            df_cods = pd.DataFrame(inconsistencias["inconsistencias_codigos"])
            df_cods.to_csv(REPORTE_SALIDA / "inconsistencias_codigos.csv", index=False, encoding='utf-8-sig')
        
        if inconsistencias["cambios_estructura"]:
            df_est = pd.DataFrame(inconsistencias["cambios_estructura"])
            df_est.to_csv(REPORTE_SALIDA / "cambios_estructura.csv", index=False, encoding='utf-8-sig')
        
        print(f"\nReportes exportados a: {REPORTE_SALIDA}")

# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    # Configurar ruta
    import sys
    
    if len(sys.argv) > 1:
        CARPETA_DATOS = Path(sys.argv[1])
    
    if not CARPETA_DATOS.exists():
        print(f"La carpeta {CARPETA_DATOS} no existe.")
        ruta_usuario = input("Ingresa la ruta completa de tu carpeta con archivos SNIES: ")
        CARPETA_DATOS = Path(ruta_usuario)
        if not CARPETA_DATOS.exists():
            sys.exit(1)
    
    # Ejecutar
    diagnostico = DiagnosticoCalidadSNIES(CARPETA_DATOS)
    reporte = diagnostico.ejecutar()
    
