import glob, re
import numpy as np, pandas as pd
from scratch_tune_k import clean_tokens, get_shingles, jaccard

files = sorted(glob.glob('data_2/notices/*.csv'))
df_notices = pd.concat([pd.read_csv(f) for f in files], ignore_index=True).set_index('notice_id')
df_pairs = pd.read_csv('data_2/labelled_pairs.csv')
same_pairs = df_pairs[df_pairs['label'] == 'same']
diff_pairs = df_pairs[df_pairs['label'] == 'different']

# Let's test Title Jaccard vs Head Jaccard vs Full Jaccard
print("Evaluating Title vs Full Body Jaccard on SAME pairs (n=279):")
title_j_same = []
head_j_same = []
containment_same = []
est_val_match = []

for _, r in same_pairs.iterrows():
    na, nb = r['notice_id_a'], r['notice_id_b']
    a, b = df_notices.loc[na], df_notices.loc[nb]
    
    # Title clean tokens
    t_a = clean_tokens(a['title'], "")
    t_b = clean_tokens(b['title'], "")
    s_t_a = get_shingles(t_a, 2)
    s_t_b = get_shingles(t_b, 2)
    j_title = jaccard(s_t_a, s_t_b)
    title_j_same.append(j_title)
    
    # Head tokens (first 1500 chars)
    h_a = clean_tokens(a['title'], a['body'][:1500])
    h_b = clean_tokens(b['title'], b['body'][:1500])
    s_h_a = get_shingles(h_a, 2)
    s_h_b = get_shingles(h_b, 2)
    head_j_same.append(jaccard(s_h_a, s_h_b))
    
    # Containment: len(A cap B) / min(len(A), len(B))
    c = len(s_h_a.intersection(s_h_b)) / min(len(s_h_a), len(s_h_b)) if min(len(s_h_a), len(s_h_b)) > 0 else 0
    containment_same.append(c)
    
    est_val_match.append(a['estimated_value'] == b['estimated_value'])

title_j_same = np.array(title_j_same)
head_j_same = np.array(head_j_same)
containment_same = np.array(containment_same)

print(f"Title Word-2 Jaccard: min={title_j_same.min():.3f}, 10th%={np.percentile(title_j_same, 10):.3f}, median={np.median(title_j_same):.3f}, max={title_j_same.max():.3f}")
print(f"Head Word-2 Jaccard:  min={head_j_same.min():.3f}, 10th%={np.percentile(head_j_same, 10):.3f}, median={np.median(head_j_same):.3f}, max={head_j_same.max():.3f}")
print(f"Containment:         min={containment_same.min():.3f}, 10th%={np.percentile(containment_same, 10):.3f}, median={np.median(containment_same):.3f}, max={containment_same.max():.3f}")
print(f"Estimated Value Match Rate in SAME pairs: {np.mean(est_val_match)*100:.2f}%")

# Check DIFF pairs
title_j_diff = []
est_val_match_diff = []
for _, r in diff_pairs.iterrows():
    na, nb = r['notice_id_a'], r['notice_id_b']
    a, b = df_notices.loc[na], df_notices.loc[nb]
    t_a = clean_tokens(a['title'], "")
    t_b = clean_tokens(b['title'], "")
    title_j_diff.append(jaccard(get_shingles(t_a, 2), get_shingles(t_b, 2)))
    est_val_match_diff.append(a['estimated_value'] == b['estimated_value'])

title_j_diff = np.array(title_j_diff)
print(f"\nDIFF pairs (n={len(diff_pairs)}):")
print(f"Title Word-2 Jaccard: min={title_j_diff.min():.3f}, median={np.median(title_j_diff):.3f}, 90th%={np.percentile(title_j_diff, 90):.3f}, max={title_j_diff.max():.3f}")
print(f"Estimated Value Match Rate in DIFF pairs: {np.mean(est_val_match_diff)*100:.2f}%")
