import pandas as pd, glob

clusters = pd.read_csv('data_2/_truth/clusters.csv')
sample_rows = clusters[clusters['cluster_id'] == 'OPP000005']
files = sorted(glob.glob('data_2/notices/*.csv'))
df_notices = pd.concat([pd.read_csv(f) for f in files], ignore_index=True).set_index('notice_id')

for nid in sample_rows['notice_id']:
    row = df_notices.loc[nid]
    c_info = sample_rows[sample_rows['notice_id'] == nid].iloc[0]
    print(f"\n--- {nid} ({row['portal_id']}) is_corr={c_info['is_corrigendum']} archetype={c_info['archetype']} ---")
    print(f"Title: {row['title']}")
    print(f"Est Value: {row['estimated_value']}, Closing Date: {row['closing_date']}")
    print(f"Body snippet:\n{row['body'][:300]}")
