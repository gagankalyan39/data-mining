import pandas as pd
import glob
import re

clusters = pd.read_csv('data_2/_truth/clusters.csv')
print("Archetypes present in ground truth:")
print(clusters['archetype'].value_counts())
print("\nIs Corrigendum:")
print(clusters['is_corrigendum'].value_counts())

# Group by cluster_id and see multi-copy clusters
multi = clusters.groupby('cluster_id').filter(lambda g: len(g) > 1)
print(f"Total multi-notice clusters: {multi['cluster_id'].nunique()}")

# Look at one multi-notice cluster across different archetypes
sample_cluster = multi.groupby('cluster_id').filter(lambda g: g['archetype'].nunique() > 2).iloc[0]['cluster_id']
print(f"\nExamining cluster: {sample_cluster}")
sample_rows = clusters[clusters['cluster_id'] == sample_cluster]
print(sample_rows[['notice_id', 'portal_id', 'copy_index', 'is_corrigendum', 'archetype']])

# Load notice details for this cluster
files = sorted(glob.glob('data_2/notices/*.csv'))
df_notices = pd.concat([pd.read_csv(f) for f in files], ignore_index=True).set_index('notice_id')
for nid in sample_rows['notice_id']:
    row = df_notices.loc[nid]
    print(f"\n--- {nid} ({row['portal_id']}) ---")
    print(f"Title: {row['title']}")
    print(f"Est Value: {row['estimated_value']}, Closing Date: {row['closing_date']}")
    print(f"Body[:250]:\n{row['body'][:250]}")
