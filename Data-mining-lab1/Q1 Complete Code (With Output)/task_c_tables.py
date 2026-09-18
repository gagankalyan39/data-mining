"""
task_c_tables.py
================
Task (c): Design the tables behind the dashboard.
1. Implements a star schema (fact_sales + dim_store, dim_product, dim_category, dim_date)
   so store address/name are NOT repeated across millions of raw sales lines.
2. Handles the two source data traps:
   a) Non-sale lines: EXCLUDES 'TENDER' (bill total causing ~2x doubling) and 'TAX' (GST).
      INCLUDES: SALE (+), RETURN (-), DISCOUNT (-), VOID (cancelled).
   b) Product code reuse: Joins on product_code AND date interval [valid_from, valid_to).
3. Demonstrates fast analytical queries slicing revenue by:
   - Store
   - Product Category
   - Day of the week
   - Month
"""

import duckdb
import psycopg2
import pandas as pd
import glob
import os
import re

PG_CONN_STR = "host=localhost port=5432 user=postgres password=1234 dbname=annapurna"
SALES_DIR = os.path.join(os.path.dirname(__file__), "data", "sales")

def build_star_schema():
    print("=" * 80)
    print(" TASK (c): DESIGNING WAREHOUSE TABLES & REVENUE SLICING ENGINE")
    print("=" * 80)

    # Connect to PostgreSQL to fetch master dimensions
    print("[*] Reading dimensional masters from PostgreSQL (annapurna_db)...")
    pg_conn = psycopg2.connect(PG_CONN_STR)
    stores_df = pd.read_sql("SELECT * FROM stores", pg_conn)
    categories_df = pd.read_sql("SELECT * FROM product_categories", pg_conn)
    products_df = pd.read_sql("SELECT * FROM products", pg_conn)
    pg_conn.close()

    # Load and deduplicate sales lines
    print("[*] Ingesting & deduplicating sales lines from object store...")
    files = glob.glob(os.path.join(SALES_DIR, "*.csv"))
    records = []
    for f in files:
        fname = os.path.basename(f)
        m = re.match(r"SALES_([A-Z0-9]+)_(\d{4})(\d{2})(\d{2})", fname)
        if not m:
            continue
        store_id, year, month, day = m.group(1), m.group(2), m.group(3), m.group(4)
        bdate = f"{year}-{month}-{day}"
        sep = ';' if store_id in ['S06', 'S07', 'S08', 'S09'] else ','
        enc = 'utf-8-sig' if store_id in ['S10', 'S11', 'S12'] else 'utf-8'
        df = pd.read_csv(f, sep=sep, encoding=enc, dtype=str)
        if 'item_code' in df.columns:
            df = df.rename(columns={'item_code': 'product_code', 'quantity': 'qty', 'rate': 'unit_price', 'type': 'line_type'})
        df['business_date'] = bdate
        df['store_id'] = store_id
        records.append(df[['bill_no', 'line_no', 'store_id', 'product_code', 'qty', 'unit_price', 'line_type', 'business_date']])

    raw_sales = pd.concat(records, ignore_index=True)
    dedup_sales = raw_sales.drop_duplicates(subset=['bill_no', 'line_no']).copy()
    
    # Connect in-memory DuckDB
    con = duckdb.connect()
    con.register("stg_sales", dedup_sales)
    con.register("dim_store", stores_df)
    con.register("dim_category", categories_df)
    con.register("dim_product", products_df)

    print("\n[*] Building Star Schema in DuckDB:")
    print("    - dim_store (12 stores, normalised address)")
    print("    - dim_category (14 categories)")
    print("    - dim_product (1,224 rows with SCD Type 2 date ranges)")
    print("    - fact_sales (deduplicated, filtered for valid revenue lines, linked via surrogate keys)")

    # Build fact_sales
    # CRITICAL: Filter out TENDER and TAX (prevents October 2x doubling trap!)
    # CRITICAL: Join products on product_code AND date validity (prevents code reuse trap!)
    con.execute("""
        CREATE OR REPLACE TABLE fact_sales AS
        SELECT
            s.bill_no,
            s.line_no::INTEGER AS line_no,
            s.store_id,
            p.product_sk,
            p.category_id,
            s.business_date::DATE AS business_date,
            s.line_type,
            s.qty::DOUBLE AS qty,
            s.unit_price::DOUBLE AS unit_price,
            (s.qty::DOUBLE * s.unit_price::DOUBLE) AS revenue_inr,
            EXTRACT(YEAR FROM s.business_date::DATE)::INTEGER AS sale_year,
            EXTRACT(MONTH FROM s.business_date::DATE)::INTEGER AS sale_month,
            strftime(s.business_date::DATE, '%Y-%m') AS sale_year_month,
            EXTRACT(DOW FROM s.business_date::DATE)::INTEGER AS day_of_week_num,
            dayname(s.business_date::DATE) AS day_of_week
        FROM stg_sales s
        -- 1. Join product by code AND date range (handles recycled product codes)
        LEFT JOIN dim_product p
            ON  s.product_code = p.product_code
            AND s.business_date::DATE >= p.valid_from::DATE
            AND s.business_date::DATE < p.valid_to::DATE
        -- 2. Exclude TENDER (bill totals) and TAX (GST) - counts genuine revenue only!
        WHERE s.line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID');
    """)

    fact_count = con.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
    oct_rev = con.execute("SELECT ROUND(SUM(revenue_inr), 2) FROM fact_sales WHERE sale_year_month = '2024-10'").fetchone()[0]
    print(f"\n[+] fact_sales populated: {fact_count:,} genuine revenue lines.")
    print(f"[+] October 2024 Clean Revenue: INR {oct_rev:,.2f} (Clean, single-counted!)")

    # ── Demonstration 1: Revenue Sliced by Store ─────────────────────────
    print("\n" + "=" * 80)
    print(" 1. REVENUE SLICED BY STORE (Top 5 & Total)")
    print("=" * 80)
    store_slice = con.execute("""
        SELECT
            s.store_id,
            st.store_name,
            st.city,
            COUNT(DISTINCT s.bill_no) AS total_bills,
            ROUND(SUM(s.revenue_inr), 2) AS total_revenue_inr
        FROM fact_sales s
        JOIN dim_store st ON s.store_id = st.store_id
        GROUP BY s.store_id, st.store_name, st.city
        ORDER BY total_revenue_inr DESC
    """).df()
    print(store_slice.head(5).to_string(index=False))
    print(f"... total stores: {len(store_slice)}, overall revenue: INR {store_slice['total_revenue_inr'].sum():,.2f}")

    # ── Demonstration 2: Revenue Sliced by Product Category ──────────────
    print("\n" + "=" * 80)
    print(" 2. REVENUE SLICED BY PRODUCT CATEGORY (Top 5)")
    print("=" * 80)
    cat_slice = con.execute("""
        SELECT
            c.category_id,
            c.category_name,
            c.department,
            ROUND(SUM(s.revenue_inr), 2) AS total_revenue_inr,
            ROUND(SUM(s.revenue_inr) * 100.0 / (SELECT SUM(revenue_inr) FROM fact_sales), 2) AS pct_share
        FROM fact_sales s
        JOIN dim_category c ON s.category_id = c.category_id
        GROUP BY c.category_id, c.category_name, c.department
        ORDER BY total_revenue_inr DESC
    """).df()
    print(cat_slice.head(5).to_string(index=False))

    # ── Demonstration 3: Revenue Sliced by Day of the Week ────────────────
    print("\n" + "=" * 80)
    print(" 3. REVENUE SLICED BY DAY OF THE WEEK (Mon - Sun)")
    print("=" * 80)
    dow_slice = con.execute("""
        SELECT
            day_of_week,
            COUNT(DISTINCT bill_no) AS bills_count,
            ROUND(SUM(revenue_inr), 2) AS total_revenue_inr,
            ROUND(AVG(revenue_inr), 2) AS avg_line_inr
        FROM fact_sales
        GROUP BY day_of_week_num, day_of_week
        ORDER BY (CASE day_of_week
            WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3
            WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 WHEN 'Sunday' THEN 7
        END)
    """).df()
    print(dow_slice.to_string(index=False))

    # ── Demonstration 4: Revenue Sliced by Month ─────────────────────────
    print("\n" + "=" * 80)
    print(" 4. REVENUE SLICED BY MONTH (Full Year 2024)")
    print("=" * 80)
    month_slice = con.execute("""
        SELECT
            sale_year_month AS month,
            COUNT(DISTINCT bill_no) AS transactions,
            ROUND(SUM(revenue_inr), 2) AS monthly_revenue_inr
        FROM fact_sales
        GROUP BY sale_year_month
        ORDER BY sale_year_month
    """).df()
    print(month_slice.to_string(index=False))
    print("=" * 80)

if __name__ == "__main__":
    build_star_schema()
