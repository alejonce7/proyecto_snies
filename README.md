┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              BASE DE DATOS: snies.duckdb                            │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                  TABLAS DE DIMENSIÓN                                │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────────────────────┐    ┌─────────────────────────┐                         │
│  │       dim_tiempo        │    │      dim_categoria      │                         │
│  ├─────────────────────────┤    ├─────────────────────────┤                         │
│  │ año (PK)           INT  │    │ id_categoria (PK)  INT  │                         │
│  │ periodo        VARCHAR  │    │ nombre          VARCHAR │                         │
│  │ semestre           INT  │    │ descripcion     VARCHAR │                         │
│  │ fecha_corte        DATE │    │ unidad_medida   VARCHAR │                         │
│  └─────────────────────────┘    └─────────────────────────┘                         │
│              │                              │                                       │
│              │                              │                                       │
│  ┌─────────────────────────┐    ┌─────────────────────────┐                         │
│  │         dim_ies         │    │      dim_programa       │                         │
│  ├─────────────────────────┤    ├─────────────────────────┤                         │
│  │ codigo_ies (PK)  VARCHAR│◄───│ id_programa (PK) VARCHAR│                         │
│  │ nombre_ies       VARCHAR│    │ codigo_ies (FK)  VARCHAR│                         │
│  │ ies_padre       VARCHAR │    │ nombre_programa  VARCHAR│                         │
│  │ sector          VARCHAR │    │ nivel_academico  VARCHAR│                         │
│  │ caracter        VARCHAR │    │ codigo_snies     VARCHAR│                         │
│  │ principal_secc  VARCHAR │    └─────────────────────────┘                         │
│  │ estado          VARCHAR │                                                        │
│  └─────────────────────────┘                                                        │
│              │                                                                      │
│              │                                                                      │
│  ┌─────────────────────────┐                                                        │
│  │      dim_ubicacion      │                                                        │
│  ├─────────────────────────┤                                                        │
│  │ id_ubicacion (PK) VARCHAR│                                                       │
│  │ tipo             VARCHAR │                                                       │
│  │ codigo_dane      VARCHAR │                                                       │
│  │ nombre           VARCHAR │                                                       │
│  │ codigo_departamento VARCHAR│                                                     │
│  │ nombre_departamento VARCHAR│                                                     │
│  └─────────────────────────┘                                                        │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘

                                         │
                                         │ FK
                                         ▼

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                 TABLA DE HECHOS                                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐│
│  │                              hecho_snies                                        ││
│  ├─────────────────────────────────────────────────────────────────────────────────┤│
│  │ id_hecho (PK)              BIGINT      ← Auto-incremental                       ││
│  │ año (FK)                   INT         ← Referencia a dim_tiempo                ││
│  │ id_categoria (FK)          INT         ← Referencia a dim_categoria             ││
│  │ codigo_ies (FK)            VARCHAR(20) ← Referencia a dim_ies                   ││
│  │ id_programa (FK)           VARCHAR(50) ← Referencia a dim_programa              ││
│  │ id_departamento (FK)       VARCHAR(20) ← Referencia a dim_ubicacion (departamento)│
│  │ id_municipio (FK)          VARCHAR(20) ← Referencia a dim_ubicacion (municipio) ││
│  │ valor_numerico             DECIMAL(20,2)← Valor medido                           │
│  │ texto_adicional            TEXT                                                 ││
│  │ fecha_registro             TIMESTAMP                                            ││
│  └─────────────────────────────────────────────────────────────────────────────────┘│
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                  RELACIONES                                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  hecho_snies.año ───────────────► dim_tiempo.año                                    │
│  hecho_snies.id_categoria ──────► dim_categoria.id_categoria                        │
│  hecho_snies.codigo_ies ────────► dim_ies.codigo_ies                                │
│  hecho_snies.id_programa ───────► dim_programa.id_programa                          │
│  hecho_snies.id_departamento ───► dim_ubicacion.id_ubicacion (tipo='departamento')  │
│  hecho_snies.id_municipio ──────► dim_ubicacion.id_ubicacion (tipo='municipio')     │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘

