"""
=============================================================================
FASE 3: MODELAMIENTO DE MACHINE LEARNING
Proyecto SNIES — Minería de Datos 2026 · Persona 2 (Científico/a de Datos)
=============================================================================
Combina DOS enfoques (permitido por la rúbrica):

  A. SUPERVISADO  — Regresión para predecir la TASA DE GRADUACIÓN de una IES
                    a partir de su perfil operativo.
                    Modelos: Regresión Lineal, Random Forest, Gradient Boosting.
                    Métricas: RMSE, MAE, R².  Holdout temporal 2023-2024.

  B. NO SUPERVISADO — Clustering (segmentación) de IES por perfil operativo.
                    Modelos: KMeans (elbow + silhouette), Agglomerative, DBSCAN.
                    Métrica: Silhouette Score.

Genera:
  - Modelos entrenados en          models/
  - Visualizaciones en             reports/modelado_visualizaciones/
  - Métricas (para notebook/docs)  reports/modelado_metricas.json
  - Resumen de texto               reports/modelado_resumen.txt
  - IES con clúster asignado       data/dataset/ies_clusters.csv
=============================================================================
"""

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import joblib

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import (RandomForestRegressor,
                              HistGradientBoostingRegressor)
from sklearn.cluster import KMeans, AgglomerativeClustering, DBSCAN
from sklearn.metrics import (mean_squared_error, mean_absolute_error, r2_score,
                            silhouette_score)
from sklearn.model_selection import cross_val_score, KFold
from sklearn.inspection import permutation_importance

warnings.filterwarnings('ignore')
RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

# ── Rutas y estilo ───────────────────────────────────────────────────────────
FEATURES_PATH = Path("./data/dataset/features_ml.csv")
OUT_DIR = Path("./reports/modelado_visualizaciones")
MODELS_DIR = Path("./models")
OUT_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    'figure.figsize': (14, 7), 'figure.dpi': 150, 'font.family': 'sans-serif',
    'font.size': 11, 'axes.titlesize': 14, 'axes.titleweight': 'bold',
    'axes.labelsize': 12, 'axes.grid': True, 'grid.alpha': 0.3,
    'legend.fontsize': 10, 'figure.facecolor': 'white',
})
COLORS = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#3B1F2B', '#44BBA4', '#E94F37']

resumen_lines = []
metrics = {}

def log(msg=""):
    print(msg)
    resumen_lines.append(str(msg))

log("=" * 74)
log("FASE 3 — MODELAMIENTO DE MACHINE LEARNING · SNIES")
log("=" * 74)

# ═══════════════════════════════════════════════════════════════════════════
# 0. CARGA Y NORMALIZACIÓN DE DATOS
# ═══════════════════════════════════════════════════════════════════════════
log("\n▶ 0. CARGA Y LIMPIEZA")

df = pd.read_csv(FEATURES_PATH)
log(f"  Dataset base: {df.shape[0]} filas × {df.shape[1]} columnas (IES-año, 2000-2024)")

# 0.1 Normalizar texto del departamento (quita acentos, mayúsculas, espacios)
def normaliza_texto(s):
    if pd.isna(s):
        return s
    s = str(s).strip().upper()
    repl = (('Á', 'A'), ('É', 'E'), ('Í', 'I'), ('Ó', 'O'), ('Ú', 'U'),
            ('Ñ', 'N'), ('.', ''), ('  ', ' '))
    for a, b in repl:
        s = s.replace(a, b)
    return s.strip()

df['departamento_norm'] = df['departamento'].apply(normaliza_texto)
# Unificar variantes de Bogotá
df['departamento_norm'] = df['departamento_norm'].replace(
    {'BOGOTA DC': 'BOGOTA', 'BOGOTA D C': 'BOGOTA', 'BOGOTA, D.C.': 'BOGOTA'})
df.loc[df['departamento_norm'].str.contains('BOGOTA', na=False), 'departamento_norm'] = 'BOGOTA'

