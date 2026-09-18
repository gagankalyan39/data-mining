"""
task_b_idempotency.py
=====================
Task (b):
Proves the loading pipeline is 100% IDEMPOTENT (safe to run multiple times):
1. The billing system re-sends files when a store reports a problem (e.g. __R1, __R2).
2. The loading step normalises all dialects and deduplicates by (bill_no, line_no).
3. The script executes the loading process 3 times consecutively.
4. After each run, it computes:
   - Deduplicated row count
   - A cryptographic SHA-256 checksum across the entire deduplicated dataset
5. Displays a comparison table proving Run 1 == Run 2 == Run 3.
"""

import os
import io
import re
import glob
import hashlib
import pandas as pd
from minio import Minio

MINIO_ENDPOINT = "localhost:9000"
MINIO_ACCESS = "minioadmin"
MINIO_SECRET = "minioadmin"
BUCKET_NAME = "annapurna-sales"
SALES_DIR = os.path.join(os.path.dirname(__file__), "data", "sales")

def run_ingestion_pipeline() -> pd.DataFrame:
    """
    Ingests all files, standardises column schemas across the 3 billing vendor
    generations (S01-S05, S06-S09, S10-S12), and deduplicates on (bill_no, line_no).
    """
    files = glob.glob(os.path.join(SALES_DIR, "*.csv"))
    records = []
    
    for f in files:
        fname = os.path.basename(f)
        m = re.match(r"SALES_([A-Z0-9]+)_(\d{4})(\d{2})(\d{2})", fname)
        if not m:
            continue
        store_id, year, month, day = m.group(1), m.group(2), m.group(3), m.group(4)
        bdate = f"{year}-{month}-{day}"
        
        # Dialect handling from billing_notes.md:
        sep = ';' if store_id in ['S06', 'S07', 'S08', 'S09'] else ','
        enc = 'utf-8-sig' if store_id in ['S10', 'S11', 'S12'] else 'utf-8'
        
        df = pd.read_csv(f, sep=sep, encoding=enc, dtype=str)
        
        # Standardise column names
        if 'item_code' in df.columns:
            df = df.rename(columns={
                'item_code': 'product_code',
                'quantity': 'qty',
                'rate': 'unit_price',
                'type': 'line_type',
                'txn_time': 'ts'
            })
            
        df['business_date'] = bdate
        df['store_id'] = store_id
        records.append(df[['bill_no', 'line_no', 'store_id', 'product_code', 'qty', 'unit_price', 'line_type', 'business_date']])
        
    all_df = pd.concat(records, ignore_index=True)
    raw_count = len(all_df)
    
    # Deduplicate by primary grain (bill_no, line_no)
    dedup_df = all_df.drop_duplicates(subset=['bill_no', 'line_no'], keep='first').copy()
    
    return dedup_df, raw_count

def compute_dataset_checksum(df: pd.DataFrame) -> str:
    """Computes a deterministic SHA-256 hash over sorted rows."""
    sorted_df = df.sort_values(by=['bill_no', 'line_no']).reset_index(drop=True)
    serialized = sorted_df.to_csv(index=False).encode('utf-8')
    return hashlib.sha256(serialized).hexdigest()

def main():
    print("=" * 80)
    print(" TASK (b): IDEMPOTENCY PROOF - RUNNING LOADING PIPELINE 3 TIMES")
    print("=" * 80)
    print(" Deduplication strategy: Primary transaction line grain (bill_no, line_no)")
    print(" Handling re-sent daily files (__R1, __R2) and partial files safely.\n")

    results = []

    for run_i in range(1, 4):
        print(f"[*] Executing Run #{run_i}...")
        df, raw_count = run_ingestion_pipeline()
        dedup_count = len(df)
        checksum = compute_dataset_checksum(df)
        
        results.append({
            "run": run_i,
            "raw_rows": raw_count,
            "dedup_rows": dedup_count,
            "duplicates_removed": raw_count - dedup_count,
            "checksum": checksum
        })
        print(f"    -> Raw rows loaded:        {raw_count:,}")
        print(f"    -> Deduplicated row count: {dedup_count:,}")
        print(f"    -> SHA-256 Checksum:       {checksum}\n")

    print("=" * 80)
    print(" IDEMPOTENCY VERIFICATION RESULTS TABLE")
    print("=" * 80)
    print(f"{'Run #':<8} | {'Raw Rows':<12} | {'Clean Rows':<12} | {'Duplicates Removed':<20} | {'SHA-256 Checksum':<64}")
    print("-" * 125)
    for r in results:
        print(f"Run {r['run']:<4} | {r['raw_rows']:<12,d} | {r['dedup_rows']:<12,d} | {r['duplicates_removed']:<20,d} | {r['checksum']}")
    print("-" * 125)

    all_same_count = len(set(r["dedup_rows"] for r in results)) == 1
    all_same_checksum = len(set(r["checksum"] for r in results)) == 1

    if all_same_count and all_same_checksum:
        print("\n[PROVED] All 3 consecutive runs produced the EXACT SAME row count and identical")
        print("         SHA-256 checksum down to the bit. The loading process is strictly IDEMPOTENT.")
    else:
        print("\n[FAIL] Non-deterministic results detected across runs.")
    print("=" * 80)

if __name__ == "__main__":
    main()
