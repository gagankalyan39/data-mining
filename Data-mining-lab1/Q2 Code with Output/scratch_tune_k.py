import glob, re, hashlib, time
import numpy as np
import pandas as pd

files = sorted(glob.glob('data_2/notices/*.csv'))
df_notices = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
df_pairs = pd.read_csv('data_2/labelled_pairs.csv')
notices_dict = df_notices.set_index('notice_id').to_dict('index')

RE_PREAMBLE_NPAS = re.compile(r'GOVERNMENT OF INDIA -- NATIONAL PROCUREMENT AGGREGATION SERVICE[\s\S]*?(?=(Name of work:|NAME OF WORK:|$))', re.I)
RE_PREAMBLE_SPC = re.compile(r'STATE PROCUREMENT CELL -- CONSOLIDATED TENDER BULLETIN[\s\S]*?(?=(Name of work:|NAME OF WORK:|$))', re.I)
RE_DISCLAIMER = re.compile(r'(Disclaimer:|DISCLAIMER:)[\s\S]*$', re.I)
RE_REF = re.compile(r'(tender reference number|ref no|tender ref)[\s:]*([^\n\r]+)', re.I)
RE_PORTAL_REF = re.compile(r'\b(NPAS|SPC|PWD|TN|MC|ref|DEPA|MUNI)[-\d/A-Za-z]+', re.I)
RE_TITLE_PREFIX = re.compile(r'^(e-tender|nit for|tender notice|corrigendum)\s*[-:]*', re.I)

def clean_tokens(title, body):
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

def get_shingles(toks, k):
    if len(toks) < k:
        return set(toks)
    return set(tuple(toks[i:i+k]) for i in range(len(toks) - k + 1))

def jaccard(s1, s2):
    if not s1 or not s2: return 0.0
    return len(s1.intersection(s2)) / len(s1.union(s2))

same_pairs = df_pairs[df_pairs['label'] == 'same']
diff_pairs = df_pairs[df_pairs['label'] == 'different']

for k in [1, 2, 3]:
    j_same = []
    for _, r in same_pairs.iterrows():
        t1 = clean_tokens(notices_dict[r['notice_id_a']]['title'], notices_dict[r['notice_id_a']]['body'])
        t2 = clean_tokens(notices_dict[r['notice_id_b']]['title'], notices_dict[r['notice_id_b']]['body'])
        j_same.append(jaccard(get_shingles(t1, k), get_shingles(t2, k)))
    j_same = np.array(j_same)
    
    j_diff = []
    for _, r in diff_pairs.head(100).iterrows():
        t1 = clean_tokens(notices_dict[r['notice_id_a']]['title'], notices_dict[r['notice_id_a']]['body'])
        t2 = clean_tokens(notices_dict[r['notice_id_b']]['title'], notices_dict[r['notice_id_b']]['body'])
        j_diff.append(jaccard(get_shingles(t1, k), get_shingles(t2, k)))
    j_diff = np.array(j_diff)
    
    print(f"\n--- Word {k}-grams ---")
    print(f"SAME pairs (n={len(j_same)}): min={j_same.min():.3f}, 10th%={np.percentile(j_same, 10):.3f}, median={np.median(j_same):.3f}, max={j_same.max():.3f}")
    print(f"DIFF pairs (n=100): min={j_diff.min():.3f}, median={np.median(j_diff):.3f}, 90th%={np.percentile(j_diff, 90):.3f}, max={j_diff.max():.3f}")
