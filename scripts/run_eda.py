"""
=============================================================================
FASE 2: ANÁLISIS DESCRIPTIVO Y EXPLORACIÓN DE DATOS (EDA)
Proyecto SNIES — Minería de Datos 2025 · Persona 2
=============================================================================
Genera:
  - Visualizaciones en reports/eda_visualizaciones/
  - Dataset de features en data/dataset/features_ml.csv
  - Resumen estadístico en reports/eda_resumen.txt
=============================================================================
"""

import duckdb
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ── Configuración ──────────────────────────────────────────────────────────
DB_PATH = Path("./data/dataset/snies.duckdb")
OUT_DIR = Path("./reports/eda_visualizaciones")
OUT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    'figure.figsize': (14, 7),
    'figure.dpi': 150,
    'font.family': 'sans-serif',
    'font.size': 11,
    'axes.titlesize': 14,
    'axes.titleweight': 'bold',
    'axes.labelsize': 12,
    'axes.grid': True,
    'grid.alpha': 0.3,
    'legend.fontsize': 10,
    'figure.facecolor': 'white',
})

COLORS = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#3B1F2B', '#44BBA4', '#E94F37']
CATEGORY_NAMES = {1:'Inscritos', 2:'Admitidos', 3:'Matriculados',
                  4:'Primer Curso', 5:'Graduados', 6:'Docentes', 7:'Administrativos'}

conn = duckdb.connect(str(DB_PATH), read_only=True)
resumen_lines = []

def log(msg):
    print(msg)
    resumen_lines.append(msg)

log("=" * 70)
log("FASE 2 — EDA SNIES · Inicio del análisis")
log("=" * 70)

# ═══════════════════════════════════════════════════════════════════════════
# SECCIÓN 1: SERIES DE TIEMPO (2013-2024)
# ═══════════════════════════════════════════════════════════════════════════
log("\n▶ SECCIÓN 1: SERIES DE TIEMPO")

# 1.1 Evolución nacional por categoría
df_evol = conn.execute("""
    SELECT año, id_categoria, SUM(valor_numerico) as total
    FROM hecho_snies
    WHERE año BETWEEN 2013 AND 2024
    GROUP BY año, id_categoria
    ORDER BY año, id_categoria
""").df()

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('Evolución del Sistema de Educación Superior en Colombia (2013-2024)',
             fontsize=16, fontweight='bold', y=0.98)

# Inscritos, Admitidos, Matriculados
ax = axes[0, 0]
for idx, cat_id in enumerate([1, 2, 3]):
    data = df_evol[df_evol['id_categoria'] == cat_id]
    ax.plot(data['año'], data['total'] / 1e6, 'o-', color=COLORS[idx],
            label=CATEGORY_NAMES[cat_id], linewidth=2, markersize=6)
ax.set_title('Inscritos, Admitidos y Matriculados')
ax.set_ylabel('Millones de personas')
ax.legend()
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.1fM'))
ax.axvspan(2020, 2021, alpha=0.1, color='red', label='COVID-19')

# Graduados
ax = axes[0, 1]
data = df_evol[df_evol['id_categoria'] == 5]
ax.plot(data['año'], data['total'] / 1e3, 'o-', color=COLORS[3], linewidth=2, markersize=6)
ax.set_title('Graduados')
ax.set_ylabel('Miles de personas')
ax.axvspan(2020, 2021, alpha=0.1, color='red')
# Nota: 2017 tiene dato anómalo, filtrar
data_clean = data[data['año'] >= 2018]
ax2 = ax.twinx()
ax2.bar(data_clean['año'], data_clean['total'] / 1e3, alpha=0.2, color=COLORS[3])
ax2.set_ylabel('')
ax2.set_yticks([])

# Docentes
ax = axes[1, 0]
data = df_evol[df_evol['id_categoria'] == 6]
ax.plot(data['año'], data['total'] / 1e3, 's-', color=COLORS[5], linewidth=2, markersize=6)
ax.set_title('Docentes en IES')
ax.set_ylabel('Miles de docentes')
ax.set_xlabel('Año')
ax.axvspan(2020, 2021, alpha=0.1, color='red')

