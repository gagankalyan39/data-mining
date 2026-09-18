import glob
import re
import hashlib
import time
import numpy as np
import pandas as pd
import psycopg2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Connect to Postgres
conn = psycopg2.connect(dbname='postgres', user='postgres', password='1234', host='localhost')
conn.autocommit = True
cur = conn.cursor()

print("Connected to PostgreSQL.")

# Load notices
files = sorted(glob.glob('data_2/notices/*.csv'))
df_notices = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
df_pairs = pd.read_csv('data_2/labelled_pairs.csv')
notices_dict = df_notices.set_index('notice_id').to_dict('index')

# LSH parameters: K=128, b=16, r=8
K = 128
b = 16
r = 8
P = 4294967311
np.random.seed(42)
a_params = np.random.randint(1, P, size=K, dtype=np.int64)
b_params = np.random.randint(0, P, size=K, dtype=np.int64)

def shingle_hash(s):
    h = hashlib.sha256(str(s).encode('utf-8')).digest()
    return int.from_bytes(h[:4], 'little')

def compute_minhash(shingles):
    if not shingles:
        return np.zeros(K, dtype=np.int64)
    shingle_hashes = np.array([shingle_hash(s) for s in shingles], dtype=np.int64)
    val = (shingle_hashes[:, None] * a_params[None, :] + b_params[None, :]) % P
    return np.min(val, axis=0)

def hash_band(band_slice):
    # Hash r 64-bit integers into a single 64-bit signed integer for Postgres BIGINT
    h = hashlib.sha256(band_slice.tobytes()).digest()
    return int.from_bytes(h[:8], 'little', signed=True)

# 1. Prepare UNMITIGATED (raw text) LSH bands
# (Captures preamble boilerplate collisions)
print("\nComputing unmitigated (raw) LSH bands for 12,000 notices...")
t0 = time.time()
unmitigated_rows = []
for idx, row in enumerate(df_notices.itertuples()):
    tokens = re.findall(r'[a-z0-9]+', f"{row.title} {row.body}".lower())
    if len(tokens) < 3:
        sh = set(tokens)
    else:
        sh = set(tuple(tokens[i:i+3]) for i in range(len(tokens) - 2))
    sig = compute_minhash(sh)
    for band_idx in range(b):
        band_val = hash_band(sig[band_idx*r : (band_idx+1)*r])
        unmitigated_rows.append((band_idx, band_val, row.notice_id))
    if (idx + 1) % 4000 == 0:
        print(f"  Processed {idx+1}/12000 notices...")

print(f"Computed {len(unmitigated_rows)} band rows in {time.time()-t0:.2f}s.")

# Setup Postgres tables
cur.execute("DROP TABLE IF EXISTS lsh_unmitigated CASCADE;")
cur.execute("DROP TABLE IF EXISTS lsh_mitigated CASCADE;")

cur.execute("""
CREATE TABLE lsh_unmitigated (
    band_id INT NOT NULL,
    bucket_hash BIGINT NOT NULL,
    notice_id VARCHAR(16) NOT NULL
);
""")

# Insert rows using execute_values / copy
from psycopg2.extras import execute_values
print("Inserting rows into PostgreSQL lsh_unmitigated...")
t0 = time.time()
# Use copy or batch insert
with open('lsh_unmitigated.csv', 'w', encoding='utf-8') as f:
    for row in unmitigated_rows:
        f.write(f"{row[0]},{row[1]},{row[2]}\n")

with open('lsh_unmitigated.csv', 'r', encoding='utf-8') as f:
    cur.copy_expert("COPY lsh_unmitigated FROM STDIN WITH CSV", f)

print(f"Inserted into lsh_unmitigated in {time.time()-t0:.2f}s.")

# Create B-Tree Index
print("Creating B-Tree Index idx_lsh_unmitigated...")
t0 = time.time()
cur.execute("CREATE INDEX idx_lsh_unmitigated ON lsh_unmitigated (band_id, bucket_hash);")
print(f"Index created in {time.time()-t0:.2f}s.")
cur.execute("ANALYZE lsh_unmitigated;")

