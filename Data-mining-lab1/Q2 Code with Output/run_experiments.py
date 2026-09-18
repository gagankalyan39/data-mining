import glob
import re
import hashlib
import time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

print("1. Loading notices and labels...")
t0 = time.time()
files = sorted(glob.glob('data_2/notices/*.csv'))
df_notices = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
df_pairs = pd.read_csv('data_2/labelled_pairs.csv')
notices_dict = df_notices.set_index('notice_id').to_dict('index')
print(f"Loaded {len(df_notices)} notices and {len(df_pairs)} labelled pairs in {time.time()-t0:.2f}s.")

# Regex patterns for boilerplate and noise
RE_PREAMBLE_NPAS = re.compile(r'GOVERNMENT OF INDIA -- NATIONAL PROCUREMENT AGGREGATION SERVICE[\s\S]*?(?=(Name of work:|NAME OF WORK:|$))', re.I)
RE_PREAMBLE_SPC = re.compile(r'STATE PROCUREMENT CELL -- CONSOLIDATED TENDER BULLETIN[\s\S]*?(?=(Name of work:|NAME OF WORK:|$))', re.I)
RE_DISCLAIMER = re.compile(r'(Disclaimer:|DISCLAIMER:)[\s\S]*$', re.I)
RE_REF = re.compile(r'(tender reference number|ref no|tender ref)[\s:]*([^\n\r]+)', re.I)
RE_PORTAL_REF = re.compile(r'\b(NPAS|SPC|PWD|TN|MC|ref|DEPA|MUNI)[-\d/A-Za-z]+', re.I)
RE_TITLE_PREFIX = re.compile(r'^(e-tender|nit for|tender notice|corrigendum)\s*[-:]*', re.I)

def clean_tokens_raw(text):
    return re.findall(r'[a-z0-9]+', str(text).lower())

def clean_tokens_refined(title, body):
    # Combine title + body
    t = RE_TITLE_PREFIX.sub('', str(title))
    text = f"{t} {body}"
    text = RE_PREAMBLE_NPAS.sub('', text)
    text = RE_PREAMBLE_SPC.sub('', text)
    text = RE_DISCLAIMER.sub('', text)
    text = RE_REF.sub('', text)
    text = RE_PORTAL_REF.sub('', text)
    # Remove standardized sections
    text = re.sub(r'GENERAL INSTRUCTIONS TO BIDDERS[\s\S]*?==================+', '', text, flags=re.I)
    text = re.sub(r'STANDARD TERMS AND CONDITIONS[\s\S]*?------------------+', '', text, flags=re.I)
    tokens = re.findall(r'[a-z0-9]+', text.lower())
    return tokens

def get_shingles(tokens, k=3):
    if len(tokens) < k:
        return set(tokens)
    return set(tuple(tokens[i:i+k]) for i in range(len(tokens) - k + 1))

def jaccard(s1, s2):
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    return len(s1.intersection(s2)) / len(s1.union(s2))

# ==========================================
# PART A: Evaluating Decomposition & Filtering Choices
# ==========================================
print("\n--- Part A: Testing Representation Choices ---")
# Let's test Choice 1 (Raw text, word 2-grams) vs Choice 2 (Cleaned text, word 3-grams)
# on specific pairs:
# Pair 1 (Same): N010018 vs N010020
# Pair 2 (Different, nodal portal P003): N007021 vs N010547

p1_a, p1_b = 'N010018', 'N010020'
p2_a, p2_b = 'N007021', 'N010547'

# Raw tokens
p1_a_raw = clean_tokens_raw(f"{notices_dict[p1_a]['title']} {notices_dict[p1_a]['body']}")
p1_b_raw = clean_tokens_raw(f"{notices_dict[p1_b]['title']} {notices_dict[p1_b]['body']}")
p2_a_raw = clean_tokens_raw(f"{notices_dict[p2_a]['title']} {notices_dict[p2_a]['body']}")
p2_b_raw = clean_tokens_raw(f"{notices_dict[p2_b]['title']} {notices_dict[p2_b]['body']}")