# Variación porcentual interanual de matriculados
ax = axes[1, 1]
mat = df_evol[df_evol['id_categoria'] == 3].copy()
mat['variacion'] = mat['total'].pct_change() * 100
ax.bar(mat['año'], mat['variacion'], color=[COLORS[3] if v < 0 else COLORS[0] for v in mat['variacion']])
ax.set_title('Variación % Interanual de Matriculados')
ax.set_ylabel('Variación (%)')
ax.set_xlabel('Año')
ax.axhline(y=0, color='black', linewidth=0.8)

plt.tight_layout()
plt.savefig(OUT_DIR / '01_series_tiempo_nacional.png', bbox_inches='tight')
plt.close()
log("  ✅ 01_series_tiempo_nacional.png")

# Estadísticas clave
mat_2013 = df_evol[(df_evol['id_categoria']==3)&(df_evol['año']==2013)]['total'].values[0]
mat_2024 = df_evol[(df_evol['id_categoria']==3)&(df_evol['año']==2024)]['total'].values[0]
log(f"  📊 Matriculados 2013: {mat_2013:,.0f} → 2024: {mat_2024:,.0f} (crecimiento: {(mat_2024/mat_2013-1)*100:.1f}%)")

# 1.2 Evolución por departamento (Top 6)
df_depto = conn.execute("""
    SELECT h.año, u.nombre_departamento as depto,
           SUM(h.valor_numerico) as matriculados
    FROM hecho_snies h
    JOIN dim_ubicacion u ON h.id_departamento = u.id_ubicacion
    WHERE h.id_categoria = 3 AND h.año BETWEEN 2013 AND 2024
      AND u.nombre_departamento IS NOT NULL
    GROUP BY h.año, u.nombre_departamento
    ORDER BY h.año
""").df()

top_deptos = df_depto.groupby('depto')['matriculados'].sum().nlargest(6).index.tolist()

fig, ax = plt.subplots(figsize=(14, 7))
for i, depto in enumerate(top_deptos):
    data = df_depto[df_depto['depto'] == depto]
    ax.plot(data['año'], data['matriculados'] / 1e3, 'o-', color=COLORS[i % len(COLORS)],
            label=depto, linewidth=2, markersize=5)
ax.set_title('Evolución de Matriculados por Departamento — Top 6 (2013-2024)')
ax.set_ylabel('Miles de matriculados')
ax.set_xlabel('Año')
ax.legend(loc='upper left')
ax.axvspan(2020, 2021, alpha=0.08, color='red')
plt.tight_layout()
plt.savefig(OUT_DIR / '02_series_por_departamento.png', bbox_inches='tight')
plt.close()
log("  ✅ 02_series_por_departamento.png")

# 1.3 Series históricas completas 2000-2024
df_hist = conn.execute("""
    SELECT año,
           SUM(CASE WHEN id_categoria=1 THEN valor_numerico END) as inscritos,
           SUM(CASE WHEN id_categoria=3 THEN valor_numerico END) as matriculados,
           SUM(CASE WHEN id_categoria=5 THEN valor_numerico END) as graduados,
           SUM(CASE WHEN id_categoria=6 THEN valor_numerico END) as docentes
    FROM hecho_snies GROUP BY año ORDER BY año
""").df()

fig, ax = plt.subplots(figsize=(16, 7))
ax.fill_between(df_hist['año'], df_hist['matriculados']/1e6, alpha=0.3, color=COLORS[0])
ax.plot(df_hist['año'], df_hist['matriculados']/1e6, 'o-', color=COLORS[0], label='Matriculados', linewidth=2.5)
ax.plot(df_hist['año'], df_hist['inscritos']/1e6, 's--', color=COLORS[1], label='Inscritos', linewidth=1.5)
ax.set_title('Evolución Histórica de la Educación Superior en Colombia (2000-2024)')
ax.set_ylabel('Millones de personas')
ax.set_xlabel('Año')
ax.legend(fontsize=12)
ax.axvspan(2020, 2021, alpha=0.1, color='red')
ax.annotate('COVID-19', xy=(2020, df_hist[df_hist['año']==2020]['matriculados'].values[0]/1e6),
            xytext=(2017, 4.8), fontsize=11, color='red',
            arrowprops=dict(arrowstyle='->', color='red'))
plt.tight_layout()
plt.savefig(OUT_DIR / '03_serie_historica_completa.png', bbox_inches='tight')
plt.close()
log("  ✅ 03_serie_historica_completa.png")


