-- =============================================================
-- masters.sql  –  Annapurna Stores master reference data
-- Load into PostgreSQL: annapurna_db
-- =============================================================

-- ── Stores ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stores (
    store_id      SERIAL PRIMARY KEY,
    store_code    VARCHAR(10)  NOT NULL UNIQUE,
    store_name    VARCHAR(100) NOT NULL,
    address_line1 VARCHAR(150),
    address_line2 VARCHAR(150),
    city          VARCHAR(80),
    state         VARCHAR(80),
    pincode       VARCHAR(10)
);

INSERT INTO stores (store_code, store_name, address_line1, city, state, pincode) VALUES
('S01', 'Annapurna Banjara Hills',   '45 Road No. 12',           'Hyderabad',  'Telangana',    '500034'),
('S02', 'Annapurna Jubilee Hills',   '8-2-293/82/A, Road No. 36','Hyderabad',  'Telangana',    '500033'),
('S03', 'Annapurna Gachibowli',      'Plot 18, Financial Dist',  'Hyderabad',  'Telangana',    '500032'),
('S04', 'Annapurna Kondapur',        '1-90/2, Hi-Tech City Rd',  'Hyderabad',  'Telangana',    '500084'),
('S05', 'Annapurna Kukatpally',      'KPHB Colony, Phase 7',     'Hyderabad',  'Telangana',    '500072'),
('S06', 'Annapurna Secunderabad',    '15 Park Lane',             'Secunderabad','Telangana',   '500003'),
('S07', 'Annapurna Uppal',           'ECIL X Roads',             'Hyderabad',  'Telangana',    '500039'),
('S08', 'Annapurna LB Nagar',        'LB Nagar Circle',          'Hyderabad',  'Telangana',    '500074'),
('S09', 'Annapurna Mehdipatnam',     'Mehdipatnam Main Rd',      'Hyderabad',  'Telangana',    '500028'),
('S10', 'Annapurna Dilsukhnagar',    'Dilsukhnagar Main Rd',     'Hyderabad',  'Telangana',    '500060'),
('S11', 'Annapurna Ameerpet',        'Ameerpet Metro Stn',       'Hyderabad',  'Telangana',    '500016'),
('S12', 'Annapurna Begumpet',        'Begumpet Main Rd',         'Hyderabad',  'Telangana',    '500016');

-- ── Product Categories ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS product_categories (
    category_id   SERIAL PRIMARY KEY,
    category_code VARCHAR(10)  NOT NULL UNIQUE,
    category_name VARCHAR(100) NOT NULL
);

INSERT INTO product_categories (category_code, category_name) VALUES
('BISCUIT',  'Biscuits & Cookies'),
('BEVERAGE', 'Beverages'),
('DAIRY',    'Dairy & Eggs'),
('SNACKS',   'Snacks & Namkeen'),
('STAPLES',  'Staples & Grains'),
('FROZEN',   'Frozen Foods'),
('PERSONAL', 'Personal Care'),
('CLEANING', 'Cleaning & Household'),
('BAKERY',   'Bakery'),
('CONFECT',  'Confectionery');

-- ── Products ───────────────────────────────────────────────────
-- Note: product_code can be REUSED after a product is retired.
-- Always filter by (product_code, valid_from / valid_to) period.
CREATE TABLE IF NOT EXISTS products (
    product_id    SERIAL PRIMARY KEY,
    product_code  VARCHAR(20)  NOT NULL,
    product_name  VARCHAR(150) NOT NULL,
    category_code VARCHAR(10)  REFERENCES product_categories(category_code),
    valid_from    DATE         NOT NULL,
    valid_to      DATE,          -- NULL means currently active
    UNIQUE (product_code, valid_from)
);