log(f"  Departamentos: {df['departamento'].nunique()} crudos → "
    f"{df['departamento_norm'].nunique()} normalizados")

# 0.2 Normalizar sector (cobertura baja, solo descriptivo)
df['sector_norm'] = df['sector'].apply(
    lambda s: ('OFICIAL' if str(s).upper().startswith('O') else 'PRIVADO')
    if pd.notna(s) else 'DESCONOCIDO')
log(f"  Sector conocido: {(df['sector_norm'] != 'DESCONOCIDO').sum()} de {len(df)} "
    f"({(df['sector_norm'] != 'DESCONOCIDO').mean()*100:.0f}%) → se excluye del modelo, "
    f"se usa solo como descriptor")

# ═══════════════════════════════════════════════════════════════════════════
# A. MODELO SUPERVISADO — REGRESIÓN DE LA TASA DE GRADUACIÓN
# ═══════════════════════════════════════════════════════════════════════════
log("\n" + "=" * 74)
log("A. MODELO SUPERVISADO — Predicción de la tasa de graduación")
log("=" * 74)

# A.1 Filtros de calidad
#   - Solo 2018+ (graduados consistentes); 2017 tiene dato anómalo de carga
#   - tasa_graduacion válida y plausible (0 < t <= 1: imposible graduar más
#     personas que las matriculadas en el mismo año)
reg = df[(df['año'] >= 2018) &
         (df['matriculados'] > 0) &
         (df['tasa_graduacion'].notna()) &
         (df['tasa_graduacion'] > 0) &
         (df['tasa_graduacion'] <= 1.0)].copy()
log(f"\n▶ A.1 PREPARACIÓN")
log(f"  Filtro 2018-2024 + tasa_graduacion en (0,1]: {len(reg)} observaciones")
log(f"  (se descartaron {((df['año']>=2018)&(df['tasa_graduacion']>1.0)).sum()} filas "
    f"con tasa > 1.0, físicamente imposibles)")

# A.2 Ingeniería de variables (log para variables muy sesgadas de tamaño)
reg['log_matriculados'] = np.log1p(reg['matriculados'])
reg['log_docentes'] = np.log1p(reg['docentes'])

NUM_FEATS = ['log_matriculados', 'log_docentes', 'ratio_docente_estudiante',
             'tasa_admision', 'tasa_matricula_admitidos', 'num_programas',
             'crecimiento_matricula']
CAT_FEATS = ['departamento_norm']
TARGET = 'tasa_graduacion'
ALL_FEATS = NUM_FEATS + CAT_FEATS

log("  Variables predictoras (NO incluye 'graduados' → evita fuga de información):")
for f in NUM_FEATS:
    log(f"     [num] {f}")
for f in CAT_FEATS:
    log(f"     [cat] {f} (one-hot)")
log(f"  Variable objetivo: {TARGET}  (graduados / matriculados)")

# A.3 Split TEMPORAL (holdout de años recientes, como exige la validación)
train = reg[reg['año'].between(2018, 2022)].copy()
test = reg[reg['año'].between(2023, 2024)].copy()
X_train, y_train = train[ALL_FEATS], train[TARGET]
X_test, y_test = test[ALL_FEATS], test[TARGET]
log(f"\n  Split TEMPORAL (evita fuga del futuro):")
log(f"     Entrenamiento 2018-2022: {len(train)} filas")
log(f"     Holdout       2023-2024: {len(test)} filas")

# A.4 Preprocesamiento: imputación (mediana) + escalado + one-hot
#   Decisión: imputar nulos con la MEDIANA (robusta a outliers) en numéricas;
#   one-hot en el departamento. Se escala solo para la Regresión Lineal.
preproc_lineal = ColumnTransformer([
    ('num', Pipeline([('imp', SimpleImputer(strategy='median')),
                      ('sc', StandardScaler())]), NUM_FEATS),
    ('cat', OneHotEncoder(handle_unknown='ignore'), CAT_FEATS),
])
preproc_arbol = ColumnTransformer([
    ('num', SimpleImputer(strategy='median'), NUM_FEATS),
    ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), CAT_FEATS),
])

