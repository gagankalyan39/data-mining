"""
Step 0: Multi-Engine Lakehouse Architecture Setup
Demonstrates:
1. MinIO: S3 Object Storage for raw/partitioned notices data lake (s3://setubid-lake/notices/).
2. DuckDB: In-process analytical engine querying MinIO S3 directly via httpfs.
3. PostgreSQL: Enterprise RDBMS on localhost:5432 (pass: 1234) for indexing & bookmark state.
"""

import os, glob, time
import pandas as pd
from minio import Minio
import duckdb
import psycopg2

print("="*80)
print("STEP 0: SETUBID LAKEHOUSE & DATABASE INFRASTRUCTURE SETUP")
print("="*80)

# 1. Connect to MinIO (S3 Object Storage)
print("\n1. CONNECTING TO MINIO (S3 Lakehouse)...")
t0 = time.time()
minio_client = Minio('localhost:9000', access_key='minioadmin', secret_key='minioadmin', secure=False)
bucket_name = 'setubid-lake'
if not minio_client.bucket_exists(bucket_name):
    minio_client.make_bucket(bucket_name)
    print(f"   [MinIO] Created bucket: s3://{bucket_name}")
else:
    print(f"   [MinIO] Connected to bucket: s3://{bucket_name}")

# Ingest & upload parquet files
csv_files = sorted(glob.glob('data_2/notices/*.csv'))
os.makedirs('scratch/parquet_notices', exist_ok=True)
for f in csv_files:
    base = os.path.basename(f).replace('.csv', '.parquet')
    parquet_path = os.path.join('scratch/parquet_notices', base)
    if not os.path.exists(parquet_path):
        df = pd.read_csv(f)
        df.to_parquet(parquet_path, index=False)
    minio_client.fput_object(bucket_name, f"notices/{base}", parquet_path)

objects = list(minio_client.list_objects(bucket_name, prefix="notices/"))
total_lake_bytes = sum(o.size for o in objects)
print(f"   [MinIO] Uploaded {len(objects)} Parquet partition files ({total_lake_bytes / (1024*1024):.2f} MB total)")
print(f"   [MinIO] Status: OPERATIONAL (latency: {time.time()-t0:.2f}s)")

# 2. Connect DuckDB to MinIO
print("\n2. CONNECTING DUCKDB TO MINIO S3 LAKEHOUSE...")
t0 = time.time()
con = duckdb.connect()
con.execute("""
INSTALL httpfs;
LOAD httpfs;
SET s3_endpoint='localhost:9000';
SET s3_use_ssl=false;
SET s3_url_style='path';
SET s3_access_key_id='minioadmin';
SET s3_secret_access_key='minioadmin';
""")
duck_count = con.execute(f"SELECT count(*) FROM read_parquet('s3://{bucket_name}/notices/*.parquet');").fetchone()[0]
portal_count = con.execute(f"SELECT count(distinct portal_id) FROM read_parquet('s3://{bucket_name}/notices/*.parquet');").fetchone()[0]
print(f"   [DuckDB] Query: SELECT count(*) FROM read_parquet('s3://{bucket_name}/notices/*.parquet')")
print(f"   [DuckDB] Total Notices in S3: {duck_count:,}")
print(f"   [DuckDB] Total Portals in S3: {portal_count}")
print(f"   [DuckDB] Status: OPERATIONAL (query latency: {time.time()-t0:.2f}s)")
con.close()

# 3. Connect to PostgreSQL
print("\n3. CONNECTING TO POSTGRESQL (Relational Store & Index Host)...")
t0 = time.time()
pg_conn = psycopg2.connect(dbname='postgres', user='postgres', password='1234', host='localhost', port=5432)
pg_cur = pg_conn.cursor()
pg_cur.execute("SELECT version();")
pg_ver = pg_cur.fetchone()[0]
print(f"   [PostgreSQL] Connected: {pg_ver.split(',')[0]}")
print(f"   [PostgreSQL] Connection: localhost:5432 / DB: postgres / User: postgres / Password: (verified)")
print(f"   [PostgreSQL] Status: OPERATIONAL (latency: {time.time()-t0:.2f}s)")
pg_cur.close()
pg_conn.close()

print("\n" + "="*80)
print("INFRASTRUCTURE VERIFICATION SUMMARY:")
print("  - Storage Layer:    MinIO S3 Bucket (s3://setubid-lake/notices/*.parquet)")
print("  - Query Engine:     DuckDB (Zero-copy in-process analytical query engine)")
print("  - Relational Layer: PostgreSQL 18 (B-Tree indexed retrieval & ACID bookmark state)")
print("All 3 systems integrated and ready for deduplication workload.")
print("="*80)
