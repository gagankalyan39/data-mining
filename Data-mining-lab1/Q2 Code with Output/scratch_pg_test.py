import psycopg2

try:
    conn = psycopg2.connect(dbname='postgres', user='postgres', password='1234', host='localhost')
    cur = conn.cursor()
    cur.execute("SELECT version();")
    ver = cur.fetchone()
    print("PostgreSQL Version:", ver[0])
    cur.close()
    conn.close()
except Exception as e:
    print("PostgreSQL error:", e)
