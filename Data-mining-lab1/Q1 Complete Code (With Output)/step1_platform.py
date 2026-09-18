"""
step1_platform.py
=================
Task a (Platform Setup):
Verifies that:
1. Object Store: MinIO is UP and reachable at localhost:9000
2. Relational Database: PostgreSQL is UP at localhost:5432 (db=annapurna, pass=1234)
   with all master tables loaded: stores, product_categories, products, price_revisions
3. Analytical Query Engine: DuckDB analytical engine is initialized and ready
"""

import sys
import duckdb
from minio import Minio
import psycopg2

def main():
    print("=" * 75)
    print("      ANNAPURNA STORES DATA PLATFORM - COMPONENT HEALTH CHECK")
    print("=" * 75)
    
    # 1. MinIO Object Store Check
    print("\n[1] CHECKING OBJECT STORE (MinIO)...")
    try:
        minio_client = Minio('localhost:9000', access_key='minioadmin', secret_key='minioadmin', secure=False)
        buckets = [b.name for b in minio_client.list_buckets()]
        print("  -> MinIO Server:      ONLINE (localhost:9000)")
        print(f"  -> Existing Buckets:  {buckets if buckets else 'None (ready to create)'}")
        print("  -> Status:            HEALTHY [PASS]")
    except Exception as e:
        print(f"  -> MinIO Error:       {e}")
        sys.exit(1)

    # 2. PostgreSQL Relational Database Check
    print("\n[2] CHECKING RELATIONAL DATABASE (PostgreSQL)...")
    try:
        pg_conn = psycopg2.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="1234",
            dbname="annapurna"
        )
        cur = pg_conn.cursor()
        print("  -> PostgreSQL Server: ONLINE (localhost:5432)")
        print("  -> Database:          annapurna")
        print("  -> Master Tables & Row Counts:")
        
        for table in ['stores', 'product_categories', 'products', 'price_revisions']:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            count = cur.fetchone()[0]
            print(f"     * {table:<20}: {count:>6,} rows")
            
        cur.close()
        pg_conn.close()
        print("  -> Status:            HEALTHY [PASS]")
    except Exception as e:
        print(f"  -> PostgreSQL Error:  {e}")
        sys.exit(1)

    # 3. DuckDB Analytical Engine Check
    print("\n[3] CHECKING ANALYTICAL ENGINE (DuckDB)...")
    try:
        con = duckdb.connect()
        ver = con.execute("SELECT version()").fetchone()[0]
        print(f"  -> DuckDB Engine:     ONLINE (version {ver})")
        print("  -> In-Memory Engine:  READY for federated analytical queries")
        print("  -> Status:            HEALTHY [PASS]")
        con.close()
    except Exception as e:
        print(f"  -> DuckDB Error:      {e}")
        sys.exit(1)

    print("\n" + "=" * 75)
    print(" ALL 3 PLATFORM TIERS ARE OPERATIONAL & VERIFIED!")
    print("=" * 75)

if __name__ == "__main__":
    main()
