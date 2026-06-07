-- ============================================================
-- Customer Spend Analytics  -  Schema (SQLite-compatible)
-- ============================================================
-- The ETL pipeline (etl_pipeline.py) creates the base tables
-- with `to_sql`. The DDL below adds indexes that improve view
-- performance and documents the canonical column contract.
-- ============================================================

-- transactions ---------------------------------------------------
-- Grain: one row per Amazon order line item (post-clean).
-- Columns expected:
--   order_id           TEXT     Amazon Order ID
--   customer_id        TEXT     ship-postal-code used as proxy id
--   sku                TEXT     SKU
--   style              TEXT     Style code
--   category           TEXT     Garment category (Set, Kurta ...)
--   qty                INTEGER  Units in the line
--   amount             REAL     Line amount (INR)
--   total_amount       REAL     Line revenue (== amount)
--   date               TEXT     ISO date
--   year, month        INTEGER
--   year_month         TEXT     'YYYY-MM'
--   day_of_week        TEXT
--   status             TEXT
--   fulfilment         TEXT     Amazon | Merchant
--   ship_city          TEXT
--   ship_state         TEXT
--   ship_postal_code   REAL
--   ship_country       TEXT
--   b2b                INTEGER  0/1
CREATE INDEX IF NOT EXISTS ix_tx_date         ON transactions(date);
CREATE INDEX IF NOT EXISTS ix_tx_yearmonth    ON transactions(year_month);
CREATE INDEX IF NOT EXISTS ix_tx_customer     ON transactions(customer_id);
CREATE INDEX IF NOT EXISTS ix_tx_state        ON transactions(ship_state);
CREATE INDEX IF NOT EXISTS ix_tx_category     ON transactions(category);

-- customers ------------------------------------------------------
-- Grain: one row per ship_postal_code (customer proxy).
--   customer_id        TEXT
--   recency_days       INTEGER
--   frequency          INTEGER
--   monetary           REAL
--   r_score, f_score, m_score  INTEGER (1-5)
--   rfm_score          TEXT   e.g. '555'
--   rfm_total          INTEGER (3-15)
--   segment            TEXT   Champions | Loyal | At Risk | Lost ...
--   is_high_value      INTEGER 0/1
--   country, state, city TEXT
CREATE INDEX IF NOT EXISTS ix_cust_segment    ON customers(segment);
CREATE INDEX IF NOT EXISTS ix_cust_highvalue  ON customers(is_high_value);

-- products -------------------------------------------------------
-- Grain: one row per (sku, style, category)
--   sku, style, category    TEXT
--   units_sold              INTEGER
--   revenue                 REAL
--   orders                  INTEGER
CREATE INDEX IF NOT EXISTS ix_prod_category   ON products(category);

-- cancelled_orders ----------------------------------------------
-- Grain: one row per cancelled order line, used for risk page.
CREATE INDEX IF NOT EXISTS ix_can_state       ON cancelled_orders(ship_state);
