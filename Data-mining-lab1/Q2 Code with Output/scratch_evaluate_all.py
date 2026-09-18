import pandas as pd
import glob
import re
import numpy as np

# Load notices and labels
files = sorted(glob.glob('data_2/notices/*.csv'))
df_notices = pd.concat([pd.read_csv(f) for f in files], ignore_index=True).set_index('notice_id')
df_pairs = pd.read_csv('data_2/labelled_pairs.csv')

print(f"Loaded {len(df_notices)} notices and {len(df_pairs)} pairs.")

# Boilerplate patterns from portal_profiles.md
NPAS_PATTERN = re.compile(r'GOVERNMENT OF INDIA -- NATIONAL PROCUREMENT AGGREGATION SERVICE[\s\S]*?(?=(Name of work:|NAME OF WORK:|$))', re.I)
SPC_PATTERN = re.compile(r'STATE PROCUREMENT CELL -- CONSOLIDATED TENDER BULLETIN[\s\S]*?(?=(Name of work:|NAME OF WORK:|$))', re.I)
DISCLAIMER_PATTERN = re.compile(r'(Disclaimer:|DISCLAIMER:)[\s\S]*$', re.I)
REF_NUM_PATTERN = re.compile(r'(tender reference number|ref no|tender ref)[\s:]*([^\n\r]+)', re.I)

def clean_text(title, body, strip_boilerplate=True):
    text = f"{title} {body}"
    if strip_boilerplate:
        text = NPAS_PATTERN.sub('', text)
        text = SPC_PATTERN.sub('', text)
        text = DISCLAIMER_PATTERN.sub('', text)
        text = REF_NUM_PATTERN.sub('', text)
        # Remove standard legal disclaimer / general instructions repeated lines
        text = re.sub(r'GENERAL INSTRUCTIONS TO BIDDERS[\s\S]*?==================+', '', text, flags=re.I)
        text = re.sub(r'STANDARD TERMS AND CONDITIONS[\s\S]*?------------------+', '', text, flags=re.I)
    
    # Normalize: lowercase, keep letters and numbers
    tokens = re.findall(r'[a-z0-9]+', text.lower())
    return tokens

def get_word_shingles(tokens, k=3):
    if len(tokens) < k:
        return set(tokens)
    return set(tuple(tokens[i:i+k]) for i in range(len(tokens) - k + 1))

def get_char_shingles(text, k=9):
    text = re.sub(r'\s+', ' ', text.lower())
    if len(text) < k:
        return set([text])
    return set(text[i:i+k] for i in range(len(text) - k + 1))

def jaccard(s1, s2):
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    return len(s1.intersection(s2)) / len(s1.union(s2))

# Let's test a few representations across all 900 labelled pairs
# Rep 1: Raw text, word 2-shingles
# Rep 2: Raw text, word 3-shingles
# Rep 3: Cleaned text, word 2-shingles
# Rep 4: Cleaned text, word 3-shingles
# Rep 5: Cleaned text, char 8-shingles

# Let's inspect pairs on the same nodal portal
print("\nChecking pairs from identical nodal portals...")
nodal_diff = []
for idx, r in df_pairs.iterrows():
    p_a = df_notices.loc[r['notice_id_a'], 'portal_id']
    p_b = df_notices.loc[r['notice_id_b'], 'portal_id']
    if r['label'] == 'different' and p_a == p_b and p_a in ['P001', 'P002', 'P003', 'P004', 'P005', 'P006']:
        nodal_diff.append((r['notice_id_a'], r['notice_id_b'], p_a))
print(f"Found {len(nodal_diff)} different pairs on identical nodal portals. Examples: {nodal_diff[:3]}")

if nodal_diff:
    n1, n2, portal = nodal_diff[0]
    print(f"\nAnalyzing pair {n1} vs {n2} on portal {portal}:")
    
    # Raw word 2-shingles
    t1_raw = re.findall(r'[a-z0-9]+', f"{df_notices.loc[n1, 'title']} {df_notices.loc[n1, 'body']}".lower())
    t2_raw = re.findall(r'[a-z0-9]+', f"{df_notices.loc[n2, 'title']} {df_notices.loc[n2, 'body']}".lower())
    s1_raw = get_word_shingles(t1_raw, 2)
    s2_raw = get_word_shingles(t2_raw, 2)
    print(f"Raw Word 2-Shingle Jaccard: {jaccard(s1_raw, s2_raw):.4f}")
    
    # Cleaned word 2-shingles
    t1_clean = clean_text(df_notices.loc[n1, 'title'], df_notices.loc[n1, 'body'], strip_boilerplate=True)
    t2_clean = clean_text(df_notices.loc[n2, 'title'], df_notices.loc[n2, 'body'], strip_boilerplate=True)
    s1_clean = get_word_shingles(t1_clean, 2)
    s2_clean = get_word_shingles(t2_clean, 2)
    print(f"Cleaned Word 2-Shingle Jaccard: {jaccard(s1_clean, s2_clean):.4f}")

    # Cleaned word 3-shingles
    s1_c3 = get_word_shingles(t1_clean, 3)
    s2_c3 = get_word_shingles(t2_clean, 3)
    print(f"Cleaned Word 3-Shingle Jaccard: {jaccard(s1_c3, s2_c3):.4f}")
