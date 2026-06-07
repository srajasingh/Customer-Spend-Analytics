"""
Export each SQL view to a CSV file for Power BI ingestion,
and emit a compact JSON bundle used by the HTML dashboard.
"""
import json
import sqlite3
from pathlib import Path

import pandas as pd

ROOT      = Path(__file__).resolve().parent.parent
DB_PATH   = ROOT / "db" / "analytics.db"
EXPORTS   = ROOT / "exports"
DASH_DIR  = ROOT / "dashboard"
EXPORTS.mkdir(exist_ok=True)
DASH_DIR.mkdir(exist_ok=True)

VIEWS = [
    "vw_kpis",
    "vw_monthly_revenue",
    "vw_customer_segments",
    "vw_top_products",
    "vw_top_customers",
    "vw_country_spend",
    "vw_state_spend",
    "vw_category_spend",
    "vw_anomalous_customers",
    "vw_cancellation_by_state",
]

con = sqlite3.connect(DB_PATH)
bundle = {}

for v in VIEWS:
    df = pd.read_sql(f"SELECT * FROM {v}", con)
    out = EXPORTS / f"{v}.csv"
    df.to_csv(out, index=False)
    bundle[v] = df.to_dict(orient="records")
    print(f"  exported {v}: {len(df):>5} rows -> {out.name}")

# Scatter source - per-customer frequency vs monetary, sampled if big
cust = pd.read_sql(
    "SELECT customer_id, segment, frequency, monetary, recency_days "
    "FROM customers", con)
if len(cust) > 4000:
    cust = cust.sample(4000, random_state=42)
bundle["customers_scatter"] = cust.to_dict(orient="records")

# Treemap source - category -> style -> revenue (top 60)
treemap = pd.read_sql("""
    SELECT category, style, SUM(total_amount) AS revenue
    FROM transactions
    GROUP BY category, style
    ORDER BY revenue DESC
    LIMIT 60
""", con)
bundle["category_style_treemap"] = treemap.to_dict(orient="records")

con.close()

with open(DASH_DIR / "data.json", "w") as f:
    json.dump(bundle, f, default=str)
print(f"\nWrote dashboard bundle: {DASH_DIR / 'data.json'}")
