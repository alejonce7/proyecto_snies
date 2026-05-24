"""
Exploración profunda de variables disponibles en la BD SNIES
para la Fase 1: Identificación de stakeholders y preguntas de negocio
"""
import duckdb

conn = duckdb.connect('data/dataset/snies.duckdb', read_only=True)

# 1. Categorias disponibles
print("=" * 70)
print("1. CATEGORIAS DISPONIBLES")
print("=" * 70)
print(conn.execute("SELECT * FROM dim_categoria ORDER BY id_categoria").df().to_string())

# 2. Hechos por año y categoria
print("\n" + "=" * 70)
print("2. HECHOS POR AÑO Y CATEGORÍA (pivot)")
print("=" * 70)
df = conn.execute("""
    SELECT año, 
           id_categoria,
           COUNT(*) as registros,
           SUM(valor_numerico) as total
    FROM hecho_snies 
    GROUP BY año, id_categoria
    ORDER BY año, id_categoria
""").df()
pivot = df.pivot_table(index='año', columns='id_categoria', values='total', fill_value=0)
pivot.columns = ['inscritos','admitidos','matriculados','primer_curso','graduados','docentes','administrativos']
print(pivot.to_string())

# 3. Departamentos con datos
print("\n" + "=" * 70)
print("3. DEPARTAMENTOS CON MÁS DATOS")
print("=" * 70)
print(conn.execute("""
    SELECT u.nombre_departamento, COUNT(*) as registros, 
           COUNT(DISTINCT h.codigo_ies) as num_ies
    FROM hecho_snies h
    LEFT JOIN dim_ubicacion u ON h.id_departamento = u.id_ubicacion
    WHERE u.nombre_departamento IS NOT NULL
    GROUP BY u.nombre_departamento
    ORDER BY registros DESC
    LIMIT 15
""").df().to_string())

# 4. Sectores de IES
print("\n" + "=" * 70)
print("4. SECTORES DE IES")
print("=" * 70)
print(conn.execute("""
    SELECT sector, COUNT(*) as num_ies
    FROM dim_ies
    WHERE sector IS NOT NULL AND sector != 'None' AND sector != 'nan'
    GROUP BY sector
""").df().to_string())

# 5. Carácter de IES
print("\n" + "=" * 70)
print("5. CARÁCTER DE IES")
print("=" * 70)
print(conn.execute("""
    SELECT caracter, COUNT(*) as num_ies
    FROM dim_ies
    WHERE caracter IS NOT NULL AND caracter != 'None' AND caracter != 'nan'
    GROUP BY caracter
    ORDER BY num_ies DESC
""").df().to_string())

# 6. Tendencias clave: evolución inscritos/matriculados/graduados
print("\n" + "=" * 70)
print("6. EVOLUCIÓN ANUAL AGREGADA (categorías principales)")
print("=" * 70)
print(conn.execute("""
    SELECT h.año,
           SUM(CASE WHEN h.id_categoria = 1 THEN h.valor_numerico END) as inscritos,
           SUM(CASE WHEN h.id_categoria = 2 THEN h.valor_numerico END) as admitidos,
           SUM(CASE WHEN h.id_categoria = 3 THEN h.valor_numerico END) as matriculados,
           SUM(CASE WHEN h.id_categoria = 5 THEN h.valor_numerico END) as graduados,
           SUM(CASE WHEN h.id_categoria = 6 THEN h.valor_numerico END) as docentes
    FROM hecho_snies h
    GROUP BY h.año
    ORDER BY h.año
""").df().to_string())

# 7. Top IES por matriculados (últimos datos)
print("\n" + "=" * 70)
print("7. TOP 15 IES POR MATRICULADOS (2024)")
print("=" * 70)
print(conn.execute("""
    SELECT i.nombre_ies, i.sector, i.caracter,
           SUM(h.valor_numerico) as total_matriculados
    FROM hecho_snies h
    JOIN dim_ies i ON h.codigo_ies = i.codigo_ies
    WHERE h.id_categoria = 3 AND h.año = 2024
    GROUP BY i.nombre_ies, i.sector, i.caracter
    ORDER BY total_matriculados DESC
    LIMIT 15
""").df().to_string())

