import duckdb

conn = duckdb.connect('data/dataset/snies.duckdb', read_only=True)

# Tablas
tablas = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()
print("TABLAS:")
for t in tablas:
    count = conn.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
    print(f"  {t[0]}: {count} registros")

print("\n--- dim_categoria ---")
print(conn.execute("SELECT * FROM dim_categoria").df())

print("\n--- Rango de años ---")
print(conn.execute("SELECT MIN(año), MAX(año) FROM hecho_snies").df())

print("\n--- Hechos por categoria ---")
print(conn.execute("SELECT id_categoria, COUNT(*) as registros, SUM(valor_numerico) as total FROM hecho_snies GROUP BY id_categoria ORDER BY id_categoria").df())

print("\n--- IES unicas ---")
print(conn.execute("SELECT COUNT(DISTINCT codigo_ies) as ies_unicas FROM dim_ies").df())

print("\n--- Años disponibles ---")
print(conn.execute("SELECT DISTINCT año FROM hecho_snies ORDER BY año").df())

print("\n--- Muestra hecho_snies ---")
print(conn.execute("SELECT * FROM hecho_snies LIMIT 5").df())

print("\n--- dim_ies muestra ---")
print(conn.execute("SELECT * FROM dim_ies LIMIT 5").df())

print("\n--- dim_ubicacion muestra ---")
print(conn.execute("SELECT * FROM dim_ubicacion LIMIT 5").df())

print("\n--- dim_programa count ---")
print(conn.execute("SELECT COUNT(*) FROM dim_programa").df())

conn.close()
