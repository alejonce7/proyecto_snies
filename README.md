┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              BASE DE DATOS: snies.duckdb                             │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                  TABLAS DE DIMENSIÓN                                  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                       │
│  ┌─────────────────────────┐    ┌─────────────────────────┐                          │
│  │       dim_tiempo        │    │      dim_categoria      │                          │
│  ├─────────────────────────┤    ├─────────────────────────┤                          │
│  │ año (PK)           INT  │    │ id_categoria (PK)  INT  │                          │
│  │ periodo        VARCHAR  │    │ nombre          VARCHAR │                          │
│  │ semestre           INT  │    │ descripcion     VARCHAR │                          │
│  │ fecha_corte        DATE │    │ unidad_medida   VARCHAR │                          │
│  └─────────────────────────┘    └─────────────────────────┘                          │
│              │                              │                                         │
│              │                              │                                         │
│  ┌─────────────────────────┐    ┌─────────────────────────┐                          │
│  │         dim_ies         │    │      dim_programa       │                          │
│  ├─────────────────────────┤    ├─────────────────────────┤                          │
│  │ codigo_ies (PK)  VARCHAR│◄───│ id_programa (PK) VARCHAR│                          │
│  │ nombre_ies       VARCHAR│    │ codigo_ies (FK)  VARCHAR│                          │
│  │ ies_padre       VARCHAR │    │ nombre_programa  VARCHAR│                          │
│  │ sector          VARCHAR │    │ nivel_academico  VARCHAR│                          │
│  │ caracter        VARCHAR │    │ codigo_snies     VARCHAR│                          │
│  │ principal_secc  VARCHAR │    └─────────────────────────┘                          │
│  │ estado          VARCHAR │                                                         │
│  └─────────────────────────┘                                                         │
│              │                                                                        │
│              │                                                                        │
│  ┌─────────────────────────┐    ┌─────────────────────────┐                          │
│  │      dim_ubicacion      │    │                         │                          │
│  ├─────────────────────────┤    │                         │                          │
│  │ id_ubicacion (PK) VARCHAR│    │                         │                          │
│  │ tipo             VARCHAR │    │                         │                          │
│  │ codigo_dane      VARCHAR │    │                         │                          │
│  │ nombre           VARCHAR │    │                         │                          │
│  │ codigo_departamento VARCHAR│    │                         │                          │
│  │ nombre_departamento VARCHAR│    │                         │                          │
│  └─────────────────────────┘    └─────────────────────────┘                          │
│                                                                                       │
└─────────────────────────────────────────────────────────────────────────────────────┘

                                         │
                                         │ FK
                                         ▼

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                 TABLA DE HECHOS                                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐│
│  │                              hecho_snies                                         ││
│  ├─────────────────────────────────────────────────────────────────────────────────┤│
│  │ id_hecho (PK)              BIGINT      ← Auto-incremental                       ││
│  │ año (FK)                   INT         ← Referencia a dim_tiempo                ││
│  │ id_categoria (FK)          INT         ← Referencia a dim_categoria             ││
│  │ codigo_ies (FK)            VARCHAR(20) ← Referencia a dim_ies                   ││
│  │ id_programa (FK)           VARCHAR(50) ← Referencia a dim_programa              ││
│  │ id_departamento (FK)       VARCHAR(20) ← Referencia a dim_ubicacion (departamento)│
│  │ id_municipio (FK)          VARCHAR(20) ← Referencia a dim_ubicacion (municipio) ││
│  │ valor_numerico             DECIMAL(20,2)← Valor medido (ej: cantidad de estudiantes)│
│  │ texto_adicional            TEXT        ← Información adicional                  ││
│  │ fecha_registro             TIMESTAMP   ← Cuándo se cargó el registro            ││
│  └─────────────────────────────────────────────────────────────────────────────────┘│
│                                                                                       │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                  RELACIONES                                           │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                       │
│  hecho_snies.año ───────────────► dim_tiempo.año                                     │
│  hecho_snies.id_categoria ──────► dim_categoria.id_categoria                         │
│  hecho_snies.codigo_ies ────────► dim_ies.codigo_ies                                 │
│  hecho_snies.id_programa ───────► dim_programa.id_programa                           │
│  hecho_snies.id_departamento ───► dim_ubicacion.id_ubicacion (tipo='departamento')   │
│  hecho_snies.id_municipio ──────► dim_ubicacion.id_ubicacion (tipo='municipio')      │
│                                                                                       │
└─────────────────────────────────────────────────────────────────────────────────────┘