# ═══════════════════════════════════════════════════════════════════════════
# SECCIÓN 2: DISTRIBUCIONES Y CORRELACIONES
# ═══════════════════════════════════════════════════════════════════════════
log("\n▶ SECCIÓN 2: DISTRIBUCIONES Y CORRELACIONES")

# 2.1 Distribución de matriculados por IES (2024) — Histograma + Box
df_ies_2024 = conn.execute("""
    SELECT h.codigo_ies, i.nombre_ies, i.sector, i.caracter,
           SUM(h.valor_numerico) as matriculados
    FROM hecho_snies h
    JOIN dim_ies i ON h.codigo_ies = i.codigo_ies
    WHERE h.id_categoria = 3 AND h.año = 2024
    GROUP BY h.codigo_ies, i.nombre_ies, i.sector, i.caracter
    HAVING matriculados > 0
    ORDER BY matriculados DESC
""").df()

fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# Histograma
ax = axes[0]
ax.hist(df_ies_2024['matriculados'], bins=50, color=COLORS[0], edgecolor='white', alpha=0.8)
ax.set_title('Distribución de Matriculados por IES (2024)')
ax.set_xlabel('Total matriculados')
ax.set_ylabel('Número de IES')
ax.axvline(df_ies_2024['matriculados'].median(), color='red', linestyle='--',
           label=f'Mediana: {df_ies_2024["matriculados"].median():,.0f}')
ax.axvline(df_ies_2024['matriculados'].mean(), color='orange', linestyle='--',
           label=f'Media: {df_ies_2024["matriculados"].mean():,.0f}')
ax.legend()

# Top 15 IES
ax = axes[1]
top15 = df_ies_2024.head(15).iloc[::-1]
bars = ax.barh(range(len(top15)), top15['matriculados'] / 1e3, color=COLORS[0], alpha=0.85)
ax.set_yticks(range(len(top15)))
ax.set_yticklabels([n[:40] for n in top15['nombre_ies']], fontsize=8)
ax.set_title('Top 15 IES por Matriculados (2024)')
ax.set_xlabel('Miles de matriculados')

plt.tight_layout()
plt.savefig(OUT_DIR / '04_distribucion_matriculados_ies.png', bbox_inches='tight')
plt.close()
log("  ✅ 04_distribucion_matriculados_ies.png")

stats = df_ies_2024['matriculados'].describe()
log(f"  📊 IES con matrícula 2024: {len(df_ies_2024)}")
log(f"     Media: {stats['mean']:,.0f} | Mediana: {stats['50%']:,.0f} | Desv. Est.: {stats['std']:,.0f}")
log(f"     Min: {stats['min']:,.0f} | Max: {stats['max']:,.0f}")

# 2.2 Disparidades regionales — Matriculados por departamento 2024
df_reg = conn.execute("""
    SELECT u.nombre_departamento as depto,
           SUM(h.valor_numerico) as matriculados,
           COUNT(DISTINCT h.codigo_ies) as num_ies
    FROM hecho_snies h
    JOIN dim_ubicacion u ON h.id_departamento = u.id_ubicacion
    WHERE h.id_categoria = 3 AND h.año = 2024
      AND u.nombre_departamento IS NOT NULL
    GROUP BY u.nombre_departamento
    ORDER BY matriculados DESC
""").df()

fig, axes = plt.subplots(1, 2, figsize=(16, 8))

# Barras horizontales
ax = axes[0]
data_plot = df_reg.head(20).iloc[::-1]
colors_bar = [COLORS[0] if v > df_reg['matriculados'].median() else COLORS[3] for v in data_plot['matriculados']]
ax.barh(range(len(data_plot)), data_plot['matriculados'] / 1e3, color=colors_bar[::-1], alpha=0.85)
ax.set_yticks(range(len(data_plot)))
ax.set_yticklabels(data_plot['depto'], fontsize=9)
ax.set_title('Matriculados por Departamento (2024)')
ax.set_xlabel('Miles de matriculados')
ax.axvline(df_reg['matriculados'].median() / 1e3, color='gray', linestyle=':', label='Mediana')
ax.legend()