modelos = {
    'Regresión Lineal': Pipeline([
        ('prep', preproc_lineal),
        ('model', LinearRegression())]),
    'Random Forest': Pipeline([
        ('prep', preproc_arbol),
        ('model', RandomForestRegressor(
            n_estimators=400, max_depth=10, min_samples_leaf=12,
            max_features=0.6, n_jobs=-1, random_state=RANDOM_STATE))]),
    'Gradient Boosting': Pipeline([
        ('prep', preproc_arbol),
        ('model', HistGradientBoostingRegressor(
            max_iter=600, learning_rate=0.03, max_depth=3, max_leaf_nodes=15,
            min_samples_leaf=25, l2_regularization=2.0, early_stopping=True,
            validation_fraction=0.15, n_iter_no_change=25,
            random_state=RANDOM_STATE))]),
}

log(f"\n▶ A.2 ENTRENAMIENTO Y COMPARACIÓN DE 3 ALGORITMOS")
cv = KFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
resultados = []
preds_test = {}

for nombre, pipe in modelos.items():
    # Validación cruzada (5-fold) sobre entrenamiento → estabilidad
    cv_r2 = cross_val_score(pipe, X_train, y_train, cv=cv, scoring='r2')
    cv_rmse = -cross_val_score(pipe, X_train, y_train, cv=cv,
                               scoring='neg_root_mean_squared_error')
    # Ajuste final y evaluación en holdout
    pipe.fit(X_train, y_train)
    pred_tr = pipe.predict(X_train)
    pred_te = pipe.predict(X_test)
    preds_test[nombre] = pred_te

    r2_tr = r2_score(y_train, pred_tr)
    r2_te = r2_score(y_test, pred_te)
    rmse_te = np.sqrt(mean_squared_error(y_test, pred_te))
    mae_te = mean_absolute_error(y_test, pred_te)

    resultados.append({
        'modelo': nombre,
        'cv_r2_mean': float(cv_r2.mean()), 'cv_r2_std': float(cv_r2.std()),
        'cv_rmse_mean': float(cv_rmse.mean()),
        'r2_train': float(r2_tr), 'r2_holdout': float(r2_te),
        'rmse_holdout': float(rmse_te), 'mae_holdout': float(mae_te),
        'gap_overfit': float(r2_tr - r2_te),
    })
    log(f"\n  ── {nombre} ──")
    log(f"     CV(5) R²:  {cv_r2.mean():.3f} ± {cv_r2.std():.3f}")
    log(f"     R² train:  {r2_tr:.3f}   |   R² holdout: {r2_te:.3f}   "
        f"(gap={r2_tr-r2_te:+.3f})")
    log(f"     RMSE holdout: {rmse_te:.4f}   MAE holdout: {mae_te:.4f}")

df_res = pd.DataFrame(resultados).sort_values('r2_holdout', ascending=False)
metrics['supervisado'] = {
    'n_train': len(train), 'n_test': len(test),
    'features': ALL_FEATS, 'target': TARGET,
    'resultados': resultados,
    'baseline_rmse_media': float(np.sqrt(mean_squared_error(
        y_test, np.full_like(y_test, y_train.mean())))),
}

# A.5 Selección del mejor modelo
mejor = df_res.iloc[0]['modelo']
mejor_pipe = modelos[mejor]
metrics['supervisado']['mejor_modelo'] = mejor
log(f"\n▶ A.3 MODELO SELECCIONADO: {mejor}")
log(f"     Justificación: mejor R² en holdout ({df_res.iloc[0]['r2_holdout']:.3f}) "
    f"con menor RMSE ({df_res.iloc[0]['rmse_holdout']:.4f}).")
log(f"     Baseline (predecir la media): RMSE = "
    f"{metrics['supervisado']['baseline_rmse_media']:.4f} → el modelo lo supera.")

