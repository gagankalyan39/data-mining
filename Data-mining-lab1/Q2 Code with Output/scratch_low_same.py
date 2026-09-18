import glob, re
import numpy as np, pandas as pd
from scratch_tune_k import clean_tokens, get_shingles, jaccard

files = sorted(glob.glob('data_2/notices/*.csv'))
df_notices = pd.concat([pd.read_csv(f) for f in files], ignore_index=True).set_index('notice_id')
df_pairs = pd.read_csv('data_2/labelled_pairs.csv')
same_pairs = df_pairs[df_pairs['label'] == 'same']

low_same = []
for _, r in same_pairs.iterrows():
    na, nb = r['notice_id_a'], r['notice_id_b']
    t1 = clean_tokens(df_notices.loc[na, 'title'], df_notices.loc[na, 'body'])
    t2 = clean_tokens(df_notices.loc[nb, 'title'], df_notices.loc[nb, 'body'])
    j3 = jaccard(get_shingles(t1, 3), get_shingles(t2, 3))
    if j3 < 0.4:
        low_same.append((j3, na, nb, df_notices.loc[na, 'portal_id'], df_notices.loc[nb, 'portal_id']))

low_same.sort()
print(f"Found {len(low_same)} SAME pairs with word-3 Jaccard < 0.4:")
for j3, na, nb, pa, pb in low_same[:5]:
    print(f"\n--- J3={j3:.3f}: {na} ({pa}) vs {nb} ({pb}) ---")
    print("Title A:", df_notices.loc[na, 'title'])
    print("Title B:", df_notices.loc[nb, 'title'])
    print("Est Val A:", df_notices.loc[na, 'estimated_value'], "B:", df_notices.loc[nb, 'estimated_value'])
    print("Close A:", df_notices.loc[na, 'closing_date'], "B:", df_notices.loc[nb, 'closing_date'])
    print("Body A len:", len(df_notices.loc[na, 'body']), "Body B len:", len(df_notices.loc[nb, 'body']))
    print("Body A[:200]:", repr(df_notices.loc[na, 'body'][:200]))
    print("Body B[:200]:", repr(df_notices.loc[nb, 'body'][:200]))