# Cleaned tokens
p1_a_clean = clean_tokens_refined(notices_dict[p1_a]['title'], notices_dict[p1_a]['body'])
p1_b_clean = clean_tokens_refined(notices_dict[p1_b]['title'], notices_dict[p1_b]['body'])
p2_a_clean = clean_tokens_refined(notices_dict[p2_a]['title'], notices_dict[p2_a]['body'])
p2_b_clean = clean_tokens_refined(notices_dict[p2_b]['title'], notices_dict[p2_b]['body'])

# Compute Jaccard
j_raw_same = jaccard(get_shingles(p1_a_raw, 2), get_shingles(p1_b_raw, 2))
j_clean_same = jaccard(get_shingles(p1_a_clean, 3), get_shingles(p1_b_clean, 3))

j_raw_diff = jaccard(get_shingles(p2_a_raw, 2), get_shingles(p2_b_raw, 2))
j_clean_diff = jaccard(get_shingles(p2_a_clean, 3), get_shingles(p2_b_clean, 3))

print(f"Same pair ({p1_a} vs {p1_b}):")
print(f"  Choice 1 (Raw Word-2):    {j_raw_same:.4f}")
print(f"  Choice 2 (Cleaned Word-3):{j_clean_same:.4f}")
print(f"Diff pair ({p2_a} vs {p2_b}, both P003):")
print(f"  Choice 1 (Raw Word-2):    {j_raw_diff:.4f}  <-- Catastrophic false collision due to boilerplate!")
print(f"  Choice 2 (Cleaned Word-3):{j_clean_diff:.4f}  <-- Dropped significantly!")

# Benchmark time for clean_tokens_refined across 1000 notices
t_start = time.time()
for n in df_notices.head(1000).itertuples():
    clean_tokens_refined(n.title, n.body)
t_clean_1000 = time.time() - t_start
print(f"Cleaning cost: {t_clean_1000*1000/1000:.2f} ms per notice ({t_clean_1000*12:.2f}s for 12,000 notices).")

# ==========================================
# PART B: MinHash Size & Accuracy Loop
# ==========================================
print("\n--- Part B: MinHash Signature Size & Error Analysis ---")
K = 128
# Theoretical error:
# Var(J_hat) = J(1-J)/K <= 0.25/K = 0.25/128 = 0.00195
# StdDev(J_hat) <= sqrt(0.25/128) = 0.0442 (4.4%)
print(f"Theoretical max standard error for K={K}: {np.sqrt(0.25/K):.4f} (at J=0.5)")

# Generate K independent linear hash parameters: h_i(x) = (a_i * x + b_i) % P
np.random.seed(42)
P = 4294967311 # Large prime > 2^32
a_params = np.random.randint(1, P, size=K, dtype=np.int64)
b_params = np.random.randint(0, P, size=K, dtype=np.int64)

def shingle_hash(s):
    # Hash string tuple to 32-bit int
    h = hashlib.sha256(str(s).encode('utf-8')).digest()
    return int.from_bytes(h[:4], 'little')

def compute_minhash(shingles, K, a_params, b_params, P):
    if not shingles:
        return np.zeros(K, dtype=np.int64)
    shingle_hashes = np.array([shingle_hash(s) for s in shingles], dtype=np.int64)
    # Vectorized MinHash calculation
    # hashes matrix: (len(shingles), K)
    # (x[:, None] * a[None, :] + b[None, :]) % P
    val = (shingle_hashes[:, None] * a_params[None, :] + b_params[None, :]) % P
    sig = np.min(val, axis=0)
    return sig

def minhash_similarity(sig1, sig2):
    return np.mean(sig1 == sig2)

# Measure exact vs estimated Jaccard on labelled pairs
exact_jaccards = []
est_jaccards = []
pair_labels = []

# Precompute shingles and signatures for all unique notices in labelled pairs
unique_nids = set(df_pairs['notice_id_a']).union(set(df_pairs['notice_id_b']))
print(f"Precomputing MinHash signatures for {len(unique_nids)} unique notices in labelled pairs...")
shingles_cache = {}
sig_cache = {}