# Scatter: IES vs Matriculados
ax = axes[1]
ax.scatter(df_reg['num_ies'], df_reg['matriculados'] / 1e3, c=COLORS[1], s=80, alpha=0.7, edgecolors='white')
for _, row in df_reg.head(5).iterrows():
    ax.annotate(row['depto'], (row['num_ies'], row['matriculados']/1e3),
                fontsize=8, ha='left', va='bottom')
ax.set_title('Relación: Número de IES vs. Matriculados por Departamento')
ax.set_xlabel('Número de IES')
ax.set_ylabel('Miles de matriculados')

plt.tight_layout()
plt.savefig(OUT_DIR / '05_disparidades_regionales.png', bbox_inches='tight')
plt.close()
log("  ✅ 05_disparidades_regionales.png")
log(f"  📊 Top 3 deptos: {', '.join(df_reg.head(3)['depto'].tolist())}")
log(f"     Concentración Bogotá: {df_reg.iloc[0]['matriculados']/df_reg['matriculados'].sum()*100:.1f}%")

# 2.3 Relación Matrícula vs Graduación por IES (2018-2024)
df_mat_grad = conn.execute("""
    SELECT h.codigo_ies, i.nombre_ies,
           SUM(CASE WHEN h.id_categoria = 3 THEN h.valor_numerico END) as matriculados,
           SUM(CASE WHEN h.id_categoria = 5 THEN h.valor_numerico END) as graduados
    FROM hecho_snies h
    JOIN dim_ies i ON h.codigo_ies = i.codigo_ies
    WHERE h.año BETWEEN 2018 AND 2024
    GROUP BY h.codigo_ies, i.nombre_ies
    HAVING matriculados > 0 AND graduados > 0
""").df()
df_mat_grad['tasa_grad'] = df_mat_grad['graduados'] / df_mat_grad['matriculados'] * 100

fig, axes = plt.subplots(1, 2, figsize=(16, 7))

ax = axes[0]
ax.scatter(df_mat_grad['matriculados']/1e3, df_mat_grad['tasa_grad'],
           c=COLORS[0], s=40, alpha=0.5, edgecolors='white')
ax.set_title('Relación: Tamaño de IES vs. Tasa de Graduación (2018-2024 acum.)')
ax.set_xlabel('Matriculados acumulados (miles)')
ax.set_ylabel('Tasa de graduación (%)')
ax.set_xlim(0, df_mat_grad['matriculados'].quantile(0.95)/1e3)
ax.set_ylim(0, min(df_mat_grad['tasa_grad'].quantile(0.95), 50))
ax.axhline(df_mat_grad['tasa_grad'].median(), color='red', linestyle='--',
           label=f'Mediana: {df_mat_grad["tasa_grad"].median():.1f}%')
ax.legend()

ax = axes[1]
ax.hist(df_mat_grad['tasa_grad'], bins=40, color=COLORS[1], edgecolor='white', alpha=0.8,
        range=(0, df_mat_grad['tasa_grad'].quantile(0.95)))
ax.set_title('Distribución de Tasa de Graduación por IES')
ax.set_xlabel('Tasa de graduación (%)')
ax.set_ylabel('Número de IES')
ax.axvline(df_mat_grad['tasa_grad'].median(), color='red', linestyle='--')

plt.tight_layout()
plt.savefig(OUT_DIR / '06_matricula_vs_graduacion.png', bbox_inches='tight')
plt.close()
log("  ✅ 06_matricula_vs_graduacion.png")

# 2.4 Estadísticas descriptivas completas
log("\n  📋 ESTADÍSTICAS DESCRIPTIVAS COMPLETAS (2024):")
df_stats = conn.execute("""
    SELECT c.nombre as categoria,
           COUNT(*) as registros,
           SUM(h.valor_numerico) as total,
           AVG(h.valor_numerico) as promedio,
           MEDIAN(h.valor_numerico) as mediana,
           STDDEV(h.valor_numerico) as desv_std,
           MIN(h.valor_numerico) as minimo,
           MAX(h.valor_numerico) as maximo
    FROM hecho_snies h
    JOIN dim_categoria c ON h.id_categoria = c.id_categoria
    WHERE h.año = 2024
    GROUP BY c.nombre
    ORDER BY total DESC
""").df()
log(df_stats.to_string(index=False))

