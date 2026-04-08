# Basket Craft Sales Pipeline — Design Spec

**Date:** 2026-04-08
**Project:** basket-craft-pipeline
**Status:** Approved

---

## Overview

Build an ETL data pipeline that extracts sales data from the Basket Craft MySQL database, transforms it using dbt, and loads a monthly sales summary into a local PostgreSQL instance running in Docker. The final output is a `monthly_sales_summary` mart table that powers a sales dashboard showing revenue, order counts, and average order value grouped by product and month.

---

## 1. Pipeline Architecture

The pipeline follows a five-stage ETL pattern:

```
SOURCE → EXTRACT → TRANSFORM → LOAD → DESTINATION
```

| Stage | Tool | Responsibility |
|---|---|---|
| Source | MySQL (`db.isba.co`) | Live basket_craft transactional database |
| Extract | Python + SQLAlchemy | Read orders, order_items, products from MySQL; write to `raw` schema in PostgreSQL |
| Transform | dbt staging models | Clean, cast, and join raw tables into analysis-ready staging models |
| Load | dbt mart models | Aggregate staging models into `marts.monthly_sales_summary` |
| Destination | PostgreSQL (Docker) | Local data warehouse with `raw`, `staging`, and `marts` schemas |

**Tables extracted from MySQL:** `orders`, `order_items`, `products`
All other tables (`users`, `website_sessions`, `website_pageviews`, `employees`, `order_item_refunds`) are out of scope for this dashboard.

---

## 2. File Structure

```
basket-craft-pipeline/
├── .env                          # DB credentials (git-ignored)
├── docker-compose.yml            # PostgreSQL container definition
├── requirements.txt              # Python + dbt dependencies
│
├── extract/
│   └── extract.py                # Connects to MySQL, reads 3 tables,
│                                 # bulk-inserts into raw.* schema in PostgreSQL
│
└── dbt_project/
    ├── dbt_project.yml           # Project name, model paths, schema config
    ├── profiles.yml              # dbt connection profile → local PostgreSQL
    ├── sources.yml               # Declares raw.orders, raw.order_items, raw.products
    │
    └── models/
        ├── staging/
        │   ├── stg_orders.sql        # Casts created_at, renames columns, filters nulls
        │   ├── stg_order_items.sql   # Casts price_usd/cogs_usd to NUMERIC
        │   └── stg_products.sql      # Selects product_id, product_name
        │
        └── marts/
            └── monthly_sales_summary.sql  # Final aggregation by product + month
```

---

## 3. Table Schemas

### Raw Schema (loaded by extract.py)

**`raw.orders`**
| Column | Type |
|---|---|
| order_id | INTEGER |
| created_at | TIMESTAMP |
| website_session_id | INTEGER |
| user_id | INTEGER |
| primary_product_id | INTEGER |
| items_purchased | INTEGER |
| price_usd | NUMERIC |
| cogs_usd | NUMERIC |

**`raw.order_items`**
| Column | Type |
|---|---|
| order_item_id | INTEGER |
| created_at | TIMESTAMP |
| order_id | INTEGER |
| product_id | INTEGER |
| is_primary_item | BOOLEAN |
| price_usd | NUMERIC |
| cogs_usd | NUMERIC |

**`raw.products`**
| Column | Type |
|---|---|
| product_id | INTEGER |
| created_at | TIMESTAMP |
| product_name | VARCHAR |
| description | TEXT |

### Mart Schema (materialized by dbt)

**`marts.monthly_sales_summary`**
| Column | Type | Description |
|---|---|---|
| product_name | VARCHAR | From `products.product_name` — grouping dimension |
| month | DATE | First day of month (`DATE_TRUNC('month', created_at)`) |
| revenue_usd | NUMERIC | `SUM(order_items.price_usd)` |
| order_count | INTEGER | `COUNT(DISTINCT orders.order_id)` |
| avg_order_value_usd | NUMERIC | `revenue_usd / order_count` |

### Aggregation SQL

```sql
SELECT
    p.product_name,
    DATE_TRUNC('month', o.created_at)              AS month,
    SUM(oi.price_usd)                              AS revenue_usd,
    COUNT(DISTINCT o.order_id)                     AS order_count,
    SUM(oi.price_usd)
        / NULLIF(COUNT(DISTINCT o.order_id), 0)    AS avg_order_value_usd
FROM   {{ ref('stg_order_items') }}  oi
JOIN   {{ ref('stg_orders') }}       o  ON oi.order_id   = o.order_id
JOIN   {{ ref('stg_products') }}     p  ON oi.product_id = p.product_id
GROUP  BY 1, 2
ORDER  BY 2, 1
```

---

## 4. Docker & Credential Configuration

### docker-compose.yml

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: pipeline
      POSTGRES_PASSWORD: pipeline
      POSTGRES_DB: basket_craft_dw
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

### .env (git-ignored)

```
MYSQL_HOST=db.isba.co
MYSQL_PORT=3306
MYSQL_USER=analyst
MYSQL_PASSWORD=go_lions
MYSQL_DATABASE=basket_craft

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=pipeline
POSTGRES_PASSWORD=pipeline
POSTGRES_DB=basket_craft_dw
```

Both `extract.py` and `dbt profiles.yml` read credentials from `.env` via `python-dotenv`.

### .gitignore additions

```
.env
dbt_project/profiles.yml
```

---

## 5. Error Handling & Testing Strategy

### extract.py

- Wrap MySQL connection in `try/except` with a clear error message if the remote DB is unreachable
- Log row counts after each table load to verify completeness
- Use `CREATE TABLE IF NOT EXISTS` so the script is idempotent (safe to re-run)

### dbt

- `sources.yml` includes `dbt source freshness` checks — warns if raw tables are stale
- Built-in `not_null` and `unique` tests on `order_id`, `product_id`, `order_item_id`
- `dbt test` runs after every `dbt run` to validate mart output

### Manual Verification

- Spot-check `monthly_sales_summary` by summing a known month directly in MySQL and comparing totals

---

## 6. Run Order

```bash
# 1. Start PostgreSQL
docker compose up -d

# 2. Extract from MySQL → load into raw schema
python extract/extract.py

# 3. Build staging + mart models
cd dbt_project
dbt run
dbt test
```

---

## Out of Scope

- Dashboard visualization layer (e.g. Metabase, Superset) — pipeline ends at the mart table
- Scheduling / orchestration (Airflow, cron) — pipeline is run manually
- Refunds adjustment to revenue — `order_item_refunds` table excluded for now
- User or session-level analytics
