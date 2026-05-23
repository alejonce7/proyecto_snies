# database/schema.py
import duckdb
from pathlib import Path

DB_PATH = Path("./data/database/snies.duckdb")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def conectar_db():
    return duckdb.connect(str(DB_PATH))

def crear_esquema():
    conn = conectar_db()

    # 1. DIMENSION TIEMPO
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dim_tiempo (
            año INTEGER PRIMARY KEY
        )
    """)

    # 2. DIMENSION CATEGORIA
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dim_categoria (
            id_categoria INTEGER PRIMARY KEY,
            nombre VARCHAR(50) UNIQUE NOT NULL,
            descripcion VARCHAR(255),
            unidad_medida VARCHAR(50)
        )
    """)

    # 3. DIMENSION IES
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dim_ies (
            codigo_ies VARCHAR(20) PRIMARY KEY,
            nombre_ies VARCHAR(255) NOT NULL,
            ies_padre VARCHAR(20),
            sector VARCHAR(50),
            caracter VARCHAR(50),
            metodologia VARCHAR(50),
            principal_seccional VARCHAR(20),
            estado VARCHAR(20) DEFAULT 'ACTIVO'
        )
    """)

    # 4. DIMENSION PROGRAMA
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dim_programa (
            id_programa VARCHAR(50) PRIMARY KEY,
            codigo_ies VARCHAR(20),
            nombre_programa VARCHAR(255),
            nivel_academico VARCHAR(100),
            codigo_snies VARCHAR(20),
            FOREIGN KEY (codigo_ies) REFERENCES dim_ies(codigo_ies)
        )
    """)

    # 5. DIMENSION UBICACION
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dim_ubicacion (
            id_ubicacion VARCHAR(20) PRIMARY KEY,
            tipo VARCHAR(20) CHECK (tipo IN ('departamento', 'municipio')),
            codigo_dane VARCHAR(20),
            nombre VARCHAR(255),
            codigo_departamento VARCHAR(20),
            nombre_departamento VARCHAR(255)
        )
    """)

    # 6. TABLA DE HECHOS
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hecho_snies (
            id_hecho BIGINT PRIMARY KEY,
            año INTEGER NOT NULL,
            id_categoria INTEGER NOT NULL,
            codigo_ies VARCHAR(20) NOT NULL,
            id_programa VARCHAR(50),
            id_departamento VARCHAR(20),
            id_municipio VARCHAR(20),
            valor_numerico DECIMAL(20,2),
            texto_adicional TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (año) REFERENCES dim_tiempo(año),
            FOREIGN KEY (id_categoria) REFERENCES dim_categoria(id_categoria),
            FOREIGN KEY (codigo_ies) REFERENCES dim_ies(codigo_ies),
            FOREIGN KEY (id_programa) REFERENCES dim_programa(id_programa),
            FOREIGN KEY (id_departamento) REFERENCES dim_ubicacion(id_ubicacion),
            FOREIGN KEY (id_municipio) REFERENCES dim_ubicacion(id_ubicacion)
        )
    """)

    # Indices
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hecho_año ON hecho_snies(año)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hecho_categoria ON hecho_snies(id_categoria)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hecho_ies ON hecho_snies(codigo_ies)")

    # Poblar dim_categoria
    conn.execute("""
        INSERT OR IGNORE INTO dim_categoria (id_categoria, nombre, descripcion, unidad_medida) VALUES
        (1, 'inscritos', 'Estudiantes que se inscribieron en educacion superior', 'numero de personas'),
        (2, 'admitidos', 'Estudiantes admitidos en educacion superior', 'numero de personas'),
        (3, 'matriculados', 'Estudiantes matriculados en educacion superior', 'numero de personas'),
        (4, 'primer_curso', 'Estudiantes matriculados en primer curso', 'numero de personas'),
        (5, 'graduados', 'Estudiantes graduados en educacion superior', 'numero de personas'),
        (6, 'docentes', 'Personal docente en IES', 'numero de personas'),
        (7, 'administrativos', 'Personal administrativo en IES', 'numero de personas')
    """)

    # Poblar dim_tiempo (2000-2030)
    for año in range(2000, 2031):
        conn.execute("INSERT OR IGNORE INTO dim_tiempo (año) VALUES (?)", [año])

    conn.close()
    print("Esquema de base de datos creado exitosamente")

def verificar_esquema():
    conn = conectar_db()

    tablas = conn.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY table_name
    """).fetchall()

    print("\nTablas en la base de datos:")
    for (tabla,) in tablas:
        count = conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
        print(f"  {tabla}: {count} registros")

    conn.close()

def resetear_esquema():
    conn = conectar_db()
    tablas = ["hecho_snies", "dim_programa", "dim_ies", "dim_ubicacion", "dim_categoria", "dim_tiempo"]
    for t in tablas:
        conn.execute(f"DROP TABLE IF EXISTS {t}")
    conn.close()
    print("Esquema eliminado")
    crear_esquema()

if __name__ == "__main__":
    crear_esquema()
    verificar_esquema()