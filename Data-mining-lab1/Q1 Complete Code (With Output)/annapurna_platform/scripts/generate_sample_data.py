"""
generate_sample_data.py
-----------------------
Generates ~600 synthetic daily sales files (CSV + Parquet mixed)
for 12 stores over ~50 days (covering 2024 to match finance_monthly.csv).

Run ONCE before ingestion:
    python scripts/generate_sample_data.py
"""

import os
import random
import hashlib
import pandas as pd
import numpy as np
from datetime import date, timedelta

SALES_DIR = os.path.join(os.path.dirname(__file__), "..", "exam", "data", "sales")
os.makedirs(SALES_DIR, exist_ok=True)

random.seed(42)
np.random.seed(42)

STORES = [f"S{str(i).zfill(2)}" for i in range(1, 13)]
PRODUCTS = [f"P{str(i).zfill(3)}" for i in range(1, 16)] + ["P050"]
LINE_TYPES = ["SALE", "SALE", "SALE", "SALE", "VOID", "RETURN"]  # weighted toward SALE

# Prices roughly matching price_revisions table
PRICES = {
    "P001": 28.00, "P002": 10.00, "P003": 55.00, "P004": 33.00,
    "P005": 99.00, "P006": 95.00, "P007": 62.00, "P008": 285.00,
    "P009": 20.00, "P010": 75.00, "P011": 295.00, "P012": 25.00,
    "P013": 155.00, "P014": 52.00, "P015": 325.00, "P050": 38.00,
}

START_DATE = date(2024, 1, 1)
END_DATE   = date(2024, 10, 31)

def generate_day_store(store_code: str, sale_date: date) -> pd.DataFrame:
    n_lines = random.randint(80, 250)
    rows = []
    for i in range(n_lines):
        bill_no   = f"BILL-{store_code}-{sale_date.strftime('%Y%m%d')}-{str(i+1).zfill(5)}"
        prod_code = random.choice(PRODUCTS)
        qty       = random.randint(1, 5)
        base_price = PRICES[prod_code]
        unit_price = round(base_price * random.uniform(0.95, 1.05), 2)
        line_type  = random.choice(LINE_TYPES)
        ts = pd.Timestamp(sale_date) + pd.Timedelta(
            hours=random.randint(8, 22),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59)
        )
        rows.append({
            "bill_number":   bill_no,
            "store_code":    store_code,
            "product_code":  prod_code,
            "quantity":      qty,
            "unit_price":    unit_price,
            "line_type":     line_type,
            "timestamp":     ts.isoformat(),
            "sale_date":     sale_date.isoformat(),
        })
    return pd.DataFrame(rows)


files_created = 0
current_date = START_DATE
while current_date <= END_DATE:
    for store in STORES:
        df = generate_day_store(store, current_date)
        filename_base = f"{store}_{current_date.strftime('%Y%m%d')}"

        # Alternate between CSV and Parquet
        if hash(filename_base) % 2 == 0:
            path = os.path.join(SALES_DIR, f"{filename_base}.csv")
            df.to_csv(path, index=False)
        else:
            path = os.path.join(SALES_DIR, f"{filename_base}.parquet")
            df.to_parquet(path, index=False)

        files_created += 1

    # Simulate re-send: ~5% of days, one random store re-sends
    if random.random() < 0.05:
        resend_store = random.choice(STORES)
        df = generate_day_store(resend_store, current_date)
        resend_path = os.path.join(SALES_DIR, f"{resend_store}_{current_date.strftime('%Y%m%d')}_resend.csv")
        df.to_csv(resend_path, index=False)
        files_created += 1

    current_date += timedelta(days=1)

print(f"Generated {files_created} sales files in {SALES_DIR}")
