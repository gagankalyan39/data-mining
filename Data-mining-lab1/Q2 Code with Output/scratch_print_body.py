import pandas as pd, glob
files = sorted(glob.glob('data_2/notices/*.csv'))
df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True).set_index('notice_id')
for nid in ['N007876', 'N008565']:
    print(f"=== {nid} ({df.loc[nid, 'portal_id']}) ===")
    print("Title:", df.loc[nid, 'title'])
    print("Body:\n", df.loc[nid, 'body'])
    print("="*60)