# 2.5 Heatmap de correlaciones
df_corr_data = conn.execute("""
    SELECT h.codigo_ies,
           SUM(CASE WHEN h.id_categoria=1 THEN h.valor_numerico END) as inscritos,
           SUM(CASE WHEN h.id_categoria=2 THEN h.valor_numerico END) as admitidos,
           SUM(CASE WHEN h.id_categoria=3 THEN h.valor_numerico END) as matriculados,
           SUM(CASE WHEN h.id_categoria=4 THEN h.valor_numerico END) as primer_curso,
           SUM(CASE WHEN h.id_categoria=5 THEN h.valor_numerico END) as graduados,
           SUM(CASE WHEN h.id_categoria=6 THEN h.valor_numerico END) as docentes
    FROM hecho_snies h
    WHERE h.año BETWEEN 2018 AND 2024
    GROUP BY h.codigo_ies
    HAVING inscritos > 0 AND matriculados > 0
""").df()

fig, ax = plt.subplots(figsize=(10, 8))
corr = df_corr_data.drop(columns=['codigo_ies']).corr()
mask = np.triu(np.ones_like(corr, dtype=bool))
sns.heatmap(corr, mask=mask, annot=True, fmt='.2f', cmap='RdBu_r', center=0,
            square=True, ax=ax, linewidths=1, vmin=-1, vmax=1)
ax.set_title('Matriz de Correlación entre Categorías SNIES (2018-2024, por IES)')
plt.tight_layout()
plt.savefig(OUT_DIR / '07_correlaciones.png', bbox_inches='tight')
plt.close()
log("  ✅ 07_correlaciones.png")


# ═══════════════════════════════════════════════════════════════════════════
# SECCIÓN 3: DETECCIÓN DE TENDENCIAS Y ANOMALÍAS
# ═══════════════════════════════════════════════════════════════════════════
log("\n▶ SECCIÓN 3: TENDENCIAS Y ANOMALÍAS")

# 3.1 Impacto COVID — Variación 2019→2020 por categoría
df_covid = conn.execute("""
    SELECT id_categoria, año, SUM(valor_numerico) as total
    FROM hecho_snies
    WHERE año IN (2019, 2020, 2021, 2022)
    GROUP BY id_categoria, año
    ORDER BY id_categoria, año
""").df()

covid_pivot = df_covid.pivot(index='id_categoria', columns='año', values='total')
covid_pivot['caida_2020'] = (covid_pivot[2020] - covid_pivot[2019]) / covid_pivot[2019] * 100
covid_pivot['recup_2021'] = (covid_pivot[2021] - covid_pivot[2019]) / covid_pivot[2019] * 100
covid_pivot['recup_2022'] = (covid_pivot[2022] - covid_pivot[2019]) / covid_pivot[2019] * 100
covid_pivot['categoria'] = covid_pivot.index.map(CATEGORY_NAMES)

fig, ax = plt.subplots(figsize=(14, 7))
x = range(len(covid_pivot))
width = 0.25
bars1 = ax.bar([i - width for i in x], covid_pivot['caida_2020'], width,
               label='2020 vs 2019', color=COLORS[3], alpha=0.85)
bars2 = ax.bar(x, covid_pivot['recup_2021'], width,
               label='2021 vs 2019', color=COLORS[2], alpha=0.85)
bars3 = ax.bar([i + width for i in x], covid_pivot['recup_2022'], width,
               label='2022 vs 2019', color=COLORS[0], alpha=0.85)
ax.set_xticks(x)
ax.set_xticklabels(covid_pivot['categoria'], fontsize=10)
ax.set_ylabel('Variación respecto a 2019 (%)')
ax.set_title('Impacto COVID-19 en la Educación Superior — Variación respecto a 2019')
ax.axhline(y=0, color='black', linewidth=0.8)
ax.legend()

# Agregar etiquetas de valor
for bars in [bars1, bars2, bars3]:
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.1f}%', xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3 if height >= 0 else -12), textcoords="offset points",
                    ha='center', va='bottom' if height >= 0 else 'top', fontsize=8)

plt.tight_layout()
plt.savefig(OUT_DIR / '08_impacto_covid.png', bbox_inches='tight')
plt.close()
log("  ✅ 08_impacto_covid.png")
log(f"  📊 COVID — Caída matriculados 2020: {covid_pivot.loc[3, 'caida_2020']:.1f}%")
log(f"     COVID — Caída graduados 2020: {covid_pivot.loc[5, 'caida_2020']:.1f}%")
log(f"     COVID — Caída docentes 2020: {covid_pivot.loc[6, 'caida_2020']:.1f}%")

