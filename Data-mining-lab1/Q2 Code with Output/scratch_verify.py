import pandas as pd
import glob
import re
import hashlib
import numpy as np

# Load data
files = sorted(glob.glob('data_2/notices/*.csv'))
df_notices = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
df_pairs = pd.read_csv('data_2/labelled_pairs.csv')
notices_dict = df_notices.set_index('notice_id').to_dict('index')

print(f"Loaded {len(df_notices)} notices and {len(df_pairs)} labelled pairs.")

# Inspect portal preambles
nodal_portals = ['P001', 'P002', 'P003', 'P004', 'P005', 'P006']
for pid in ['P001', 'P003']:
    sub = df_notices[df_notices['portal_id'] == pid].iloc[0]
    print(f"\n--- Snippet from {pid} ---")
    print(sub['body'][:300])
