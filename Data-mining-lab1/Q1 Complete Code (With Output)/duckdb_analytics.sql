-- ============================================================================
-- duckdb_analytics.sql
-- Annapurna Stores Analytical Query Engine (DuckDB)
-- Demonstrates direct federated query across MinIO / Object Store and PostgreSQL
-- ============================================================================

.echo on
.mode box

-- 1. Load PostgreSQL Extension & Attach Database directly
LOAD postgres;
ATTACH 'host=localhost port=5432 user=postgres password=1234 dbname=annapurna' AS pg (TYPE POSTGRES, READ_ONLY);

-- 2. Verify PostgreSQL Master Tables in DuckDB
SHOW TABLES FROM pg;

-- 3. Query PostgreSQL Store Master Table
SELECT store_id, store_name, city, state, region FROM pg.stores LIMIT 5;

-- 4. Cross-System Federated Query: Join Object Store Sales with PostgreSQL Masters
-- Note: Filters out TENDER (causes 2x doubling) and TAX (GST)
SELECT 
    st.store_name,
    c.category_name,
    COUNT(DISTINCT s.bill_no) AS total_bills,
    ROUND(SUM(s.qty::DOUBLE * s.unit_price::DOUBLE), 2) AS category_revenue_inr
FROM read_csv('data/sales/SALES_S01_202410*.csv',
              header=true,
              columns={'bill_no': 'VARCHAR', 'line_no': 'INTEGER', 'product_code': 'VARCHAR', 'qty': 'DOUBLE', 'unit_price': 'DOUBLE', 'line_type': 'VARCHAR', 'ts': 'VARCHAR'}) s
JOIN pg.stores st ON st.store_id = 'S01'
JOIN pg.products p ON s.product_code = p.product_code AND s.ts::DATE >= p.valid_from AND s.ts::DATE < p.valid_to
JOIN pg.product_categories c ON p.category_id = c.category_id
WHERE s.line_type = 'SALE'
GROUP BY st.store_name, c.category_name
ORDER BY category_revenue_inr DESC
LIMIT 6;

-- 5. Physical Engine Evidence: EXPLAIN PLAN proving zero data copying
EXPLAIN
SELECT 
    st.store_name,
    c.category_name,
    ROUND(SUM(s.qty::DOUBLE * s.unit_price::DOUBLE), 2) AS category_revenue_inr
FROM read_csv('data/sales/SALES_S01_202410*.csv',
              header=true,
              columns={'bill_no': 'VARCHAR', 'line_no': 'INTEGER', 'product_code': 'VARCHAR', 'qty': 'DOUBLE', 'unit_price': 'DOUBLE', 'line_type': 'VARCHAR', 'ts': 'VARCHAR'}) s
JOIN pg.stores st ON st.store_id = 'S01'
JOIN pg.products p ON s.product_code = p.product_code AND s.ts::DATE >= p.valid_from AND s.ts::DATE < p.valid_to
JOIN pg.product_categories c ON p.category_id = c.category_id
WHERE s.line_type = 'SALE'
GROUP BY st.store_name, c.category_name;