proyecto_snies/
│
├── data/                              # Datos crudos y procesados
│   ├── raw/                          # Archivos originales SNIES
│   │   ├── inscritos/
│   │   ├── admitidos/
│   │   ├── matriculados/
│   │   ├── graduados/
│   │   ├── docentes/
│   │   └── administrativos/
│   ├── processed/                    # Datos limpios (CSV/Parquet)
│   └── database/                     # Base de datos DuckDB
│       └── snies.duckdb
│
├── src/                              # Código fuente
│   ├── __init__.py
│   │
│   ├── etl/                          # Pipeline ETL
│   │   ├── __init__.py
│   │   ├── extract.py               # Lectura de archivos
│   │   ├── transform.py             # Limpieza y transformación
│   │   ├── load.py                  # Carga a base de datos
│   │   └── pipeline.py              # Orquestador completo
│   │
│   ├── database/                     # Gestión de base de datos
│   │   ├── __init__.py
│   │   ├── schema.py                # Creación de tablas
│   │   ├── connection.py            # Conexión a DuckDB
│   │   └── queries.py               # Consultas SQL reutilizables
│   │
│   ├── quality/                      # Diagnóstico de calidad
│   │   ├── __init__.py
│   │   ├── diagnostico.py           # Tu script actual
│   │   ├── validaciones.py          # Reglas de calidad
│   │   └── reportes.py              # Generación de reportes
│   │
│   └── utils/                        # Utilidades compartidas
│       ├── __init__.py
│       ├── config.py                # Configuración (rutas, parámetros)
│       ├── helpers.py               # Funciones auxiliares
│       └── constants.py             # Constantes (categorías, patrones)
│
├── notebooks/                        # Jupyter notebooks para análisis
│   ├── 01_exploracion_datos.ipynb
│   ├── 02_analisis_calidad.ipynb
│   ├── 03_modelo_datos.ipynb
│   └── 04_pruebas_etl.ipynb
│
├── reports/                          # Reportes generados
│   ├── calidad_datos/               # Diagnóstico de calidad
│   │   ├── diagnostico_completo.json
│   │   ├── mapa_problemas_calidad.csv
│   │   ├── inconsistencias_columnas.csv
│   │   ├── inconsistencias_codigos.csv
│   │   └── cambios_estructura.csv
│   ├── diseno/                       # Documentación de diseño
│   │   ├── diagrama_er.png
│   │   ├── modelo_datos.md
│   │   └── diccionario_datos.xlsx
│   └── dashboards/                   # Exportaciones para dashboard
│       ├── vista_ies_anual.csv
│       ├── vista_departamentos.csv
│       └── vista_programas.csv
│
├── docs/                             # Documentación del proyecto
│   ├── hoja_ruta.md                 # Hoja de ruta del proyecto
│   ├── manual_etl.md                # Documentación técnica ETL
│   ├── manual_usuario.md            # Guía para el equipo
│   └── arquitectura.md              # Diagramas y decisiones técnicas
│
├── tests/                            # Pruebas unitarias
│   ├── __init__.py
│   ├── test_extract.py
│   ├── test_transform.py
│   └── test_load.py
│
├── scripts/                          # Scripts ejecutables
│   ├── run_diagnostico.py           # Ejecutar diagnóstico
│   ├── run_etl_completo.py          # Ejecutar ETL completo
│   ├── run_etl_anio.py              # Ejecutar ETL para un año específico
│   └── generar_reportes.sh          # Script bash para automatizar
│
├── dashboards/                       # Dashboard (Streamlit/Power BI)
│   ├── app.py                       # Aplicación Streamlit
│   ├── pages/                        # Múltiples páginas
│   │   ├── home.py
│   │   ├── analisis_ies.py
│   │   ├── comparativo_anual.py
│   │   └── mapa_colombia.py
│   └── assets/                       # Recursos visuales
│       └── logo.png
│
├── requirements.txt                  # Dependencias Python
├── .env.example                      # Variables de entorno (ejemplo)
├── .gitignore                        # Archivos a ignorar en Git
├── README.md                         # Descripción del proyecto
└── setup.py                          # Instalación del paquete