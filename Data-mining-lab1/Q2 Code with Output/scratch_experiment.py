import pandas as pd
import glob
import re
import numpy as np

# Load data
files = sorted(glob.glob('data_2/notices/*.csv'))
df_notices = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
df_pairs = pd.read_csv('data_2/labelled_pairs.csv')
notices_dict = df_notices.set_index('notice_id').to_dict('index')

# Analyze preamble patterns
preamble_npas = r"GOVERNMENT OF INDIA -- NATIONAL PROCUREMENT AGGREGATION SERVICE.*?(\n\s*\n|Name of work:)"
preamble_spc = r"STATE PROCUREMENT CELL -- CONSOLIDATED TENDER BULLETIN.*?(\n\s*\n|Name of work:)"

def clean_text_raw(text):
    if not isinstance(text, str):
        return ""
    # Just lowercase and tokenize words
    words = re.findall(r'\b\w+\b', text.lower())
    return words

def clean_text_refined(title, body):
    full_text = f"{title}\n{body}"
    
    # 1. Remove NPAS and SPC boilerplate blocks
    text = re.sub(r'GOVERNMENT OF INDIA -- NATIONAL PROCUREMENT AGGREGATION SERVICE[\s\S]*?(?=Name of work:|NAME OF WORK:|$)', '', full_text, flags=re.IGNORECASE)
    text = re.sub(r'STATE PROCUREMENT CELL -- CONSOLIDATED TENDER BULLETIN[\s\S]*?(?=Name of work:|NAME OF WORK:|$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'STANDARD TERMS AND CONDITIONS APPLICABLE TO ALL NOTICES[\s\S]*?(?=Name of work:|NAME OF WORK:|$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'GENERAL INSTRUCTIONS TO BIDDERS \(REPRODUCED IN FULL IN EVERY BULLETIN ENTRY\)[\s\S]*?(?=Name of work:|NAME OF WORK:|$)', '', text, flags=re.IGNORECASE)
    
    # 2. Remove disclaimer footers
    text = re.sub(r'DISCLAIMER:[\s\S]*', '', text, flags=re.IGNORECASE)
    
    # 3. Remove portal-specific reference numbers: NPAS-..., SPC/..., ref-..., TN-..., MC/...
    text = re.sub(r'\b(NPAS|SPC|PWD|TN|MC|ref)[-\d/A-Za-z]+', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'tender reference number:\s*[^\n]+', ' ', text, flags=re.IGNORECASE)
    
    # 4. Remove common portal prefix titles like "e-Tender -", "NIT for", "Tender Notice: Corrigendum -"
    text = re.sub(r'^(e-tender|nit for|tender notice|corrigendum)\s*[-:]*', ' ', text, flags=re.IGNORECASE)
    
    # Lowercase & tokenize words
    words = re.findall(r'\b[a-z0-9]+\b', text.lower())
    return words

def get_word_shingles(words, k=2):
    if len(words) < k:
        return set(words)
    return set(tuple(words[i:i+k]) for i in range(len(words) - k + 1))

def jaccard(s1, s2):
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    return len(s1.intersection(s2)) / len(s1.union(s2))

# Test on a specific same pair and diff pair
# Pair N010018 vs N010020 (same)
a_same = notices_dict['N010018']
b_same = notices_dict['N010020']

# Pair N007876 vs N008565 (diff, both have nodal preambles)
a_diff = notices_dict['N007876']
b_diff = notices_dict['N008565']

# Raw word 2-shingles
s_raw_same_a = get_word_shingles(clean_text_raw(f"{a_same['title']} {a_same['body']}"), k=2)
s_raw_same_b = get_word_shingles(clean_text_raw(f"{b_same['title']} {b_same['body']}"), k=2)
j_raw_same = jaccard(s_raw_same_a, s_raw_same_b)

s_raw_diff_a = get_word_shingles(clean_text_raw(f"{a_diff['title']} {a_diff['body']}"), k=2)
s_raw_diff_b = get_word_shingles(clean_text_raw(f"{b_diff['title']} {b_diff['body']}"), k=2)
j_raw_diff = jaccard(s_raw_diff_a, s_raw_diff_b)

# Cleaned word 2-shingles
s_clean_same_a = get_word_shingles(clean_text_refined(a_same['title'], a_same['body']), k=2)
s_clean_same_b = get_word_shingles(clean_text_refined(b_same['title'], b_same['body']), k=2)
j_clean_same = jaccard(s_clean_same_a, s_clean_same_b)

s_clean_diff_a = get_word_shingles(clean_text_refined(a_diff['title'], a_diff['body']), k=2)
s_clean_diff_b = get_word_shingles(clean_text_refined(b_diff['title'], b_diff['body']), k=2)
j_clean_diff = jaccard(s_clean_diff_a, s_clean_diff_b)

print("--- DEMONSTRATION OF COMPETING CHOICES (Section A) ---")
print(f"SAME PAIR N010018 & N010020:")
print(f"  Raw Text Jaccard (Choice 1):     {j_raw_same:.4f}")
print(f"  Cleaned Text Jaccard (Choice 2): {j_clean_same:.4f}")
print(f"DIFF PAIR N007876 & N008565 (Both on Nodal Portals):")
print(f"  Raw Text Jaccard (Choice 1):     {j_raw_diff:.4f}")
print(f"  Cleaned Text Jaccard (Choice 2): {j_clean_diff:.4f}")
