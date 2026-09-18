"""
task_d_prices.py
================
Task (d): Make March use March's prices.
1. The authoritative price list is in PostgreSQL (table: price_revisions),
   which contains historical SCD Type 2 price revisions:
   (product_sk, selling_price, effective_from, effective_to).
2. The exact same analytical SQL query is executed twice:
   - RUN 1: Target Month = '2024-03' (March 2024)
   - RUN 2: Target Month = '2024-10' (October 2024 / Last Month)
   WITHOUT ANY CODE CHANGE.
3. Proves that March reporting automatically uses March's effective price,
   and October reporting automatically uses October's effective price.
"""

import duckdb
import psycopg2
import pandas as pd
import glob
import os
import re

PG_CONN_STR = "host=localhost port=5432 user=postgres password=1234 dbname=annapurna"
SALES_DIR = os.path.join(os.path.dirname(__file__), "data", "sales")

def run_price_demonstration():
    print("=" * 80)
    print(" TASK (d): HISTORICAL PRICE REVISION ENGINE (March vs October Prices)")
    print("=" * 80)

    # 1. Fetch masters from PostgreSQL
    pg_conn = psycopg2.connect(PG_CONN_STR)
    products_df = pd.read_sql("SELECT * FROM products", pg_conn)
    price_rev_df = pd.read_sql("SELECT * FROM price_revisions", pg_conn)
    pg_conn.close()

    # 2. Ingest sales lines
    files = glob.glob(os.path.join(SALES_DIR, "*.csv"))
    records = []
    for f in files:
        fname = os.path.basename(f)
        m = re.match(r"SALES_([A-Z0-9]+)_(\d{4})(\d{2})(\d{2})", fname)
        if not m:
            continue
        store_id, year, month, day = m.group(1), m.group(2), m.group(3), m.group(4)
        if month not in ['03', '10']: # Focus on March & October for speed
            continue
        bdate = f"{year}-{month}-{day}"
        sep = ';' if store_id in ['S06', 'S07', 'S08', 'S09'] else ','
        enc = 'utf-8-sig' if store_id in ['S10', 'S11', 'S12'] else 'utf-8'
        df = pd.read_csv(f, sep=sep, encoding=enc, dtype=str)
        if 'item_code' in df.columns:
            df = df.rename(columns={'item_code': 'product_code', 'quantity': 'qty', 'rate': 'unit_price', 'type': 'line_type'})
        df['business_date'] = bdate
        df['store_id'] = store_id
        records.append(df[['bill_no', 'line_no', 'store_id', 'product_code', 'qty', 'unit_price', 'line_type', 'business_date']])

    all_sales = pd.concat(records, ignore_index=True).drop_duplicates(subset=['bill_no', 'line_no'])

    con = duckdb.connect()
    con.register("stg_sales", all_sales)
    con.register("dim_product", products_df)
    con.register("price_revisions", price_rev_df)

    # Create base sales fact
    con.execute("""
        CREATE TABLE fact_sales AS
        SELECT
            s.bill_no,
            s.line_no::INTEGER AS line_no,
            s.store_id,
            p.product_sk,
            p.product_code,
            p.product_name,
            s.business_date::DATE AS business_date,
            strftime(s.business_date::DATE, '%Y-%m') AS sale_year_month,
            s.qty::DOUBLE AS qty,
            s.unit_price::DOUBLE AS printed_unit_price
        FROM stg_sales s
        JOIN dim_product p
            ON  s.product_code = p.product_code
            AND s.business_date::DATE >= p.valid_from::DATE
            AND s.business_date::DATE < p.valid_to::DATE
        WHERE s.line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID');
    """)

    # Pick 4 representative products with price revisions across the year
    sample_prods = con.execute("""
        SELECT DISTINCT p.product_code
        FROM price_revisions pr
        JOIN dim_product p ON pr.product_sk = p.product_sk
        GROUP BY p.product_code
        HAVING COUNT(DISTINCT pr.selling_price) >= 2
        LIMIT 4
    """).fetchall()
    prod_codes = [r[0] for r in sample_prods]
    prod_codes_str = ", ".join([f"'{c}'" for c in prod_codes])

    # ── THE AUTHORITATIVE PRICING QUERY (Parameterised ONLY by :period) ─
    pricing_query_template = """
        SELECT
            s.sale_year_month AS reporting_period,
            s.product_code,
            s.product_name,
            -- Authoritative historical price in effect on the sale date:
            pr.selling_price AS effective_price_inr,
            -- Average price printed on POS receipts:
            ROUND(AVG(s.printed_unit_price), 2) AS avg_printed_price_inr,
            SUM(s.qty)::INTEGER AS total_quantity_sold,
            -- Revenue calculated at the authoritative historical price:
            ROUND(SUM(s.qty * pr.selling_price), 2) AS total_revenue_at_effective_price
        FROM fact_sales s
        -- Point-in-time join to PostgreSQL price_revisions:
        JOIN price_revisions pr
            ON  s.product_sk = pr.product_sk
            AND s.business_date >= pr.effective_from::DATE
            AND s.business_date < pr.effective_to::DATE
        WHERE s.sale_year_month = '{reporting_period}'
          AND s.product_code IN ({prod_list})
        GROUP BY s.sale_year_month, s.product_code, s.product_name, pr.selling_price
        ORDER BY s.product_code;
    """

    print("\n" + "=" * 80)
    print(" RUN 1: REPORT FOR MARCH 2024 (Uses March's Prices)")
    print("=" * 80)
    march_query = pricing_query_template.format(reporting_period="2024-03", prod_list=prod_codes_str)
    march_df = con.execute(march_query).df()
    print(march_df.to_string(index=False))

    print("\n" + "=" * 80)
    print(" RUN 2: REPORT FOR OCTOBER 2024 (Uses October's Prices - Same Query!)")
    print("=" * 80)
    oct_query = pricing_query_template.format(reporting_period="2024-10", prod_list=prod_codes_str)
    oct_df = con.execute(oct_query).df()
    print(oct_df.to_string(index=False))

    print("\n" + "=" * 80)
    print(" PRICE REVISION COMPARISON SUMMARY")
    print("=" * 80)
    merged = march_df[['product_code', 'product_name', 'effective_price_inr']].merge(
        oct_df[['product_code', 'effective_price_inr']],
        on='product_code',
        suffixes=('_march', '_october')
    )
    merged['price_change_inr'] = (merged['effective_price_inr_october'] - merged['effective_price_inr_march']).round(2)
    merged['pct_change'] = ((merged['price_change_inr'] / merged['effective_price_inr_march']) * 100).round(1).astype(str) + '%'
    print(merged.to_string(index=False))

    print("\nCONCLUSION:")
    print("  Notice that the exact same query with zero code change uses the price that")
    print("  applied in March 2024 for the March report, and the revised price in October 2024")
    print("  for the October report, fulfilling the CFO's requirement:")
    print("  'I also want last march's price when I ask about last march.'")

if __name__ == "__main__":
    run_price_demonstration()
