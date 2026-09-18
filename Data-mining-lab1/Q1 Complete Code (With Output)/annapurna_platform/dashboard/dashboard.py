"""
dashboard.py  –  Streamlit dashboard (optional but impressive)
=============================================================
Revenue sliced by store / category / day-of-week / month.

Run:
    pip install streamlit plotly
    streamlit run scripts/dashboard.py
"""

import os
import io
import pandas as pd
import streamlit as st
import plotly.express as px
import duckdb
from minio import Minio

# ── Page config ────────────────────────────────────────────────
st.set_page_config(
    page_title="Annapurna Stores – Revenue Dashboard",
    page_icon="🛒",
    layout="wide",
)

# ── Styling ────────────────────────────────────────────────────
st.markdown("""
<style>
    body { background: #0f1117; }
    .metric-card {
        background: linear-gradient(135deg, #1e3a5f, #0d2137);
        border: 1px solid #2a5480;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
    .metric-value { font-size: 2rem; font-weight: 700; color: #4fc3f7; }
    .metric-label { font-size: 0.9rem; color: #90a4ae; }
</style>
""", unsafe_allow_html=True)

# ── Title ──────────────────────────────────────────────────────
st.title("🛒 Annapurna Stores – Revenue Intelligence")
st.caption("Single source of truth. October is October. Always.")

# ── Load data ──────────────────────────────────────────────────
MINIO_ENDPOINT = "localhost:9000"
BUCKET_NAME    = "annapurna-sales"

@st.cache_data(ttl=300)
def load_fact_sales():
    minio_client = Minio(MINIO_ENDPOINT, access_key="minioadmin", secret_key="minioadmin", secure=False)
    objects = list(minio_client.list_objects(BUCKET_NAME, prefix="sales/", recursive=True))
    frames = []
    for obj in objects:
        resp = minio_client.get_object(BUCKET_NAME, obj.object_name)
        data = resp.read(); resp.close()
        if obj.object_name.endswith(".parquet"):
            df = pd.read_parquet(io.BytesIO(data))
        else:
            df = pd.read_csv(io.StringIO(data.decode("utf-8")))
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)
    raw = raw.drop_duplicates(subset=["bill_number","product_code","timestamp"], keep="first")
    raw = raw[raw["line_type"] == "SALE"].copy()
    raw["sale_date"]  = pd.to_datetime(raw["sale_date"])
    raw["sale_month"] = raw["sale_date"].dt.month
    raw["sale_year"]  = raw["sale_date"].dt.year
    raw["day_name"]   = raw["sale_date"].dt.day_name()
    raw["revenue"]    = raw["quantity"] * raw["unit_price"]
    return raw

with st.spinner("Loading from MinIO…"):
    df = load_fact_sales()

# ── Sidebar filters ────────────────────────────────────────────
st.sidebar.header("🔍 Filters")
years   = sorted(df["sale_year"].unique())
year    = st.sidebar.selectbox("Year", years, index=len(years)-1)
months  = sorted(df[df["sale_year"]==year]["sale_month"].unique())
month   = st.sidebar.selectbox("Month", months, index=len(months)-1)
stores  = ["All"] + sorted(df["store_code"].unique().tolist())
store   = st.sidebar.selectbox("Store", stores)

filt = df[(df["sale_year"]==year) & (df["sale_month"]==month)]
if store != "All":
    filt = filt[filt["store_code"]==store]

# ── KPI row ────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Revenue (INR)", f"₹{filt['revenue'].sum():,.0f}")
col2.metric("Total Transactions",  f"{filt['bill_number'].nunique():,}")
col3.metric("Stores Active",       f"{filt['store_code'].nunique()}")
col4.metric("Products Sold",       f"{filt['product_code'].nunique()}")

st.divider()

# ── Charts ─────────────────────────────────────────────────────
c1, c2 = st.columns(2)

with c1:
    st.subheader("Revenue by Store")
    by_store = filt.groupby("store_code")["revenue"].sum().reset_index().sort_values("revenue", ascending=True)
    fig = px.bar(by_store, x="revenue", y="store_code", orientation="h",
                 color="revenue", color_continuous_scale="Blues",
                 labels={"revenue": "Revenue (INR)", "store_code": "Store"})
    fig.update_layout(plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
                      font_color="white", coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("Revenue by Day of Week")
    day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    by_day = filt.groupby("day_name")["revenue"].sum().reindex(day_order).reset_index()
    fig2 = px.bar(by_day, x="day_name", y="revenue",
                  color="revenue", color_continuous_scale="Viridis",
                  labels={"revenue": "Revenue (INR)", "day_name": "Day"})
    fig2.update_layout(plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
                       font_color="white", coloraxis_showscale=False)
    st.plotly_chart(fig2, use_container_width=True)

# ── Monthly trend ──────────────────────────────────────────────
st.subheader("Monthly Revenue Trend")
monthly = df[df["sale_year"]==year].groupby("sale_month")["revenue"].sum().reset_index()
monthly["month_name"] = pd.to_datetime(monthly["sale_month"], format="%m").dt.strftime("%b")
fig3 = px.area(monthly, x="month_name", y="revenue",
               color_discrete_sequence=["#4fc3f7"],
               labels={"revenue": "Revenue (INR)", "month_name": "Month"})
fig3.update_layout(plot_bgcolor="#0f1117", paper_bgcolor="#0f1117", font_color="white")
st.plotly_chart(fig3, use_container_width=True)

st.caption("Data sourced from MinIO (partitioned Parquet/CSV) + PostgreSQL masters. "
           "Revenue uses historical prices from price_revisions table. "
           "Duplicates and non-SALE lines excluded.")