INSERT INTO products (product_code, product_name, category_code, valid_from, valid_to) VALUES
-- Active products
('P001', 'Britannia Marie Gold 250g',       'BISCUIT',  '2023-01-01', NULL),
('P002', 'Parle-G Original 500g',           'BISCUIT',  '2023-01-01', NULL),
('P003', 'Sunfeast Dark Fantasy 100g',      'BISCUIT',  '2023-01-01', NULL),
('P004', 'Oreo Original 120g',              'BISCUIT',  '2023-01-01', NULL),
('P005', 'Pepsi 2L',                        'BEVERAGE', '2023-01-01', NULL),
('P006', 'Coca-Cola 1.5L',                  'BEVERAGE', '2023-01-01', NULL),
('P007', 'Amul Taaza Milk 1L',              'DAIRY',    '2023-01-01', NULL),
('P008', 'Amul Butter 500g',                'DAIRY',    '2023-01-01', NULL),
('P009', 'Lay s Classic Salted 26g',        'SNACKS',   '2023-01-01', NULL),
('P010', 'Haldiram Aloo Bhujia 200g',       'SNACKS',   '2023-01-01', NULL),
('P011', 'Aashirvaad Atta 5kg',             'STAPLES',  '2023-01-01', NULL),
('P012', 'Tata Salt 1kg',                   'STAPLES',  '2023-01-01', NULL),
('P013', 'McCain Smiles Frozen 400g',       'FROZEN',   '2023-01-01', NULL),
('P014', 'Dove Soap 75g',                   'PERSONAL', '2023-01-01', NULL),
('P015', 'Surf Excel Matic 1kg',            'CLEANING', '2023-01-01', NULL),
-- Retired & reissued product code example
('P050', 'OLD: Disco Biscuit 100g',         'BISCUIT',  '2020-01-01', '2022-12-31'),
('P050', 'NEW: Sunfeast Mom Magic 150g',    'BISCUIT',  '2023-01-01', NULL);

-- ── Price Revisions ────────────────────────────────────────────
-- Effective price for a (product_code, period).
-- The price that applied on date D = max(effective_date) where effective_date <= D
CREATE TABLE IF NOT EXISTS price_revisions (
    revision_id    SERIAL PRIMARY KEY,
    product_code   VARCHAR(20)  NOT NULL,
    unit_price     NUMERIC(10,2) NOT NULL,
    effective_date DATE          NOT NULL,
    currency       CHAR(3)       DEFAULT 'INR',
    UNIQUE (product_code, effective_date)
);

INSERT INTO price_revisions (product_code, unit_price, effective_date) VALUES
-- P001 Britannia Marie Gold
('P001', 25.00,  '2023-01-01'),
('P001', 27.00,  '2023-07-01'),
('P001', 28.00,  '2024-01-01'),
('P001', 30.00,  '2024-07-01'),
-- P002 Parle-G
('P002', 10.00,  '2023-01-01'),
('P002', 10.00,  '2024-01-01'),  -- price unchanged
-- P003 Sunfeast Dark Fantasy
('P003', 50.00,  '2023-01-01'),
('P003', 55.00,  '2024-01-01'),
-- P004 Oreo
('P004', 30.00,  '2023-01-01'),
('P004', 33.00,  '2024-03-01'),
-- P005 Pepsi
('P005', 95.00,  '2023-01-01'),
('P005', 99.00,  '2024-01-01'),
-- P006 Coca-Cola
('P006', 90.00,  '2023-01-01'),
('P006', 95.00,  '2024-01-01'),
-- P007 Amul Taaza
('P007', 60.00,  '2023-01-01'),
('P007', 62.00,  '2024-01-01'),
-- P008 Amul Butter
('P008', 275.00, '2023-01-01'),
('P008', 285.00, '2024-01-01'),
-- P009 Lays
('P009', 20.00,  '2023-01-01'),
('P009', 20.00,  '2024-01-01'),
-- P010 Haldiram
('P010', 70.00,  '2023-01-01'),
('P010', 75.00,  '2024-01-01'),
-- P011 Aashirvaad Atta
('P011', 280.00, '2023-01-01'),
('P011', 295.00, '2024-01-01'),
-- P012 Tata Salt
('P012', 24.00,  '2023-01-01'),
('P012', 25.00,  '2024-01-01'),
-- P013 McCain Smiles
('P013', 145.00, '2023-01-01'),
('P013', 155.00, '2024-01-01'),
-- P014 Dove Soap
('P014', 48.00,  '2023-01-01'),
('P014', 52.00,  '2024-01-01'),
-- P015 Surf Excel
('P015', 310.00, '2023-01-01'),
('P015', 325.00, '2024-01-01'),
-- P050 OLD product (before retirement)
('P050', 18.00,  '2020-01-01'),
-- P050 NEW product (after reissue)
('P050', 35.00,  '2023-01-01'),
('P050', 38.00,  '2024-01-01');