# 3.2 IES con mayor crecimiento y decrecimiento (2018-2024)
df_crec = conn.execute("""
    WITH por_año AS (
        SELECT codigo_ies, año, SUM(valor_numerico) as matriculados
        FROM hecho_snies
        WHERE id_categoria = 3 AND año IN (2018, 2024)
        GROUP BY codigo_ies, año
    ),
    pivoteado AS (
        SELECT codigo_ies,
               MAX(CASE WHEN año=2018 THEN matriculados END) as mat_2018,
               MAX(CASE WHEN año=2024 THEN matriculados END) as mat_2024
        FROM por_año
        GROUP BY codigo_ies
        HAVING mat_2018 > 100 AND mat_2024 > 0
    )
    SELECT p.codigo_ies, i.nombre_ies,
           p.mat_2018, p.mat_2024,
           ROUND((p.mat_2024 - p.mat_2018) * 100.0 / p.mat_2018, 1) as variacion_pct
    FROM pivoteado p
    JOIN dim_ies i ON p.codigo_ies = i.codigo_ies
    ORDER BY variacion_pct DESC
""").df()

fig, axes = plt.subplots(1, 2, figsize=(16, 8))

# Top crecimiento
ax = axes[0]
top_crec = df_crec.head(10).iloc[::-1]
colors_g = [COLORS[0]] * len(top_crec)
ax.barh(range(len(top_crec)), top_crec['variacion_pct'], color=colors_g, alpha=0.85)
ax.set_yticks(range(len(top_crec)))
ax.set_yticklabels([n[:35] for n in top_crec['nombre_ies']], fontsize=8)
ax.set_title('Top 10 IES — Mayor Crecimiento 2018→2024')
ax.set_xlabel('Variación (%)')

# Top decrecimiento
ax = axes[1]
top_dec = df_crec.tail(10)
ax.barh(range(len(top_dec)), top_dec['variacion_pct'], color=COLORS[3], alpha=0.85)
ax.set_yticks(range(len(top_dec)))
ax.set_yticklabels([n[:35] for n in top_dec['nombre_ies']], fontsize=8)
ax.set_title('Top 10 IES — Mayor Decrecimiento 2018→2024')
ax.set_xlabel('Variación (%)')

plt.tight_layout()
plt.savefig(OUT_DIR / '09_crecimiento_decrecimiento_ies.png', bbox_inches='tight')
plt.close()
log("  ✅ 09_crecimiento_decrecimiento_ies.png")

# 3.3 Evolución COVID por departamento
df_covid_dep = conn.execute("""
    SELECT u.nombre_departamento as depto, h.año,
           SUM(h.valor_numerico) as matriculados
    FROM hecho_snies h
    JOIN dim_ubicacion u ON h.id_departamento = u.id_ubicacion
    WHERE h.id_categoria = 3 AND h.año IN (2019, 2020, 2021)
      AND u.nombre_departamento IS NOT NULL
    GROUP BY u.nombre_departamento, h.año
""").df()

covid_dep_piv = df_covid_dep.pivot(index='depto', columns='año', values='matriculados').dropna()
covid_dep_piv['var_2020'] = (covid_dep_piv[2020] - covid_dep_piv[2019]) / covid_dep_piv[2019] * 100
covid_dep_piv = covid_dep_piv.sort_values('var_2020')

fig, ax = plt.subplots(figsize=(14, 8))
colors_c = [COLORS[3] if v < 0 else COLORS[5] for v in covid_dep_piv['var_2020']]
ax.barh(range(len(covid_dep_piv)), covid_dep_piv['var_2020'], color=colors_c, alpha=0.85)
ax.set_yticks(range(len(covid_dep_piv)))
ax.set_yticklabels(covid_dep_piv.index, fontsize=8)
ax.set_title('Impacto COVID-19 por Departamento — Variación Matriculados 2019→2020 (%)')
ax.set_xlabel('Variación (%)')
ax.axvline(x=0, color='black', linewidth=0.8)
plt.tight_layout()
plt.savefig(OUT_DIR / '10_covid_por_departamento.png', bbox_inches='tight')
plt.close()
log("  ✅ 10_covid_por_departamento.png")

