# Basket Craft Pipeline

An ETL pipeline that extracts data from a remote MySQL database and loads it into two PostgreSQL targets: a local Docker instance (transformed with dbt into a sales summary) and an AWS RDS instance (all 8 raw tables, no transformation).

**Transformed output:** `monthly_sales_summary` — revenue, order count, and average order value per product per month.
**Raw output:** All MySQL tables loaded as-is into AWS RDS for ad-hoc analysis.

---

## How It Works

```
MySQL (remote, db.isba.co)
│
├─► extract/extract.py ──► PostgreSQL (local Docker)
│      3 tables                  │
│      (orders, order_items,     ▼
│       products)         dbt staging views
│                         (type casts + null filters)
│                                │
│                                ▼
│                         public.monthly_sales_summary
│
└─► extract/extract_rds.py ──► AWS RDS PostgreSQL
       all 8 tables                 (raw, no transforms)
       auto-discovered
```

---

## Prerequisites

- Python 3.10+
- Docker Desktop (running)
- Access to the MySQL source database

---

## Setup

**1. Clone the repository**

```bash
git clone https://github.com/nquek/basket-craft-pipeline.git
cd basket-craft-pipeline
```

**2. Create the virtual environment and install dependencies**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**3. Create `.env` with database credentials**

```bash
# .env

# MySQL source (remote)
MYSQL_HOST=db.isba.co
MYSQL_PORT=3306
MYSQL_USER=analyst
MYSQL_PASSWORD=go_lions
MYSQL_DATABASE=basket_craft

# Local Docker PostgreSQL (used by extract.py and dbt)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=basket_craft

# AWS RDS PostgreSQL (used by extract_rds.py)
RDS_HOST=<your-rds-endpoint>.us-east-2.rds.amazonaws.com
RDS_PORT=5432
RDS_USER=student
RDS_PASSWORD=go_lions
RDS_DB=basket_craft
```

**4. Create `dbt_project/profiles.yml`**

```yaml
basket_craft:
  target: dev
  outputs:
    dev:
      type: postgres
      host: localhost
      port: 5432
      user: postgres
      password: postgres
      dbname: basket_craft
      schema: public
      threads: 1
```

> `.env` and `profiles.yml` are gitignored and must be created manually.

**5. Start the PostgreSQL container**

```bash
docker compose up -d
```

---

## Running the Pipeline

### Local pipeline (Docker → dbt)

```bash
source .venv/bin/activate

# Step 1: Extract from MySQL into local Docker PostgreSQL
python extract/extract.py

# Step 2: Transform with dbt
cd dbt_project
dbt run --profiles-dir .
dbt test --profiles-dir .
```

Expected output from `extract/extract.py`:
```
Creating raw schema...
Loading orders... 32313 rows loaded into public.orders
Loading order_items... 40025 rows loaded into public.order_items
Loading products... 4 rows loaded into public.products
Extract complete.
```

Expected output from `dbt run`:
```
1 of 4 OK created sql view model public.stg_order_items
2 of 4 OK created sql view model public.stg_orders
3 of 4 OK created sql view model public.stg_products
4 of 4 OK created sql table model public.monthly_sales_summary
```

### AWS RDS load (all raw tables)

```bash
source .venv/bin/activate
python extract/extract_rds.py
```

Expected output:
```
Discovered 8 tables: employees, order_item_refunds, order_items, orders, products, users, website_pageviews, website_sessions
Loading employees... 20 rows loaded into public.employees
Loading order_item_refunds... 1731 rows loaded into public.order_item_refunds
Loading order_items... 40025 rows loaded into public.order_items
Loading orders... 32313 rows loaded into public.orders
Loading products... 4 rows loaded into public.products
Loading users... 31696 rows loaded into public.users
Loading website_pageviews... 1188124 rows loaded into public.website_pageviews
Loading website_sessions... 472871 rows loaded into public.website_sessions
Extract complete.
```

---

## Running Tests

```bash
# All tests (requires Docker PostgreSQL running)
pytest tests/ -v

# Unit tests only (no database required)
pytest tests/ -v -m "not integration"
```

---

## Output Table

Query the final mart in psql or DBeaver:

```sql
SELECT product_name, month, revenue_usd, order_count, avg_order_value_usd
FROM public.monthly_sales_summary
ORDER BY month DESC, revenue_usd DESC;
```

| Column | Description |
|---|---|
| `product_name` | Gift basket product |
| `month` | First day of the month |
| `revenue_usd` | Total revenue for that product/month |
| `order_count` | Number of distinct orders |
| `avg_order_value_usd` | Revenue divided by order count |

---

## Tech Stack

| Tool | Purpose |
|---|---|
| Python + SQLAlchemy | Extract from MySQL, load into PostgreSQL |
| pandas | DataFrame-based bulk loading |
| dbt-postgres | Staging views + mart aggregation |
| Docker | Local PostgreSQL instance |
| AWS RDS (PostgreSQL) | Cloud-hosted raw data store |
| pytest | Unit and integration tests |
