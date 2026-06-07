"""
Customer Spend Analytics - ETL Pipeline
=======================================
Reads the raw Amazon India Sale Report CSV, cleans + enriches it,
performs RFM segmentation (ship-postal-code as customer proxy),
and loads three normalised tables (transactions, customers, products)
into a SQLite database.

Usage
-----
    python etl_pipeline.py \
        --input  ../data/amazon_sale_report.csv \
        --db     ../db/analytics.db
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# 1. EXTRACT
# ---------------------------------------------------------------------------
def extract(csv_path: Path) -> pd.DataFrame:
    print(f"[extract] Reading {csv_path} ...")
    df = pd.read_csv(csv_path, low_memory=False)
    # Drop stray unnamed/index columns coming from the source dump
    df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed") or c == "index"],
                 errors="ignore")
    # Normalise column names: lower_snake_case
    df.columns = (df.columns
                    .str.strip()
                    .str.lower()
                    .str.replace("-", "_", regex=False)
                    .str.replace(" ", "_", regex=False))
    print(f"[extract] Loaded {len(df):,} rows, {len(df.columns)} columns")
    return df


# ---------------------------------------------------------------------------
# 2. TRANSFORM
# ---------------------------------------------------------------------------
def clean(df: pd.DataFrame) -> pd.DataFrame:
    print("[clean] Removing cancelled / invalid / B2B rows ...")
    df = df.copy()

    # Standardise dtypes
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["qty"]    = pd.to_numeric(df["qty"], errors="coerce").fillna(0).astype(int)
    df["date"]   = pd.to_datetime(df["date"], format="%m-%d-%y", errors="coerce")

    # Drop rows with no usable amount or date
    df = df.dropna(subset=["amount", "date", "order_id"])
    # Drop cancelled / pending orders for the spend-side analysis
    cancelled_mask = df["status"].str.contains("Cancelled", case=False, na=False)
    cancelled_df   = df[cancelled_mask].copy()        # keep for anomalies page
    df             = df[~cancelled_mask]

    # Remove non-positive transactions
    df = df[(df["amount"] > 0) & (df["qty"] > 0)]

    # Trim text
    for c in ["ship_city", "ship_state", "category", "sku", "style", "fulfilment"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    df["ship_state"] = df["ship_state"].str.title()
    df["ship_city"]  = df["ship_city"].str.title()

    print(f"[clean] Kept {len(df):,} valid spend rows, "
          f"set aside {len(cancelled_df):,} cancelled rows")
    return df, cancelled_df


def engineer(df: pd.DataFrame) -> pd.DataFrame:
    print("[engineer] Adding derived fields ...")
    df = df.copy()
    df["total_amount"] = df["amount"] * 1.0                # already line total in this feed
    df["year"]         = df["date"].dt.year
    df["month"]        = df["date"].dt.month
    df["year_month"]   = df["date"].dt.to_period("M").astype(str)
    df["day_of_week"]  = df["date"].dt.day_name()
    return df


# ---------------------------------------------------------------------------
# 3. RFM SEGMENTATION
# ---------------------------------------------------------------------------
def build_customers(df: pd.DataFrame) -> pd.DataFrame:
    """
    The Amazon feed has no real customer_id. We use ship_postal_code as a
    customer proxy (per the project plan). Aggregates compute Recency,
    Frequency, Monetary -> RFM score -> segment label.
    """
    print("[rfm] Building customer table via ship_postal_code proxy ...")
    df = df.dropna(subset=["ship_postal_code"]).copy()
    df["customer_id"] = df["ship_postal_code"].astype(float).astype(int).astype(str)

    snapshot_date = df["date"].max() + pd.Timedelta(days=1)

    cust = (df.groupby("customer_id")
              .agg(recency_days = ("date",       lambda s: (snapshot_date - s.max()).days),
                   frequency    = ("order_id",   "nunique"),
                   monetary     = ("total_amount", "sum"),
                   country      = ("ship_country", "first"),
                   state        = ("ship_state",   "first"),
                   city         = ("ship_city",    "first"))
              .reset_index())

    # 1-5 quintile scoring. Recency: low days = better (5). F/M: high = better (5).
    def qscore(s: pd.Series, ascending: bool) -> pd.Series:
        try:
            q = pd.qcut(s.rank(method="first"), 5, labels=[1, 2, 3, 4, 5])
        except ValueError:
            q = pd.Series([3] * len(s), index=s.index)
        q = q.astype(int)
        return (6 - q) if not ascending else q

    cust["r_score"] = qscore(cust["recency_days"], ascending=False)
    cust["f_score"] = qscore(cust["frequency"],    ascending=True)
    cust["m_score"] = qscore(cust["monetary"],     ascending=True)
    cust["rfm_score"] = (cust["r_score"].astype(str) +
                         cust["f_score"].astype(str) +
                         cust["m_score"].astype(str))
    cust["rfm_total"] = cust["r_score"] + cust["f_score"] + cust["m_score"]

    def segment(row):
        r, f, m = row["r_score"], row["f_score"], row["m_score"]
        if r >= 4 and f >= 4 and m >= 4:
            return "Champions"
        if r >= 3 and f >= 3:
            return "Loyal"
        if r >= 4 and f <= 2:
            return "New / Promising"
        if r <= 2 and f >= 3:
            return "At Risk"
        if r <= 2 and f <= 2:
            return "Lost"
        return "Potential"

    cust["segment"] = cust.apply(segment, axis=1)

    # High-value flag = top 20% monetary
    cutoff = cust["monetary"].quantile(0.80)
    cust["is_high_value"] = (cust["monetary"] >= cutoff).astype(int)

    print(f"[rfm] {len(cust):,} customer rows, "
          f"high-value cutoff = {cutoff:,.0f}")
    return cust


# ---------------------------------------------------------------------------
# 4. TRANSACTIONS + PRODUCTS
# ---------------------------------------------------------------------------
def build_transactions(df: pd.DataFrame) -> pd.DataFrame:
    print("[transactions] Materialising transactions table ...")
    t = df.copy()
    t["customer_id"] = t["ship_postal_code"].astype(float, errors="ignore")
    t["customer_id"] = t["customer_id"].astype("Int64").astype(str)

    cols = ["order_id", "customer_id", "sku", "style", "category",
            "qty", "amount", "total_amount", "date", "year", "month",
            "year_month", "day_of_week", "status", "fulfilment",
            "ship_city", "ship_state", "ship_postal_code", "ship_country",
            "b2b"]
    t = t[[c for c in cols if c in t.columns]]
    return t


def build_products(df: pd.DataFrame) -> pd.DataFrame:
    print("[products] Materialising products table ...")
    p = (df.groupby(["sku", "style", "category"], dropna=False)
           .agg(units_sold = ("qty",          "sum"),
                revenue    = ("total_amount", "sum"),
                orders     = ("order_id",     "nunique"))
           .reset_index())
    return p


# ---------------------------------------------------------------------------
# 5. LOAD
# ---------------------------------------------------------------------------
def load_sqlite(db_path: Path, transactions, customers, products, cancelled):
    print(f"[load] Writing SQLite -> {db_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    con = sqlite3.connect(db_path)
    transactions.to_sql("transactions", con, index=False, if_exists="replace")
    customers.to_sql   ("customers",    con, index=False, if_exists="replace")
    products.to_sql    ("products",     con, index=False, if_exists="replace")
    cancelled.to_sql   ("cancelled_orders", con, index=False, if_exists="replace")

    # Run schema/index DDL
    schema_path = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"
    if schema_path.exists():
        con.executescript(schema_path.read_text())
    # Create analysis views
    views_path = Path(__file__).resolve().parent.parent / "sql" / "analysis_views.sql"
    if views_path.exists():
        con.executescript(views_path.read_text())
    con.commit()
    con.close()
    print("[load] Done")


# ---------------------------------------------------------------------------
# 6. MAIN
# ---------------------------------------------------------------------------
def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(here.parent / "data" / "amazon_sale_report.csv"))
    ap.add_argument("--db",    default=str(here.parent / "db"   / "analytics.db"))
    args = ap.parse_args()

    raw                = extract(Path(args.input))
    cleaned, cancelled = clean(raw)
    enriched           = engineer(cleaned)
    customers          = build_customers(enriched)
    transactions       = build_transactions(enriched)
    products           = build_products(enriched)

    # Tidy cancelled: keep useful cols only
    cancelled = cancelled[["order_id", "date", "category", "sku",
                           "ship_city", "ship_state", "ship_country",
                           "qty", "amount", "status"]].copy()
    cancelled["date"] = pd.to_datetime(cancelled["date"], errors="coerce")

    load_sqlite(Path(args.db), transactions, customers, products, cancelled)

    print("\n=== Summary ===")
    print(f" transactions     : {len(transactions):>10,}")
    print(f" customers        : {len(customers):>10,}")
    print(f" products         : {len(products):>10,}")
    print(f" cancelled_orders : {len(cancelled):>10,}")
    print(f" segments         : {customers['segment'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
