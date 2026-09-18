import os, glob, time
import pandas as pd
from minio import Minio
import duckdb

print("1. Testing MinIO...")
minio_client = Minio('localhost:9000', access_key='minioadmin', secret_key='minioadmin', secure=False)
bucket_name = 'setubid-lake'
if not minio_client.bucket_exists(bucket_name):
    minio_client.make_bucket(bucket_name)
    print(f"Created MinIO bucket: {bucket_name}")
else:
    print(f"MinIO bucket already exists: {bucket_name}")

# Convert CSV notices to Parquet and upload to MinIO
csv_files = sorted(glob.glob('data_2/notices/*.csv'))
os.makedirs('scratch/parquet_notices', exist_ok=True)

print(f"2. Converting {len(csv_files)} CSV notice files to Parquet and uploading to MinIO...")
for f in csv_files:
    base = os.path.basename(f).replace('.csv', '.parquet')
    parquet_path = os.path.join('scratch/parquet_notices', base)
    if not os.path.exists(parquet_path):
        df = pd.read_csv(f)
        df.to_parquet(parquet_path, index=False)
    
    # Upload to MinIO
    object_name = f"notices/{base}"
    minio_client.fput_object(bucket_name, object_name, parquet_path)

print("MinIO Upload Complete. Objects in bucket:")
for obj in minio_client.list_objects(bucket_name, prefix="notices/"):
    print(f" - {obj.object_name} ({obj.size} bytes)")

print("\n3. Testing DuckDB querying from MinIO S3...")
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

res = con.execute(f"SELECT count(*) as total_notices FROM read_parquet('s3://{bucket_name}/notices/*.parquet');").df()
print("DuckDB query over MinIO S3 result:")
print(res)

sample = con.execute(f"SELECT notice_id, portal_id, published_at, title, estimated_value FROM read_parquet('s3://{bucket_name}/notices/*.parquet') LIMIT 3;").df()
print("\nSample rows queried by DuckDB from MinIO S3:")
print(sample)
con.close()