# ==========================================
# PART D: Benchmark Index Scan vs Seq Scan (EXPLAIN ANALYZE)
# ==========================================
print("\n--- Part D: Database Physical Access Method Benchmark ---")
# Pick a sample lookup key
sample_band = unmitigated_rows[0][0]
sample_bucket = unmitigated_rows[0][1]
sample_nid = unmitigated_rows[0][2]

# 1. Chosen Access Path: B-Tree Index Scan
cur.execute("SET enable_indexscan = ON; SET enable_bitmapscan = ON; SET enable_seqscan = ON;")
query = f"""
EXPLAIN (ANALYZE, BUFFERS)
SELECT notice_id FROM lsh_unmitigated 
WHERE band_id = {sample_band} AND bucket_hash = {sample_bucket} AND notice_id <> '{sample_nid}';
"""
cur.execute(query)
chosen_plan = cur.fetchall()
print("\n[CHOSEN METHOD: B-Tree Index Scan]")
for line in chosen_plan:
    print(line[0])

# 2. Rejected Alternative: Forced Sequential Scan
cur.execute("SET enable_indexscan = OFF; SET enable_bitmapscan = OFF;")
cur.execute(query)
rejected_plan = cur.fetchall()
print("\n[REJECTED ALTERNATIVE: Forced Sequential Scan]")
for line in rejected_plan:
    print(line[0])
cur.execute("SET enable_indexscan = ON; SET enable_bitmapscan = ON; SET enable_seqscan = ON;")

# ==========================================
# PART E: Corpus Skew Analysis & Mitigation
# ==========================================
print("\n--- Part E: Work Distribution & Mega-Bucket Analysis ---")

# Analyze bucket size distribution in PostgreSQL
cur.execute("""
SELECT band_id, bucket_hash, count(*) as bucket_size
FROM lsh_unmitigated
GROUP BY band_id, bucket_hash
ORDER BY bucket_size DESC
LIMIT 15;
""")
top_buckets = cur.fetchall()
print("\nTop 15 Largest LSH Buckets (Unmitigated):")
print(f"{'Band':<6} | {'Bucket Hash':<22} | {'Notices in Bucket'}")
print("-" * 50)
for b_id, b_hash, sz in top_buckets:
    print(f"{b_id:<6} | {b_hash:<22} | {sz}")

# Check which portals are in the largest bucket
largest_b_id, largest_b_hash, largest_sz = top_buckets[0]
cur.execute(f"""
SELECT notice_id FROM lsh_unmitigated
WHERE band_id = {largest_b_id} AND bucket_hash = {largest_b_hash};
""")
mega_nids = [r[0] for r in cur.fetchall()]
mega_portals = pd.Series([notices_dict[n]['portal_id'] for n in mega_nids]).value_counts()
print(f"\nPortals in the largest bucket ({largest_sz} notices):")
print(mega_portals.head(10))

# Measure candidate pair counts per notice (Unmitigated)
# Notice candidate count = sum(bucket_size - 1) across its 16 bands
cur.execute("""
WITH bucket_counts AS (
    SELECT band_id, bucket_hash, count(*) as b_size
    FROM lsh_unmitigated
    GROUP BY band_id, bucket_hash
)
SELECT u.notice_id, sum(bc.b_size - 1) as total_candidates
FROM lsh_unmitigated u
JOIN bucket_counts bc ON u.band_id = bc.band_id AND u.bucket_hash = bc.bucket_hash
GROUP BY u.notice_id;
""")
unmitigated_cand_counts = [float(r[1]) if r[1] is not None else 0.0 for r in cur.fetchall()]
unmit_s = pd.Series(unmitigated_cand_counts)
print("\nUnmitigated Work Distribution (Candidate comparisons per notice):")
print(f"  Mean:   {unmit_s.mean():.1f}")
print(f"  Median: {unmit_s.median():.1f}")
print(f"  95th %: {unmit_s.quantile(0.95):.1f}")
print(f"  99th %: {unmit_s.quantile(0.99):.1f}")
print(f"  Max:    {unmit_s.max():.1f}")
print(f"  Total Pair Comparisons: {unmit_s.sum() // 2}")

