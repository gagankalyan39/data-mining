"""
app_dashboard.py
================
Streamlit Executive Dashboard for Annapurna Stores:
- Slices revenue by Store, Category, Day of the Week, and Month.
- Live DuckDB analytical backend querying star schema.
- Interactive KPI cards and Plotly charts.
Run:
    py -m streamlit run app_dashboard.py
"""

import streamlit as st
import pandas as pd
import duckdb
import plotly.express as px
import psycopg2
import glob
import os
import re

st.set_page_config(
    page_title="Annapurna Stores - Revenue Intelligence",
    page_icon="🛒",
    layout="wide"
)

# Custom Styling
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .kpi-card {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        color: white;
    }
    .kpi-title { font-size: 0.9rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; }
    .kpi-value { font-size: 1.8rem; font-weight: 700; color: #38bdf8; margin-top: 5px; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(show_spinner="Loading operational & transactional data into DuckDB...")
def load_data():
    pg_conn = psycopg2.connect("host=localhost port=5432 user=postgres password=1234 dbname=annapurna")
    stores = pd.read_sql("SELECT store_id, store_name, city, state, region FROM stores", pg_conn)
    categories = pd.read_sql("SELECT category_id, category_name, department FROM product_categories", pg_conn)
    products = pd.read_sql("SELECT product_sk, product_code, product_name, category_id, valid_from, valid_to FROM products", pg_conn)
    pg_conn.close()

    files = glob.glob("data/sales/*.csv")
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

    raw = pd.concat(records, ignore_index=True).drop_duplicates(subset=['bill_no', 'line_no'])
    
    con = duckdb.connect()
    con.register("raw_s", raw)
    con.register("dim_st", stores)
    con.register("dim_cat", categories)
    con.register("dim_pr", products)

    fact = con.execute("""
        SELECT
            s.bill_no,
            s.store_id,
            st.store_name,
            st.city,
            p.category_id,
            c.category_name,
            c.department,
            s.business_date::DATE AS business_date,
            strftime(s.business_date::DATE, '%Y-%m') AS month_str,
            dayname(s.business_date::DATE) AS day_of_week,
            EXTRACT(DOW FROM s.business_date::DATE)::INTEGER AS dow_num,
            (s.qty::DOUBLE * s.unit_price::DOUBLE) AS revenue_inr
        FROM raw_s s
        JOIN dim_st st ON s.store_id = st.store_id
        JOIN dim_pr p 
            ON s.product_code = p.product_code 
           AND s.business_date::DATE >= p.valid_from::DATE 
           AND s.business_date::DATE < p.valid_to::DATE
        JOIN dim_cat c ON p.category_id = c.category_id
        WHERE s.line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID');
    """).df()
    
    return fact

df = load_data()

# Header
st.title("🛒 Annapurna Stores - Executive Revenue Dashboard")
st.caption("CFO Single-Source-of-Truth Intelligence Platform | October is October. Always.")

# Sidebar Filters
st.sidebar.header("Filter Criteria")
months = sorted(df['month_str'].unique())
selected_month = st.sidebar.selectbox("Select Month", ["All Months"] + months, index=10) # default October

all_stores = ["All Stores"] + sorted(df['store_name'].unique().tolist())
selected_store = st.sidebar.selectbox("Select Store", all_stores)

all_cats = ["All Categories"] + sorted(df['category_name'].unique().tolist())
selected_cat = st.sidebar.selectbox("Select Category", all_cats)

# Filter Dataframe
filt_df = df.copy()
if selected_month != "All Months":
    filt_df = filt_df[filt_df['month_str'] == selected_month]
if selected_store != "All Stores":
    filt_df = filt_df[filt_df['store_name'] == selected_store]
if selected_cat != "All Categories":
    filt_df = filt_df[filt_df['category_name'] == selected_cat]

# KPIs
col1, col2, col3, col4 = st.columns(4)
total_rev = filt_df['revenue_inr'].sum()
total_tx = filt_df['bill_no'].nunique()
avg_basket = total_rev / max(total_tx, 1)
active_stores = filt_df['store_id'].nunique()

with col1:
    st.markdown(f"<div class='kpi-card'><div class='kpi-title'>Total Net Revenue</div><div class='kpi-value'>₹{total_rev:,.2f}</div></div>", unsafe_allow_html=True)
with col2:
    st.markdown(f"<div class='kpi-card'><div class='kpi-title'>Total Transactions</div><div class='kpi-value'>{total_tx:,}</div></div>", unsafe_allow_html=True)
with col3:
    st.markdown(f"<div class='kpi-card'><div class='kpi-title'>Avg Basket Value</div><div class='kpi-value'>₹{avg_basket:,.2f}</div></div>", unsafe_allow_html=True)
with col4:
    st.markdown(f"<div class='kpi-card'><div class='kpi-title'>Reporting Stores</div><div class='kpi-value'>{active_stores} / 12</div></div>", unsafe_allow_html=True)

st.write("")

# Charts Row 1: Slicing by Store & Slicing by Category
r1_col1, r1_col2 = st.columns(2)

with r1_col1:
    st.subheader("📍 Revenue by Store")
    store_agg = filt_df.groupby("store_name")["revenue_inr"].sum().reset_index().sort_values("revenue_inr", ascending=True)
    fig_store = px.bar(store_agg, x="revenue_inr", y="store_name", orientation="h",
                       color="revenue_inr", color_continuous_scale="Blues",
                       labels={"revenue_inr": "Revenue (INR)", "store_name": "Store"})
    fig_store.update_layout(height=380, showlegend=False)
    st.plotly_chart(fig_store, use_container_width=True)

with r1_col2:
    st.subheader("🏷️ Revenue by Category")
    cat_agg = filt_df.groupby("category_name")["revenue_inr"].sum().reset_index().sort_values("revenue_inr", ascending=False)
    fig_cat = px.pie(cat_agg, values="revenue_inr", names="category_name", hole=0.45,
                     color_discrete_sequence=px.colors.qualitative.Prism)
    fig_cat.update_layout(height=380)
    st.plotly_chart(fig_cat, use_container_width=True)

# Charts Row 2: Slicing by Day of Week & Slicing by Month
r2_col1, r2_col2 = st.columns(2)

with r2_col1:
    st.subheader("📅 Revenue by Day of the Week")
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    dow_agg = filt_df.groupby("day_of_week")["revenue_inr"].sum().reindex(days_order).reset_index()
    fig_dow = px.bar(dow_agg, x="day_of_week", y="revenue_inr", color="revenue_inr",
                     color_continuous_scale="Viridis", labels={"revenue_inr": "Revenue (INR)", "day_of_week": "Day"})
    fig_dow.update_layout(height=350, showlegend=False)
    st.plotly_chart(fig_dow, use_container_width=True)

with r2_col2:
    st.subheader("📈 Monthly Revenue Trend (2024)")
    m_agg = df.groupby("month_str")["revenue_inr"].sum().reset_index()
    fig_month = px.line(m_agg, x="month_str", y="revenue_inr", markers=True,
                        labels={"month_str": "Month", "revenue_inr": "Revenue (INR)"})
    fig_month.update_traces(line_color="#38bdf8", line_width=3)
    fig_month.update_layout(height=350)
    st.plotly_chart(fig_month, use_container_width=True)