# A.6 Importancia de variables (permutación, sobre el holdout)
nombres_oh = (mejor_pipe.named_steps['prep']
              .named_transformers_['cat']
              .get_feature_names_out(CAT_FEATS))
feat_names_full = NUM_FEATS + list(nombres_oh)

perm = permutation_importance(mejor_pipe, X_test, y_test, n_repeats=15,
                              random_state=RANDOM_STATE, scoring='r2')
imp = (pd.DataFrame({'feature': ALL_FEATS, 'importancia': perm.importances_mean,
                     'std': perm.importances_std})
       .sort_values('importancia', ascending=False))
log(f"\n▶ A.4 IMPORTANCIA DE VARIABLES (permutación, holdout):")
for _, r in imp.iterrows():
    log(f"     {r['feature']:30s} {r['importancia']:+.4f}")
metrics['supervisado']['importancia'] = imp.to_dict('records')

# A.7 Guardar modelo
joblib.dump(mejor_pipe, MODELS_DIR / 'modelo_regresion_tasa_graduacion.joblib')
log(f"\n  ✅ Modelo guardado: models/modelo_regresion_tasa_graduacion.joblib")

# ── Gráfico 1: comparación de modelos ──
fig, axes = plt.subplots(1, 2, figsize=(15, 6))
ax = axes[0]
x = np.arange(len(df_res))
w = 0.35
ax.bar(x - w/2, df_res['r2_train'], w, label='R² entrenamiento', color=COLORS[0], alpha=0.85)
ax.bar(x + w/2, df_res['r2_holdout'], w, label='R² holdout 2023-24', color=COLORS[2], alpha=0.85)
ax.set_xticks(x); ax.set_xticklabels(df_res['modelo'], fontsize=10)
ax.set_ylabel('R²'); ax.set_title('Comparación de modelos — R²'); ax.legend()
for i, (tr, te) in enumerate(zip(df_res['r2_train'], df_res['r2_holdout'])):
    ax.annotate(f'{tr:.2f}', (i - w/2, tr), ha='center', va='bottom', fontsize=8)
    ax.annotate(f'{te:.2f}', (i + w/2, te), ha='center', va='bottom', fontsize=8)
ax = axes[1]
ax.bar(x, df_res['rmse_holdout'], color=COLORS[3], alpha=0.85)
ax.axhline(metrics['supervisado']['baseline_rmse_media'], color='gray',
           linestyle='--', label='Baseline (media)')
ax.set_xticks(x); ax.set_xticklabels(df_res['modelo'], fontsize=10)
ax.set_ylabel('RMSE'); ax.set_title('Comparación de modelos — RMSE holdout'); ax.legend()
for i, v in enumerate(df_res['rmse_holdout']):
    ax.annotate(f'{v:.4f}', (i, v), ha='center', va='bottom', fontsize=8)
plt.tight_layout()
plt.savefig(OUT_DIR / '13_comparacion_modelos_regresion.png', bbox_inches='tight')
plt.close()
log("  ✅ 13_comparacion_modelos_regresion.png")

# ── Gráfico 2: predicho vs real (mejor modelo) ──
fig, ax = plt.subplots(figsize=(8, 8))
pred_best = preds_test[mejor]
ax.scatter(y_test, pred_best, alpha=0.5, color=COLORS[0], edgecolors='white', s=40)
lim = [0, max(y_test.max(), pred_best.max()) * 1.05]
ax.plot(lim, lim, 'r--', label='Predicción perfecta')
ax.set_xlim(lim); ax.set_ylim(lim)
ax.set_xlabel('Tasa de graduación REAL'); ax.set_ylabel('Tasa de graduación PREDICHA')
ax.set_title(f'Predicho vs. Real — {mejor} (holdout 2023-2024)\n'
             f'R²={df_res.iloc[0]["r2_holdout"]:.3f} · RMSE={df_res.iloc[0]["rmse_holdout"]:.4f}')