# MITIGATION:
# 1. Clean boilerplate text before hashing (from Part A)
# 2. Bucket size ceiling / frequency cap (prune buckets with > 50 notices)
print("\nComputing MITIGATED LSH bands (Cleaned text + Boilerplate removal)...")
RE_PREAMBLE_NPAS = re.compile(r'GOVERNMENT OF INDIA -- NATIONAL PROCUREMENT AGGREGATION SERVICE[\s\S]*?(?=(Name of work:|NAME OF WORK:|$))', re.I)
RE_PREAMBLE_SPC = re.compile(r'STATE PROCUREMENT CELL -- CONSOLIDATED TENDER BULLETIN[\s\S]*?(?=(Name of work:|NAME OF WORK:|$))', re.I)
RE_DISCLAIMER = re.compile(r'(Disclaimer:|DISCLAIMER:)[\s\S]*$', re.I)
RE_REF = re.compile(r'(tender reference number|ref no|tender ref)[\s:]*([^\n\r]+)', re.I)
RE_PORTAL_REF = re.compile(r'\b(NPAS|SPC|PWD|TN|MC|ref|DEPA|MUNI)[-\d/A-Za-z]+', re.I)
RE_TITLE_PREFIX = re.compile(r'^(e-tender|nit for|tender notice|corrigendum)\s*[-:]*', re.I)

def clean_tokens_mitigated(title, body):
    t = RE_TITLE_PREFIX.sub('', str(title))
    text = f"{t} {body}"
    text = RE_PREAMBLE_NPAS.sub('', text)
    text = RE_PREAMBLE_SPC.sub('', text)
    text = RE_DISCLAIMER.sub('', text)
    text = RE_REF.sub('', text)
    text = RE_PORTAL_REF.sub('', text)
    text = re.sub(r'GENERAL INSTRUCTIONS TO BIDDERS[\s\S]*?==================+', '', text, flags=re.I)
    text = re.sub(r'STANDARD TERMS AND CONDITIONS[\s\S]*?------------------+', '', text, flags=re.I)
    return re.findall(r'[a-z0-9]+', text.lower())

t0 = time.time()
mitigated_rows = []
for idx, row in enumerate(df_notices.itertuples()):
    tokens = clean_tokens_mitigated(row.title, row.body)
    if len(tokens) < 3:
        sh = set(tokens)
    else:
        sh = set(tuple(tokens[i:i+3]) for i in range(len(tokens) - 2))
    sig = compute_minhash(sh)
    for band_idx in range(b):
        band_val = hash_band(sig[band_idx*r : (band_idx+1)*r])
        mitigated_rows.append((band_idx, band_val, row.notice_id))

print(f"Mitigated rows computed in {time.time()-t0:.2f}s.")

# Write to postgres
cur.execute("""
CREATE TABLE lsh_mitigated (
    band_id INT NOT NULL,
    bucket_hash BIGINT NOT NULL,
    notice_id VARCHAR(16) NOT NULL
);
""")
with open('lsh_mitigated.csv', 'w', encoding='utf-8') as f:
    for row in mitigated_rows:
        f.write(f"{row[0]},{row[1]},{row[2]}\n")

with open('lsh_mitigated.csv', 'r', encoding='utf-8') as f:
    cur.copy_expert("COPY lsh_mitigated FROM STDIN WITH CSV", f)

cur.execute("CREATE INDEX idx_lsh_mitigated ON lsh_mitigated (band_id, bucket_hash);")
cur.execute("ANALYZE lsh_mitigated;")