# 3.4 Ratio docente/estudiante por año
df_ratio = conn.execute("""
    SELECT año,
           SUM(CASE WHEN id_categoria=3 THEN valor_numerico END) as matriculados,
           SUM(CASE WHEN id_categoria=6 THEN valor_numerico END) as docentes
    FROM hecho_snies
    WHERE año BETWEEN 2013 AND 2024
    GROUP BY año
    HAVING docentes > 0
    ORDER BY año
""").df()
df_ratio['ratio'] = df_ratio['matriculados'] / df_ratio['docentes']

fig, ax = plt.subplots(figsize=(12, 6))
ax.plot(df_ratio['año'], df_ratio['ratio'], 'o-', color=COLORS[1], linewidth=2.5, markersize=8)
ax.fill_between(df_ratio['año'], df_ratio['ratio'], alpha=0.15, color=COLORS[1])
ax.set_title('Evolución del Ratio Estudiantes/Docente a Nivel Nacional (2013-2024)')
ax.set_ylabel('Estudiantes por docente')
ax.set_xlabel('Año')
ax.axvspan(2020, 2021, alpha=0.1, color='red')
for _, row in df_ratio.iterrows():
    ax.annotate(f'{row["ratio"]:.1f}', (row['año'], row['ratio']),
                textcoords="offset points", xytext=(0, 10), ha='center', fontsize=9)
plt.tight_layout()
plt.savefig(OUT_DIR / '11_ratio_docente_estudiante.png', bbox_inches='tight')
plt.close()
log("  ✅ 11_ratio_docente_estudiante.png")


# ═══════════════════════════════════════════════════════════════════════════
# SECCIÓN 4: PREPARACIÓN DE FEATURES PARA ML
# ═══════════════════════════════════════════════════════════════════════════
log("\n▶ SECCIÓN 4: PREPARACIÓN DE FEATURES PARA ML")

# Construir dataset plano: una fila por IES-año
df_features = conn.execute("""
    SELECT 
        h.año,
        h.codigo_ies,
        i.nombre_ies,
        i.sector,
        i.caracter,
        u.nombre_departamento as departamento,
        SUM(CASE WHEN h.id_categoria = 1 THEN h.valor_numerico END) as inscritos,
        SUM(CASE WHEN h.id_categoria = 2 THEN h.valor_numerico END) as admitidos,
        SUM(CASE WHEN h.id_categoria = 3 THEN h.valor_numerico END) as matriculados,
        SUM(CASE WHEN h.id_categoria = 4 THEN h.valor_numerico END) as primer_curso,
        SUM(CASE WHEN h.id_categoria = 5 THEN h.valor_numerico END) as graduados,
        SUM(CASE WHEN h.id_categoria = 6 THEN h.valor_numerico END) as docentes,
        SUM(CASE WHEN h.id_categoria = 7 THEN h.valor_numerico END) as administrativos
    FROM hecho_snies h
    JOIN dim_ies i ON h.codigo_ies = i.codigo_ies
    LEFT JOIN dim_ubicacion u ON h.id_departamento = u.id_ubicacion
    GROUP BY h.año, h.codigo_ies, i.nombre_ies, i.sector, i.caracter, u.nombre_departamento
    ORDER BY h.año, h.codigo_ies
""").df()

log(f"  Dataset base: {df_features.shape[0]} filas × {df_features.shape[1]} columnas")

# Calcular features derivadas
df_features['tasa_admision'] = df_features['admitidos'] / df_features['inscritos'].replace(0, np.nan)
df_features['tasa_matricula_admitidos'] = df_features['matriculados'] / df_features['admitidos'].replace(0, np.nan)
df_features['tasa_graduacion'] = df_features['graduados'] / df_features['matriculados'].replace(0, np.nan)
df_features['ratio_docente_estudiante'] = df_features['docentes'] / df_features['matriculados'].replace(0, np.nan)
df_features['ratio_admin_estudiante'] = df_features['administrativos'] / df_features['matriculados'].replace(0, np.nan)

# Agregar número de programas por IES
df_prog = conn.execute("""
    SELECT codigo_ies, COUNT(DISTINCT id_programa) as num_programas
    FROM dim_programa
    WHERE codigo_ies IS NOT NULL
    GROUP BY codigo_ies
""").df()
df_features = df_features.merge(df_prog, on='codigo_ies', how='left')