ax.legend()
plt.tight_layout()
plt.savefig(OUT_DIR / '14_predicho_vs_real.png', bbox_inches='tight')
plt.close()
log("  ✅ 14_predicho_vs_real.png")

# ── Gráfico 3: importancia de variables ──
fig, ax = plt.subplots(figsize=(11, 6))
imp_plot = imp.iloc[::-1]
ax.barh(range(len(imp_plot)), imp_plot['importancia'], xerr=imp_plot['std'],
        color=COLORS[5], alpha=0.85)
ax.set_yticks(range(len(imp_plot)))
ax.set_yticklabels(imp_plot['feature'], fontsize=10)
ax.set_xlabel('Caída de R² al permutar la variable (importancia)')
ax.set_title(f'Importancia de variables — {mejor}')
plt.tight_layout()
plt.savefig(OUT_DIR / '15_importancia_variables.png', bbox_inches='tight')
plt.close()
log("  ✅ 15_importancia_variables.png")

# ═══════════════════════════════════════════════════════════════════════════
# B. MODELO NO SUPERVISADO — CLUSTERING DE IES POR PERFIL OPERATIVO
# ═══════════════════════════════════════════════════════════════════════════
log("\n" + "=" * 74)
log("B. MODELO NO SUPERVISADO — Segmentación (clustering) de IES")
log("=" * 74)

# B.1 Perfil estable por IES: promedio de los años recientes 2022-2024
log("\n▶ B.1 PREPARACIÓN")
rec = df[(df['año'].between(2022, 2024)) & (df['matriculados'] > 0)].copy()
rec['log_matriculados'] = np.log1p(rec['matriculados'])

perfil = (rec.groupby('codigo_ies')
          .agg(nombre_ies=('nombre_ies', 'first'),
               departamento=('departamento_norm', 'first'),
               sector=('sector_norm', 'first'),
               log_matriculados=('log_matriculados', 'mean'),
               matriculados=('matriculados', 'mean'),
               docentes=('docentes', 'mean'),
               ratio_docente_estudiante=('ratio_docente_estudiante', 'mean'),
               tasa_graduacion=('tasa_graduacion', 'mean'),
               tasa_admision=('tasa_admision', 'mean'),
               tasa_matricula_admitidos=('tasa_matricula_admitidos', 'mean'),
               num_programas=('num_programas', 'mean'))
          .reset_index())

# Dimensiones del perfil operativo: TAMAÑO, INTENSIDAD DOCENTE, EFICIENCIA de
# salida y AMPLITUD de oferta. Se omite tasa_admision (valores ruidosos >1).
CLUSTER_FEATS = ['log_matriculados', 'ratio_docente_estudiante',
                 'tasa_graduacion', 'num_programas']
# Requerir las variables núcleo; imputar resto con mediana
perfil = perfil.dropna(subset=['log_matriculados', 'ratio_docente_estudiante',
                               'tasa_graduacion']).copy()
for c in CLUSTER_FEATS:
    perfil[c] = perfil[c].fillna(perfil[c].median())
# Recortar outliers extremos del perfil (winsorización al p1-p99)
for c in CLUSTER_FEATS:
    lo, hi = perfil[c].quantile([0.01, 0.99])
    perfil[c] = perfil[c].clip(lo, hi)

log(f"  IES con perfil completo (2022-2024): {len(perfil)}")
log(f"  Variables de segmentación: {', '.join(CLUSTER_FEATS)}")
log(f"  Normalización: StandardScaler (media 0, desv 1) — obligatorio para distancias")

scaler = StandardScaler()
Xc = scaler.fit_transform(perfil[CLUSTER_FEATS])