# 8. Tasa de conversión inscrito -> matriculado por año
print("\n" + "=" * 70)
print("8. TASA DE CONVERSIÓN INSCRITO -> MATRICULADO POR AÑO")
print("=" * 70)
print(conn.execute("""
    WITH datos AS (
        SELECT año,
               SUM(CASE WHEN id_categoria = 1 THEN valor_numerico END) as inscritos,
               SUM(CASE WHEN id_categoria = 3 THEN valor_numerico END) as matriculados,
               SUM(CASE WHEN id_categoria = 5 THEN valor_numerico END) as graduados
        FROM hecho_snies
        GROUP BY año
    )
    SELECT año, inscritos, matriculados, graduados,
           ROUND(matriculados * 100.0 / NULLIF(inscritos, 0), 1) as pct_matricula,
           ROUND(graduados * 100.0 / NULLIF(matriculados, 0), 1) as pct_graduacion
    FROM datos
    WHERE inscritos > 0
    ORDER BY año
""").df().to_string())

# 9. Datos disponibles por programa
print("\n" + "=" * 70)
print("9. PROGRAMAS: niveles académicos disponibles")
print("=" * 70)
print(conn.execute("""
    SELECT nivel_academico, COUNT(*) as num_programas
    FROM dim_programa
    WHERE nivel_academico IS NOT NULL AND nivel_academico != 'None'
    GROUP BY nivel_academico
    ORDER BY num_programas DESC
    LIMIT 10
""").df().to_string())

# 10. Disparidades regionales
print("\n" + "=" * 70)
print("10. DISPARIDADES REGIONALES - Matriculados 2024 por depto")
print("=" * 70)
print(conn.execute("""
    SELECT u.nombre_departamento,
           SUM(h.valor_numerico) as matriculados_2024,
           COUNT(DISTINCT h.codigo_ies) as num_ies
    FROM hecho_snies h
    JOIN dim_ubicacion u ON h.id_departamento = u.id_ubicacion
    WHERE h.id_categoria = 3 AND h.año = 2024
      AND u.nombre_departamento IS NOT NULL
    GROUP BY u.nombre_departamento
    ORDER BY matriculados_2024 DESC
    LIMIT 20
""").df().to_string())

# 11. Impacto COVID: comparar 2019 vs 2020 vs 2021
print("\n" + "=" * 70)
print("11. IMPACTO COVID: 2019 vs 2020 vs 2021")
print("=" * 70)
print(conn.execute("""
    SELECT año, id_categoria,
           SUM(valor_numerico) as total
    FROM hecho_snies
    WHERE año IN (2019, 2020, 2021)
    GROUP BY año, id_categoria
    ORDER BY id_categoria, año
""").df().to_string())

# 12. Ratio docente/estudiante por IES (2024)
print("\n" + "=" * 70)
print("12. RATIO DOCENTE/MATRICULADO POR IES (2024, top/bottom)")
print("=" * 70)
print(conn.execute("""
    WITH ratios AS (
        SELECT h.codigo_ies, i.nombre_ies,
               SUM(CASE WHEN h.id_categoria = 6 THEN h.valor_numerico END) as docentes,
               SUM(CASE WHEN h.id_categoria = 3 THEN h.valor_numerico END) as matriculados
        FROM hecho_snies h
        JOIN dim_ies i ON h.codigo_ies = i.codigo_ies
        WHERE h.año = 2024
        GROUP BY h.codigo_ies, i.nombre_ies
        HAVING docentes > 0 AND matriculados > 0
    )
    SELECT nombre_ies, docentes, matriculados,
           ROUND(matriculados * 1.0 / docentes, 1) as estudiantes_por_docente
    FROM ratios
    ORDER BY estudiantes_por_docente DESC
    LIMIT 10
""").df().to_string())

conn.close()
print("\n\nEXPLORACION COMPLETADA")