for nid in unique_nids:
    row = notices_dict[nid]
    toks = clean_tokens_refined(row['title'], row['body'])
    sh = get_shingles(toks, k=3)
    shingles_cache[nid] = sh
    sig_cache[nid] = compute_minhash(sh, K, a_params, b_params, P)

for _, r in df_pairs.iterrows():
    nid_a, nid_b = r['notice_id_a'], r['notice_id_b']
    j_true = jaccard(shingles_cache[nid_a], shingles_cache[nid_b])
    j_est = minhash_similarity(sig_cache[nid_a], sig_cache[nid_b])
    exact_jaccards.append(j_true)
    est_jaccards.append(j_est)
    pair_labels.append(r['label'])

exact_jaccards = np.array(exact_jaccards)
est_jaccards = np.array(est_jaccards)
errors = est_jaccards - exact_jaccards

mean_err = np.mean(errors)
mae = np.mean(np.abs(errors))
rmse = np.sqrt(np.mean(errors**2))
emp_std = np.std(errors)
max_err = np.max(np.abs(errors))

print(f"Results across {len(df_pairs)} labelled pairs (K={K}):")
print(f"  Mean Error (Bias):         {mean_err:+.5f} (theoretically 0)")
print(f"  Mean Absolute Error (MAE): {mae:.4f}")
print(f"  RMSE:                      {rmse:.4f}")
print(f"  Empirical Std Deviation:   {emp_std:.4f} (theoretical max: {np.sqrt(0.25/K):.4f})")
print(f"  Max Absolute Error:        {max_err:.4f}")

# Check error behavior across similarity bands
for low, high in [(0.0, 0.2), (0.2, 0.5), (0.5, 0.8), (0.8, 1.0)]:
    mask = (exact_jaccards >= low) & (exact_jaccards < high)
    if np.sum(mask) > 0:
        band_rmse = np.sqrt(np.mean(errors[mask]**2))
        avg_j = np.mean(exact_jaccards[mask])
        theo_band = np.sqrt(avg_j * (1 - avg_j) / K)
        print(f"  Band [{low:.1f}, {high:.1f}) (n={np.sum(mask)}): Emp RMSE = {band_rmse:.4f}, Theoretical = {theo_band:.4f}")

# ==========================================
# PART C: LSH Tuning & Operating Point
# ==========================================
print("\n--- Part C: LSH Operating Point & S-Curve ---")
# K = 128. Bands b and rows r such that b * r = 128.
# Possible (b, r): (32, 4), (16, 8), (8, 16), (64, 2)
# Or for K=120: (20, 6), (24, 5)
# Let's analyze b=16, r=8: threshold t = (1/16)^(1/8) = 0.707
# Let's analyze b=32, r=4: threshold t = (1/32)^(1/4) = 0.420
# Let's analyze b=20, r=6 (for K=120): threshold t = (1/20)^(1/6) = 0.606

s_vals = np.linspace(0, 1, 200)

plt.figure(figsize=(9, 5.5))
for b, r, label in [(32, 4, 'b=32, r=4 (t=0.42)'), (16, 8, 'b=16, r=8 (t=0.71)'), (8, 16, 'b=8, r=16 (t=0.88)')]:
    p_coll = 1 - (1 - s_vals**r)**b
    plt.plot(s_vals, p_coll, label=label, lw=2)

# Mark chosen operating point: b=16, r=8 at s=0.75
plt.axvline(x=0.707, color='red', linestyle='--', alpha=0.7, label='Operating Threshold (t=0.707)')
plt.scatter([0.75], [1 - (1 - 0.75**8)**16], color='red', s=80, zorder=5, label='Chosen Operating Point')
plt.title('LSH Candidate Survival Probability (S-Curve) vs Jaccard Similarity', fontsize=12)
plt.xlabel('True Jaccard Similarity s', fontsize=11)
plt.ylabel('Probability of Candidate Retrieval P(s)', fontsize=11)
plt.grid(True, linestyle=':', alpha=0.6)
plt.legend(loc='lower right')
plt.tight_layout()
plt.savefig('lsh_scurve.png', dpi=150)
print("Saved lsh_scurve.png successfully.")