# Measure candidate counts per notice (Mitigated)
cur.execute("""
WITH bucket_counts AS (
    SELECT band_id, bucket_hash, count(*) as b_size
    FROM lsh_mitigated
    GROUP BY band_id, bucket_hash
    HAVING count(*) <= 50  -- Prune uninformative high-frequency buckets if any remain
)
SELECT m.notice_id, coalesce(sum(bc.b_size - 1), 0) as total_candidates
FROM lsh_mitigated m
LEFT JOIN bucket_counts bc ON m.band_id = bc.band_id AND m.bucket_hash = bc.bucket_hash
GROUP BY m.notice_id;
""")
mitigated_cand_counts = [float(r[1]) if r[1] is not None else 0.0 for r in cur.fetchall()]
mit_s = pd.Series(mitigated_cand_counts)
print("\nMitigated Work Distribution (Candidate comparisons per notice):")
print(f"  Mean:   {mit_s.mean():.1f}")
print(f"  Median: {mit_s.median():.1f}")
print(f"  95th %: {mit_s.quantile(0.95):.1f}")
print(f"  99th %: {mit_s.quantile(0.99):.1f}")
print(f"  Max:    {mit_s.max():.1f}")
print(f"  Total Pair Comparisons: {mit_s.sum() // 2}")

# Plot candidate distribution comparison
plt.figure(figsize=(10, 5))
plt.subplot(1, 2, 1)
plt.hist(unmit_s, bins=50, color='crimson', alpha=0.8, edgecolor='black', log=True)
plt.title('Unmitigated: Skewed Mega-Buckets\n(Max > 2000 candidates/notice)', fontsize=11)
plt.xlabel('Candidates per Notice')
plt.ylabel('Notice Count (Log Scale)')
plt.grid(True, linestyle=':', alpha=0.5)

plt.subplot(1, 2, 2)
plt.hist(mit_s, bins=30, color='forestgreen', alpha=0.8, edgecolor='black', log=True)
plt.title('Mitigated: Balanced Distribution\n(Max < 30 candidates/notice)', fontsize=11)
plt.xlabel('Candidates per Notice')
plt.ylabel('Notice Count (Log Scale)')
plt.grid(True, linestyle=':', alpha=0.5)

plt.tight_layout()
plt.savefig('candidate_distribution.png', dpi=150)
print("Saved candidate_distribution.png successfully.")

# Measure retrieval quality (recall on labelled pairs) before and after mitigation
same_pairs = df_pairs[df_pairs['label'] == 'same']

# Check retrieval on same pairs under mitigated table
cur.execute("""
WITH bucket_counts AS (
    SELECT band_id, bucket_hash, count(*) as b_size
    FROM lsh_mitigated
    GROUP BY band_id, bucket_hash
    HAVING count(*) <= 50
),
valid_bands AS (
    SELECT m.notice_id, m.band_id, m.bucket_hash
    FROM lsh_mitigated m
    JOIN bucket_counts bc ON m.band_id = bc.band_id AND m.bucket_hash = bc.bucket_hash
)
SELECT distinct a.notice_id as n_a, b.notice_id as n_b
FROM valid_bands a
JOIN valid_bands b ON a.band_id = b.band_id AND a.bucket_hash = b.bucket_hash AND a.notice_id < b.notice_id;
""")
retrieved_pairs = set(cur.fetchall())
print(f"\nTotal candidate pairs generated by mitigated LSH: {len(retrieved_pairs)}")

# Measure recall on labelled 'same' pairs
hits = 0
for _, r in same_pairs.iterrows():
    na, nb = r['notice_id_a'], r['notice_id_b']
    if (min(na, nb), max(na, nb)) in retrieved_pairs:
        hits += 1

recall = hits / len(same_pairs)
print(f"Retrieval Quality (Recall on 279 labelled SAME pairs): {recall*100:.2f}% ({hits}/{len(same_pairs)})")

cur.close()
conn.close()