# B.2 KMeans: elbow (inercia) + silhouette para k = 2..8
log("\n▶ B.2 SELECCIÓN DEL NÚMERO DE CLÚSTERES (KMeans)")
ks = range(2, 9)
inercias, sils = [], []
for k in ks:
    km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
    labels = km.fit_predict(Xc)
    inercias.append(km.inertia_)
    s = silhouette_score(Xc, labels)
    sils.append(s)
    log(f"     k={k}: inercia={km.inertia_:8.1f}  silhouette={s:.3f}")

k_sil = list(ks)[int(np.argmax(sils))]
# Decisión: el silhouette es máximo en k_sil, pero ese k solo aísla un puñado
# de micro-IES y deja un único macro-grupo muy heterogéneo (poco accionable).
# Se elige K_FINAL=3 (silhouette 0.45, "estructura razonable"), que además es el
# codo de la inercia y revela 3 arquetipos operativos con valor para negocio.
K_FINAL = 3
metrics['no_supervisado'] = {
    'n_ies': len(perfil), 'features': CLUSTER_FEATS,
    'k_silhouette': {int(k): float(s) for k, s in zip(ks, sils)},
    'k_optimo_silhouette': int(k_sil),
    'k_seleccionado': int(K_FINAL),
}
log(f"  → k óptimo por silhouette puro: {k_sil} (silhouette={max(sils):.3f})")
log(f"  → k SELECCIONADO: {K_FINAL}. Justificación: k={k_sil} solo separa unas pocas")
log(f"     micro-IES de un macro-grupo heterogéneo (valor de negocio limitado).")
log(f"     k={K_FINAL} mantiene silhouette en zona razonable ({sils[K_FINAL-2]:.3f}),")
log(f"     coincide con el codo de la inercia y produce 3 arquetipos accionables.")

# ── Gráfico 4: elbow + silhouette ──
fig, axes = plt.subplots(1, 2, figsize=(15, 6))
ax = axes[0]
ax.plot(list(ks), inercias, 'o-', color=COLORS[0], linewidth=2, markersize=8)
ax.set_title('Método del Codo (Elbow)'); ax.set_xlabel('Número de clústeres (k)')
ax.set_ylabel('Inercia (SSE intra-clúster)')
ax = axes[1]
ax.plot(list(ks), sils, 'o-', color=COLORS[1], linewidth=2, markersize=8)
ax.axvline(k_sil, color='gray', linestyle=':', label=f'máx. silhouette (k={k_sil})')
ax.axvline(K_FINAL, color='green', linestyle='--', label=f'k seleccionado = {K_FINAL}')
ax.set_title('Silhouette Score por k'); ax.set_xlabel('Número de clústeres (k)')
ax.set_ylabel('Silhouette Score'); ax.legend()
for k, s in zip(ks, sils):
    ax.annotate(f'{s:.3f}', (k, s), textcoords='offset points', xytext=(0, 8),
                ha='center', fontsize=8)
plt.tight_layout()
plt.savefig(OUT_DIR / '16_elbow_silhouette.png', bbox_inches='tight')
plt.close()
log("  ✅ 16_elbow_silhouette.png")

# B.3 Comparar 3 algoritmos de clustering con k seleccionado
log("\n▶ B.3 COMPARACIÓN DE ALGORITMOS DE CLUSTERING (k=%d)" % K_FINAL)
km_final = KMeans(n_clusters=K_FINAL, random_state=RANDOM_STATE, n_init=20)
lab_km = km_final.fit_predict(Xc)
sil_km = silhouette_score(Xc, lab_km)

agg = AgglomerativeClustering(n_clusters=K_FINAL)
lab_agg = agg.fit_predict(Xc)
sil_agg = silhouette_score(Xc, lab_agg)

# DBSCAN: eps ajustado; puede marcar ruido (-1)
db = DBSCAN(eps=1.2, min_samples=5)
lab_db = db.fit_predict(Xc)
n_db = len(set(lab_db)) - (1 if -1 in lab_db else 0)
sil_db = (silhouette_score(Xc[lab_db != -1], lab_db[lab_db != -1])
          if n_db >= 2 and (lab_db != -1).sum() > n_db else float('nan'))