# Crecimiento interanual de matrícula por IES
df_features = df_features.sort_values(['codigo_ies', 'año'])
df_features['matriculados_ant'] = df_features.groupby('codigo_ies')['matriculados'].shift(1)
df_features['crecimiento_matricula'] = (
    (df_features['matriculados'] - df_features['matriculados_ant'])
    / df_features['matriculados_ant'].replace(0, np.nan)
)
df_features.drop(columns=['matriculados_ant'], inplace=True)

# Guardar
features_path = Path("./data/dataset/features_ml.csv")
df_features.to_csv(features_path, index=False, encoding='utf-8-sig')
log(f"  ✅ Dataset de features guardado: {features_path}")
log(f"     Dimensiones: {df_features.shape[0]} filas × {df_features.shape[1]} columnas")
log(f"     Años: {df_features['año'].min()} - {df_features['año'].max()}")
log(f"     IES únicas: {df_features['codigo_ies'].nunique()}")

# Resumen de features
log("\n  📋 FEATURES CONSTRUIDAS:")
features_desc = {
    'inscritos': 'Total inscritos en la IES para el año',
    'admitidos': 'Total admitidos en la IES para el año',
    'matriculados': 'Total matriculados en la IES para el año',
    'primer_curso': 'Matriculados en primer curso',
    'graduados': 'Total graduados (disponible desde 2018)',
    'docentes': 'Total docentes en la IES',
    'administrativos': 'Total personal administrativo',
    'tasa_admision': 'admitidos / inscritos',
    'tasa_matricula_admitidos': 'matriculados / admitidos',
    'tasa_graduacion': 'graduados / matriculados (variable objetivo)',
    'ratio_docente_estudiante': 'docentes / matriculados',
    'ratio_admin_estudiante': 'administrativos / matriculados',
    'num_programas': 'Número de programas académicos',
    'crecimiento_matricula': 'Variación % interanual de matrícula',
}
for feat, desc in features_desc.items():
    if feat in df_features.columns:
        non_null = df_features[feat].notna().sum()
        log(f"     {feat}: {desc} [{non_null} valores no nulos]")

# 4.2 Visualizar distribución de features clave
fig, axes = plt.subplots(2, 3, figsize=(18, 10))
fig.suptitle('Distribución de Features Clave para ML (2018-2024)', fontsize=14, fontweight='bold')

df_recent = df_features[(df_features['año'] >= 2018) & (df_features['matriculados'] > 0)].copy()

feat_list = [
    ('tasa_graduacion', 'Tasa de Graduación', (0, 0.5)),
    ('ratio_docente_estudiante', 'Ratio Docente/Estudiante', (0, 1)),
    ('tasa_admision', 'Tasa de Admisión', (0, 2)),
    ('crecimiento_matricula', 'Crecimiento Matrícula (%)', (-1, 1)),
    ('matriculados', 'Matriculados (log)', None),
    ('num_programas', 'Nro. de Programas', None),
]

for idx, (feat, title, rng) in enumerate(feat_list):
    ax = axes[idx // 3][idx % 3]
    data = df_recent[feat].dropna()
    if rng:
        data = data[(data >= rng[0]) & (data <= rng[1])]
    if feat == 'matriculados':
        data = np.log10(data[data > 0])
        title = 'log₁₀(Matriculados)'
    ax.hist(data, bins=40, color=COLORS[idx % len(COLORS)], edgecolor='white', alpha=0.8)
    ax.set_title(title)
    ax.set_ylabel('Frecuencia')

plt.tight_layout()
plt.savefig(OUT_DIR / '12_distribucion_features.png', bbox_inches='tight')
plt.close()
log("  ✅ 12_distribucion_features.png")

# ═══════════════════════════════════════════════════════════════════════════
# GUARDAR RESUMEN
# ═══════════════════════════════════════════════════════════════════════════
conn.close()

log("\n" + "=" * 70)
log("EDA COMPLETADO")
log(f"Visualizaciones: {OUT_DIR}")
log(f"Features ML: {features_path}")
log("=" * 70)

# Guardar resumen en txt
with open("reports/eda_resumen.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(resumen_lines))
print(f"\nResumen guardado en: reports/eda_resumen.txt")
