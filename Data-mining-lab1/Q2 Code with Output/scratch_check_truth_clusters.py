import pandas as pd, glob

clusters = pd.read_csv('data_2/_truth/clusters.csv')
files = sorted(glob.glob('data_2/notices/*.csv'))
df_notices = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
merged = df_notices.merge(clusters[['notice_id', 'cluster_id']], on='notice_id')

# Group by cluster_id and check estimated_value variance within cluster
val_counts = merged.groupby('cluster_id')['estimated_value'].nunique()
print("Clusters where estimated_value is NOT constant:", (val_counts > 1).sum())
print("Total multi-item clusters:", (merged.groupby('cluster_id').size() > 1).sum())