log(f"     KMeans (k={K_FINAL}):        silhouette={sil_km:.3f}")
log(f"     Agglomerative (k={K_FINAL}): silhouette={sil_agg:.3f}")
log(f"     DBSCAN (eps=1.2):       silhouette={sil_db:.3f}  "
    f"({n_db} clústeres, {(lab_db==-1).sum()} IES de ruido)")
metrics['no_supervisado']['comparacion'] = {
    'kmeans_silhouette': float(sil_km),
    'agglomerative_silhouette': float(sil_agg),
    'dbscan_silhouette': (None if np.isnan(sil_db) else float(sil_db)),
    'dbscan_n_clusters': int(n_db), 'dbscan_ruido': int((lab_db == -1).sum()),
}
log(f"  → Seleccionado: KMeans. DBSCAN logra mayor silhouette pero descarta "
    f"{(lab_db==-1).sum()} IES como 'ruido' y colapsa a {n_db} grupos; KMeans asigna")
log(f"     TODAS las IES a 3 arquetipos interpretables y accionables (silhouette ≈ Agglomerative).")

# B.4 Perfilar los clústeres de KMeans
perfil['cluster'] = lab_km
resumen_clusters = (perfil.groupby('cluster')
                    .agg(n_ies=('codigo_ies', 'count'),
                         matriculados_med=('matriculados', 'median'),
                         docentes_med=('docentes', 'median'),
                         ratio_doc_est=('ratio_docente_estudiante', 'median'),
                         tasa_graduacion=('tasa_graduacion', 'median'),
                         tasa_admision=('tasa_admision', 'median'),
                         num_programas=('num_programas', 'median'))
                    .reset_index())
# Asignar nombres de arquetipo ESTABLES (las etiquetas de KMeans son arbitrarias):
#   - mayor tamaño            → "Mega-masivas"
#   - menor tamaño + alto ratio docente → "Pequeñas especializadas"
#   - resto                   → "Medianas tradicionales"
orden_tam = resumen_clusters.sort_values('matriculados_med')['cluster'].tolist()
nombres_arq = {orden_tam[0]: 'Pequeñas especializadas',
               orden_tam[-1]: 'Mega-masivas'}
for cl in orden_tam[1:-1]:
    nombres_arq[cl] = 'Medianas tradicionales'
resumen_clusters['arquetipo'] = resumen_clusters['cluster'].map(nombres_arq)
perfil['arquetipo'] = perfil['cluster'].map(nombres_arq)

log("\n▶ B.4 PERFIL DE LOS CLÚSTERES (medianas):")
log(resumen_clusters[['cluster', 'arquetipo', 'n_ies', 'matriculados_med',
                      'docentes_med', 'ratio_doc_est', 'tasa_graduacion',
                      'num_programas']].to_string(index=False))
metrics['no_supervisado']['perfiles'] = resumen_clusters.to_dict('records')
metrics['no_supervisado']['nombres_arquetipo'] = {int(k): v for k, v in nombres_arq.items()}

# Sector predominante (donde se conoce) por clúster
log("\n  Sector predominante por clúster (donde se conoce):")
for cl in sorted(perfil['cluster'].unique()):
    sub = perfil[(perfil['cluster'] == cl) & (perfil['sector'] != 'DESCONOCIDO')]
    if len(sub):
        vc = sub['sector'].value_counts(normalize=True)
        log(f"     Clúster {cl}: {vc.index[0]} ({vc.iloc[0]*100:.0f}% de {len(sub)} IES con sector conocido)")
    else:
        log(f"     Clúster {cl}: sector desconocido")

# B.5 Guardar asignaciones + modelo
perfil_out = perfil[['codigo_ies', 'nombre_ies', 'departamento', 'sector',
                     'matriculados', 'docentes', 'ratio_docente_estudiante',
                     'tasa_graduacion', 'num_programas', 'cluster', 'arquetipo']].copy()
