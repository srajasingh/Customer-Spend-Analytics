<div align="center">

# Customer Spend Analytics &nbsp;|&nbsp; Amazon India

End-to-end retail analytics: **Python ETL &rarr; SQLite &rarr; SQL views &rarr; Power BI / interactive HTML dashboard**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Pandas](https://img.shields.io/badge/Pandas-2.x-150458?logo=pandas&logoColor=white)](https://pandas.pydata.org/)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite&logoColor=white)](https://sqlite.org/)
[![Plotly](https://img.shields.io/badge/Plotly-2.35-3F4F75?logo=plotly&logoColor=white)](https://plotly.com/)
[![Power BI](https://img.shields.io/badge/Power%20BI-ready-F2C811?logo=powerbi&logoColor=black)](https://powerbi.microsoft.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

<sub>108k+ orders &middot; 9k+ customer proxies &middot; RFM segmentation &middot; anomaly detection</sub>

<img src="images/overview.png" alt="Executive Overview" width="92%"/>

</div>

---

## TL;DR

A reproducible analytics pipeline that ingests the **Amazon India Sale Report**, cleans it,
builds an **RFM** customer model, materialises business **SQL views**, exports them as
**Power BI**&ndash;ready CSVs, and visualises everything in a **4-page interactive HTML
dashboard**.

```
raw CSV (128k rows)
   |--> [ ETL pipeline.py ] --> SQLite (transactions, customers, products, cancelled)
                                   |--> [ analysis_views.sql ] --> 10 business views
                                                                       |--> CSV exports (Power BI)
                                                                       |--> JSON bundle (HTML dashboard)
```

---

## Highlights

| Metric             | Value          |
| ------------------ | -------------- |
| Orders processed   | **100,727**    |
| Customer proxies   | **9,021**      |
| Total revenue      | **&#8377;7.17 Cr** |
| Avg order value    | **&#8377;712**     |
| Cancellation rate  | **9.66%**      |
| RFM segments       | 6 (Champions, Loyal, At Risk, Lost, Potential, New) |
| Top state          | Maharashtra (&#8377;1.22 Cr) |

---

## Dashboard tour

### 1. Executive Overview
KPI cards, monthly revenue + order trend (dual-axis), top 10 states, country mix, segment distribution.

![Executive Overview](images/overview.png)

### 2. Customer Segmentation
RFM donut, log-log frequency-vs-monetary scatter coloured by segment, segment economics table, top-20 high-value customers.

![Customer Segmentation](images/segmentation.png)

### 3. Product &amp; Spend
Top-20 SKUs by revenue, category &times; style treemap (drill-down), category performance table, units-by-category. Slicer narrows every chart to a single category.

![Product and Spend Analysis](images/products.png)

### 4. Anomalies &amp; Risk
Spend-spike flags (peak order > 200% of personal average), cancellations by state, cancellation KPIs.

![Anomalies and Risk Flags](images/anomalies.png)

---

## Tech stack

| Layer            | Tool                            | Purpose                                  |
| ---------------- | ------------------------------- | ---------------------------------------- |
| ETL              | Python, Pandas, NumPy           | Clean, transform, RFM scoring            |
| Storage          | SQLite                          | Structured analytics layer (Power BI &harr; MySQL swappable) |
| Business logic   | SQL views                       | KPIs, segments, anomalies                |
| Visualisation    | Plotly.js (single-file HTML)    | 4-page interactive dashboard             |
| BI hand-off      | CSV exports (one per view)      | Drop into Power BI / Tableau / Excel     |

---

## Project structure

```
customer-spend-analytics/
+-- data/
|   +-- amazon_sale_report.csv        # raw input
+-- etl/
|   +-- etl_pipeline.py               # clean + RFM + load to SQLite
|   +-- export_views.py               # dump views as CSV + dashboard JSON
+-- sql/
|   +-- schema.sql                    # indexes + canonical column contract
|   +-- analysis_views.sql            # 10 business views
+-- db/
|   +-- analytics.db                  # generated SQLite (gitignored)
+-- exports/                          # one CSV per view  -> import into Power BI
+-- dashboard/
|   +-- index.html                    # interactive Plotly dashboard
|   +-- data.json                     # pre-aggregated bundle
+-- images/                           # screenshots used in this README
+-- requirements.txt
+-- LICENSE
+-- README.md
```

---

## Quick start

```bash
# 0) Get the raw data (66 MB, not committed - GitHub's 50 MB warning)
#    Kaggle: https://www.kaggle.com/datasets/thedevastator/unlocking-amazon-s-sales-secrets-a-comprehensive
#    Save as: data/amazon_sale_report.csv

# 1) Install deps
pip install -r requirements.txt

# 2) Run the ETL (raw CSV -> SQLite)
python etl/etl_pipeline.py \
    --input data/amazon_sale_report.csv \
    --db    db/analytics.db

# 3) Export views (CSV + dashboard JSON)
python etl/export_views.py

# 4) Launch the dashboard
python -m http.server 3000 --directory dashboard
# open http://localhost:3000
```

---

## What the ETL does

1. **Extract** the raw Amazon CSV; drop `Unnamed`/`index` cruft; snake-case columns.
2. **Clean**
   * parse `Date` (`mm-dd-yy`)
   * drop rows with no usable `amount` / `date` / `order_id`
   * isolate `Status = Cancelled` rows into `cancelled_orders` (Risk page)
   * filter non-positive `qty` / `amount`
   * title-case `ship_state` / `ship_city`
3. **Engineer** derived columns: `year`, `month`, `year_month`, `day_of_week`, `total_amount`.
4. **RFM segmentation** by `ship_postal_code` (customer proxy &mdash; the source feed has no
   real customer id). Quintile-scored Recency / Frequency / Monetary &rarr; label
   (Champions, Loyal, At Risk, Lost, Potential, New / Promising) + top-20% `is_high_value` flag.
5. **Load** four tables and execute `schema.sql` + `analysis_views.sql`.

---

## SQL views

| View                       | Purpose                                              |
| -------------------------- | ---------------------------------------------------- |
| `vw_kpis`                  | Total revenue, orders, customers, AOV, cancel rate   |
| `vw_monthly_revenue`       | Revenue / orders / customers by month                |
| `vw_customer_segments`     | Customer count + economics per RFM segment           |
| `vw_top_products`          | Top 20 SKUs by revenue                               |
| `vw_top_customers`         | Top 20 high-value customers                          |
| `vw_country_spend`         | Country totals                                       |
| `vw_state_spend`           | India ship-state totals                              |
| `vw_category_spend`        | Garment-category totals                              |
| `vw_anomalous_customers`   | Customers whose peak order > 200% of personal avg    |
| `vw_cancellation_by_state` | Cancelled order counts &amp; value by state          |

Every view is also dumped to `exports/<view>.csv` so you can build a Power BI
report directly: **Get Data &rarr; Folder &rarr; exports/**.

---

## Resume bullets

* Built an end-to-end **ETL pipeline in Python** processing **128k+ retail
  transactions**, loading cleaned data into a relational **SQLite** store
  with indexed schema for downstream analytics.
* Engineered **RFM-based customer segmentation** (Recency, Frequency, Monetary)
  to classify 9k+ customers into 6 risk/value tiers, surfacing **2,554
  Champions and 1,116 At-Risk** buyers.
* Designed a **4-page interactive dashboard** (Plotly) plus **Power BI&ndash;ready
  SQL views/CSVs** with KPI tracking, geographic trends, and anomaly flagging
  for cancelled orders and spend spikes.

---

## License

[MIT](LICENSE)
