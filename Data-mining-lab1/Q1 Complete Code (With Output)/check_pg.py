import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, user='postgres', password='1234', dbname='annapurna')
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
tables = [r[0] for r in cur.fetchall()]
print('Tables in annapurna database:', tables)

for t in tables:
    cur.execute(f"SELECT count(*) FROM {t};")
    cnt = cur.fetchone()[0]
    print(f"  {t}: {cnt} rows")

conn.close()
