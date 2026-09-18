import pandas as pd
import glob

files = sorted(glob.glob('data_2/notices/*.csv'))
df_notices = pd.concat([pd.read_csv(f) for f in files], ignore_index=True).set_index('notice_id')
df_pairs = pd.read_csv('data_2/labelled_pairs.csv')

print('Pairs counts:\n', df_pairs['label'].value_counts())

same_pairs = df_pairs[df_pairs['label'] == 'same'].head(4)
for idx, row in same_pairs.iterrows():
    nid_a = row['notice_id_a']
    nid_b = row['notice_id_b']
    a = df_notices.loc[nid_a]
    b = df_notices.loc[nid_b]
    print(f"\n=== SAME PAIR {nid_a} ({a['portal_id']}) vs {nid_b} ({b['portal_id']}) ===")
    print('Title A:', a['title'])
    print('Title B:', b['title'])
    print(f"Est Val A: {a['estimated_value']} | B: {b['estimated_value']}")
    print(f"Close Date A: {a['closing_date']} | B: {b['closing_date']}")
    print('Body A[:200]:', repr(a['body'][:200]))
    print('Body B[:200]:', repr(b['body'][:200]))

diff_pairs = df_pairs[df_pairs['label'] == 'different'].head(4)
for idx, row in diff_pairs.iterrows():
    nid_a = row['notice_id_a']
    nid_b = row['notice_id_b']
    a = df_notices.loc[nid_a]
    b = df_notices.loc[nid_b]
    print(f"\n=== DIFF PAIR {nid_a} ({a['portal_id']}) vs {nid_b} ({b['portal_id']}) ===")
    print('Title A:', a['title'])
    print('Title B:', b['title'])
    print(f"Est Val A: {a['estimated_value']} | B: {b['estimated_value']}")
    print(f"Close Date A: {a['closing_date']} | B: {b['closing_date']}")
    print('Body A[:200]:', repr(a['body'][:200]))
    print('Body B[:200]:', repr(b['body'][:200]))
