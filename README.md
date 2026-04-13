# Basket Craft Pipeline

An ETL pipeline that extracts monthly sales data from a remote MySQL database, transforms it with dbt, and loads a summary into a local PostgreSQL instance.

**Final output:** `monthly_sales_summary` — revenue, order count, and average order value per product per month.

---

## How It Works

```
MySQL (remote)          PostgreSQL (local Docker)
─────────────           ─────────────────────────────────────────
orders          ──┐
order_items     ──┼──► public.orders / order_items / products
products        ──┘         │
                            ▼
                    dbt staging views
                    (type casts + null filters)
                            │
                            ▼
                    public.monthly_sales_summary
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

**4. Create `dbt_project/profiles.yml`**

```yaml
basket_craft:
  target: dev
  outputs:
    dev:
      type: postgres
      host: localhost
      port: 5432
      user: pipeline
      password: pipeline
      dbname: basket_craft_dw
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

```bash
# Activate the virtual environment
source .venv/bin/activate

# Step 1: Extract from MySQL into PostgreSQL
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
| pytest | Unit and integration tests |