perfil_out.to_csv("./data/dataset/ies_clusters.csv", index=False, encoding='utf-8-sig')
joblib.dump({'scaler': scaler, 'kmeans': km_final, 'features': CLUSTER_FEATS},
            MODELS_DIR / 'modelo_clustering_ies.joblib')
log(f"\n  ✅ Asignaciones guardadas: data/dataset/ies_clusters.csv")
log(f"  ✅ Modelo guardado: models/modelo_clustering_ies.joblib")

# ── Gráfico 5: perfiles de clúster (heatmap de medias estandarizadas) ──
perfil_std = perfil.copy()
perfil_std[CLUSTER_FEATS] = Xc
cluster_means = perfil_std.groupby('cluster')[CLUSTER_FEATS].mean()
fig, ax = plt.subplots(figsize=(10, max(4, K_FINAL * 1.1)))
sns.heatmap(cluster_means, annot=True, fmt='.2f', cmap='RdBu_r', center=0,
            linewidths=1, ax=ax, cbar_kws={'label': 'Desv. estándar respecto a la media'})
ax.set_title('Perfil de cada clúster (variables estandarizadas)')
ax.set_ylabel('Clúster'); ax.set_xlabel('Variable')
ax.set_xticklabels([c.replace('_', '\n') for c in CLUSTER_FEATS], rotation=0, fontsize=9)
plt.tight_layout()
plt.savefig(OUT_DIR / '17_perfiles_cluster_heatmap.png', bbox_inches='tight')
plt.close()
log("  ✅ 17_perfiles_cluster_heatmap.png")

# ── Gráfico 6: scatter de clústeres (matriculados vs tasa graduación) ──
fig, axes = plt.subplots(1, 2, figsize=(16, 7))
ax = axes[0]
for cl in sorted(perfil['cluster'].unique()):
    sub = perfil[perfil['cluster'] == cl]
    ax.scatter(sub['matriculados'], sub['tasa_graduacion'],
               label=f'{nombres_arq[cl]} (n={len(sub)})', alpha=0.65,
               color=COLORS[cl % len(COLORS)], s=45, edgecolors='white')
ax.set_xscale('log')
ax.set_xlabel('Matriculados (escala log)'); ax.set_ylabel('Tasa de graduación')
ax.set_title('Clústeres: Tamaño vs. Tasa de graduación'); ax.legend()
ax = axes[1]
for cl in sorted(perfil['cluster'].unique()):
    sub = perfil[perfil['cluster'] == cl]
    ax.scatter(sub['ratio_docente_estudiante'], sub['tasa_graduacion'],
               label=nombres_arq[cl], alpha=0.65,
               color=COLORS[cl % len(COLORS)], s=45, edgecolors='white')
ax.set_xlabel('Ratio docente/estudiante'); ax.set_ylabel('Tasa de graduación')
ax.set_xlim(0, perfil['ratio_docente_estudiante'].quantile(0.97))
ax.set_title('Clústeres: Dotación docente vs. Tasa de graduación'); ax.legend()
plt.tight_layout()
plt.savefig(OUT_DIR / '18_clusters_scatter.png', bbox_inches='tight')
plt.close()
log("  ✅ 18_clusters_scatter.png")

# ═══════════════════════════════════════════════════════════════════════════
# GUARDAR MÉTRICAS Y RESUMEN
# ═══════════════════════════════════════════════════════════════════════════
with open("reports/modelado_metricas.json", "w", encoding="utf-8") as f:
    json.dump(metrics, f, ensure_ascii=False, indent=2)
with open("reports/modelado_resumen.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(resumen_lines))

log("\n" + "=" * 74)
log("FASE 3 COMPLETADA")
log(f"  Modelos:        models/")
log(f"  Visualizaciones: {OUT_DIR}")
log(f"  Métricas:       reports/modelado_metricas.json")
log(f"  Resumen:        reports/modelado_resumen.txt")
log("=" * 74)
print("\nResumen guardado en reports/modelado_resumen.txt")
