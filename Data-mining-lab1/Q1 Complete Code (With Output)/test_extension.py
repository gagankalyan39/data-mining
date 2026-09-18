import duckdb

con = duckdb.connect()
try:
    con.install_extension('postgres')
    con.load_extension('postgres')
    con.execute("ATTACH 'host=localhost port=5432 user=postgres password=1234 dbname=annapurna' AS pg (TYPE POSTGRES, READ_ONLY);")
    print('SUCCESS: DuckDB attached to PostgreSQL directly!')
    cnt = con.execute("SELECT count(*) FROM pg.stores").fetchone()[0]
    print(f"pg.stores count = {cnt}")
except Exception as e:
    print('Error:', e)
