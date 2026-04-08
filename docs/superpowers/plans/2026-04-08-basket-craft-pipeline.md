# Basket Craft Sales Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an ETL pipeline that extracts sales data from a remote MySQL database, transforms it with dbt, and loads a monthly sales summary into a local PostgreSQL Docker container.

**Architecture:** Python + SQLAlchemy extracts three MySQL tables (`orders`, `order_items`, `products`) and bulk-loads them into a `raw` schema in PostgreSQL. dbt then builds staging views (clean + typed) and a final `marts.monthly_sales_summary` table aggregating revenue, order count, and average order value by product and month.

**Tech Stack:** Python 3, SQLAlchemy 2, pandas, PyMySQL, psycopg2, python-dotenv, dbt-postgres 1.9, Docker, pytest

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `requirements.txt` | Create | Python + dbt dependencies |
| `.env` | Create (not committed) | DB credentials |
| `docker-compose.yml` | Create | PostgreSQL 16 container |
| `extract/__init__.py` | Create | Package marker |
| `extract/extract.py` | Create | MySQL → PostgreSQL raw schema loader |
| `tests/__init__.py` | Create | Package marker |
| `tests/test_extract.py` | Create | Unit tests for extract.py |
| `dbt_project/dbt_project.yml` | Create | dbt project config |
| `dbt_project/profiles.yml` | Create (not committed) | dbt → PostgreSQL connection |
| `dbt_project/models/staging/sources.yml` | Create | Declares raw.* source tables + freshness |
| `dbt_project/models/staging/stg_orders.sql` | Create | Cleans raw.orders |
| `dbt_project/models/staging/stg_order_items.sql` | Create | Cleans raw.order_items |
| `dbt_project/models/staging/stg_products.sql` | Create | Cleans raw.products |
| `dbt_project/models/staging/staging.yml` | Create | not_null + unique tests for staging |
| `dbt_project/models/marts/monthly_sales_summary.sql` | Create | Final aggregation |
| `dbt_project/models/marts/marts.yml` | Create | not_null tests for mart |

---

## Task 1: Python Virtual Environment and Dependencies

**Files:**
- Create: `requirements.txt`

- [ ] **Step 1: Create the virtual environment**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Expected: shell prompt now shows `(.venv)`.

- [ ] **Step 2: Create requirements.txt**

```
sqlalchemy==2.0.36
pymysql==1.1.1
psycopg2-binary==2.9.10
python-dotenv==1.0.1
pandas==2.2.3
dbt-postgres==1.9.0
pytest==8.3.4
```

- [ ] **Step 3: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without errors. Verify with:

```bash
python -c "import sqlalchemy, pymysql, psycopg2, dotenv, pandas, dbt; print('OK')"
```

Expected output: `OK`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "feat: add Python dependencies"
```

---

## Task 2: Docker PostgreSQL Container

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Write the failing connection test**

Create `tests/__init__.py` (empty) and `extract/__init__.py` (empty):

```bash
mkdir -p tests extract
touch tests/__init__.py extract/__init__.py
```

Create `tests/test_extract.py`:

```python
import pytest
from sqlalchemy import create_engine, text


PG_URL = "postgresql+psycopg2://pipeline:pipeline@localhost:5432/basket_craft_dw"


def test_postgres_is_reachable():
    engine = create_engine(PG_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
    assert result == 1
```

- [ ] **Step 2: Run test to verify it fails (Postgres not yet running)**

```bash
pytest tests/test_extract.py::test_postgres_is_reachable -v
```

Expected: FAIL with a connection refused error.

- [ ] **Step 3: Create docker-compose.yml**

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

- [ ] **Step 4: Start the container**

```bash
docker compose up -d
```

Wait 5 seconds for Postgres to initialize, then run:

```bash
docker compose ps
```

Expected: `postgres` container shows `running`.

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_extract.py::test_postgres_is_reachable -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml tests/__init__.py extract/__init__.py tests/test_extract.py
git commit -m "feat: add PostgreSQL Docker container and connection test"
```

---

## Task 3: Credentials File

**Files:**
- Create: `.env` (not committed — already in .gitignore)

- [ ] **Step 1: Create .env**

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

- [ ] **Step 2: Verify .env is git-ignored**

```bash
git status
```

Expected: `.env` does NOT appear in untracked files. If it does, add it:

```bash
echo ".env" >> .gitignore
git add .gitignore && git commit -m "chore: ignore .env"
```

---

## Task 4: Extract Script

**Files:**
- Create: `extract/extract.py`
- Modify: `tests/test_extract.py`

- [ ] **Step 1: Write failing tests for create_raw_schema and load_table**

Replace the contents of `tests/test_extract.py` with:

```python
import pytest
from unittest.mock import MagicMock, patch, call
import pandas as pd
from sqlalchemy import create_engine, text

from extract.extract import create_raw_schema, load_table


PG_URL = "postgresql+psycopg2://pipeline:pipeline@localhost:5432/basket_craft_dw"


def test_postgres_is_reachable():
    engine = create_engine(PG_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
    assert result == 1


def test_create_raw_schema_creates_schema():
    """create_raw_schema should create the 'raw' schema in PostgreSQL."""
    engine = create_engine(PG_URL)
    create_raw_schema(engine)
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name = 'raw'"
        )).fetchone()
    assert result is not None, "Schema 'raw' was not created"


def test_load_table_returns_correct_row_count():
    """load_table should return the number of rows loaded."""
    mock_mysql = MagicMock()
    mock_pg = MagicMock()
    fake_df = pd.DataFrame({
        "order_id": [1, 2, 3],
        "created_at": pd.to_datetime(["2024-01-01"] * 3),
        "price_usd": [10.0, 20.0, 30.0],
    })

    with patch("extract.extract.pd.read_sql", return_value=fake_df):
        count = load_table(mock_mysql, mock_pg, "orders", ["order_id", "created_at", "price_usd"])

    assert count == 3


def test_load_table_calls_to_sql_with_correct_args():
    """load_table should write to the correct schema and table in PostgreSQL."""
    mock_mysql = MagicMock()
    mock_pg = MagicMock()
    fake_df = pd.DataFrame({"order_id": [1]})

    with patch("extract.extract.pd.read_sql", return_value=fake_df) as mock_read:
        with patch.object(fake_df.__class__, "to_sql") as mock_to_sql:
            load_table(mock_mysql, mock_pg, "orders", ["order_id"])
            mock_to_sql.assert_called_once_with(
                "orders", mock_pg, schema="raw", if_exists="replace", index=False
            )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_extract.py -v
```

Expected: `test_create_raw_schema_creates_schema`, `test_load_table_returns_correct_row_count`, and `test_load_table_calls_to_sql_with_correct_args` FAIL with `ImportError: cannot import name 'create_raw_schema'`.

- [ ] **Step 3: Implement extract.py**

Create `extract/extract.py`:

```python
import os
import sys
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

MYSQL_URL = (
    f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}"
    f"@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DATABASE')}"
)

PG_URL = (
    f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
)

TABLES = {
    "orders": [
        "order_id", "created_at", "website_session_id", "user_id",
        "primary_product_id", "items_purchased", "price_usd", "cogs_usd",
    ],
    "order_items": [
        "order_item_id", "created_at", "order_id", "product_id",
        "is_primary_item", "price_usd", "cogs_usd",
    ],
    "products": [
        "product_id", "created_at", "product_name", "description",
    ],
}


def create_raw_schema(pg_engine):
    with pg_engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))
        conn.commit()


def load_table(mysql_engine, pg_engine, table_name, columns):
    col_list = ", ".join(columns)
    df = pd.read_sql(f"SELECT {col_list} FROM {table_name}", mysql_engine)
    row_count = len(df)
    df.to_sql(table_name, pg_engine, schema="raw", if_exists="replace", index=False)
    return row_count


def main():
    try:
        mysql_engine = create_engine(MYSQL_URL)
        mysql_engine.connect().close()
    except Exception as e:
        print(f"ERROR: Cannot connect to MySQL at {os.getenv('MYSQL_HOST')}: {e}")
        sys.exit(1)

    try:
        pg_engine = create_engine(PG_URL)
        pg_engine.connect().close()
    except Exception as e:
        print(f"ERROR: Cannot connect to PostgreSQL at {os.getenv('POSTGRES_HOST')}: {e}")
        sys.exit(1)

    print("Creating raw schema...")
    create_raw_schema(pg_engine)

    for table_name, columns in TABLES.items():
        print(f"Loading {table_name}...", end=" ", flush=True)
        count = load_table(mysql_engine, pg_engine, table_name, columns)
        print(f"{count} rows loaded into raw.{table_name}")

    print("Extract complete.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_extract.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add extract/extract.py tests/test_extract.py extract/__init__.py
git commit -m "feat: add extract script with unit tests"
```

---

## Task 5: Run the Extraction

- [ ] **Step 1: Run the extract script**

```bash
python extract/extract.py
```

Expected output:
```
Creating raw schema...
Loading orders... 1234 rows loaded into raw.orders
Loading order_items... 4567 rows loaded into raw.order_items
Loading products... 4 rows loaded into raw.products
Extract complete.
```

(Row counts will vary based on actual data.)

- [ ] **Step 2: Verify raw tables in PostgreSQL**

```bash
docker exec -it basket-craft-pipeline-postgres-1 psql -U pipeline -d basket_craft_dw -c "\dt raw.*"
```

Expected: three tables listed — `raw.orders`, `raw.order_items`, `raw.products`.

---

## Task 6: dbt Project Setup

**Files:**
- Create: `dbt_project/dbt_project.yml`
- Create: `dbt_project/profiles.yml` (not committed)

- [ ] **Step 1: Create the dbt project directory structure**

```bash
mkdir -p dbt_project/models/staging dbt_project/models/marts
```

- [ ] **Step 2: Create dbt_project.yml**

Create `dbt_project/dbt_project.yml`:

```yaml
name: basket_craft
version: '1.0.0'
config-version: 2

profile: basket_craft

model-paths: ["models"]

models:
  basket_craft:
    staging:
      +materialized: view
      +schema: staging
    marts:
      +materialized: table
      +schema: marts
```

- [ ] **Step 3: Create profiles.yml**

Create `dbt_project/profiles.yml`:

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
      schema: raw
      threads: 1
```

- [ ] **Step 4: Add profiles.yml to .gitignore**

Append to `.gitignore`:

```
dbt_project/profiles.yml
```

- [ ] **Step 5: Verify dbt can connect**

```bash
cd dbt_project && dbt debug
```

Expected: all checks show `OK`, ending with `All checks passed!`

- [ ] **Step 6: Commit**

```bash
cd ..
git add dbt_project/dbt_project.yml .gitignore
git commit -m "feat: initialize dbt project with PostgreSQL profile"
```

---

## Task 7: dbt Sources and Staging Models

**Files:**
- Create: `dbt_project/models/staging/sources.yml`
- Create: `dbt_project/models/staging/stg_orders.sql`
- Create: `dbt_project/models/staging/stg_order_items.sql`
- Create: `dbt_project/models/staging/stg_products.sql`
- Create: `dbt_project/models/staging/staging.yml`

- [ ] **Step 1: Create sources.yml**

Create `dbt_project/models/staging/sources.yml`:

```yaml
version: 2

sources:
  - name: raw
    schema: raw
    loaded_at_field: created_at
    freshness:
      warn_after: {count: 7, period: day}
      error_after: {count: 30, period: day}
    tables:
      - name: orders
      - name: order_items
      - name: products
```

- [ ] **Step 2: Create stg_orders.sql**

Create `dbt_project/models/staging/stg_orders.sql`:

```sql
SELECT
    order_id,
    created_at::TIMESTAMP   AS created_at,
    website_session_id,
    user_id,
    primary_product_id,
    items_purchased,
    price_usd::NUMERIC      AS price_usd,
    cogs_usd::NUMERIC       AS cogs_usd
FROM {{ source('raw', 'orders') }}
WHERE order_id IS NOT NULL
```

- [ ] **Step 3: Create stg_order_items.sql**

Create `dbt_project/models/staging/stg_order_items.sql`:

```sql
SELECT
    order_item_id,
    created_at::TIMESTAMP   AS created_at,
    order_id,
    product_id,
    is_primary_item::BOOLEAN AS is_primary_item,
    price_usd::NUMERIC       AS price_usd,
    cogs_usd::NUMERIC        AS cogs_usd
FROM {{ source('raw', 'order_items') }}
WHERE order_item_id IS NOT NULL
```

- [ ] **Step 4: Create stg_products.sql**

Create `dbt_project/models/staging/stg_products.sql`:

```sql
SELECT
    product_id,
    created_at::TIMESTAMP   AS created_at,
    product_name,
    description
FROM {{ source('raw', 'products') }}
WHERE product_id IS NOT NULL
```

- [ ] **Step 5: Create staging.yml with data tests**

Create `dbt_project/models/staging/staging.yml`:

```yaml
version: 2

models:
  - name: stg_orders
    columns:
      - name: order_id
        tests:
          - not_null
          - unique

  - name: stg_order_items
    columns:
      - name: order_item_id
        tests:
          - not_null
          - unique
      - name: order_id
        tests:
          - not_null
      - name: product_id
        tests:
          - not_null

  - name: stg_products
    columns:
      - name: product_id
        tests:
          - not_null
          - unique
      - name: product_name
        tests:
          - not_null
```

- [ ] **Step 6: Run dbt to build staging models**

```bash
cd dbt_project && dbt run --select staging
```

Expected: 3 models created (stg_orders, stg_order_items, stg_products), all showing `OK`.

- [ ] **Step 7: Run staging tests**

```bash
dbt test --select staging
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
cd ..
git add dbt_project/models/staging/
git commit -m "feat: add dbt staging models with data quality tests"
```

---

## Task 8: dbt Mart Model and Final Tests

**Files:**
- Create: `dbt_project/models/marts/monthly_sales_summary.sql`
- Create: `dbt_project/models/marts/marts.yml`

- [ ] **Step 1: Create monthly_sales_summary.sql**

Create `dbt_project/models/marts/monthly_sales_summary.sql`:

```sql
SELECT
    p.product_name,
    DATE_TRUNC('month', o.created_at)::DATE                AS month,
    SUM(oi.price_usd)                                      AS revenue_usd,
    COUNT(DISTINCT o.order_id)                             AS order_count,
    SUM(oi.price_usd)
        / NULLIF(COUNT(DISTINCT o.order_id), 0)            AS avg_order_value_usd
FROM   {{ ref('stg_order_items') }}  oi
JOIN   {{ ref('stg_orders') }}       o  ON oi.order_id   = o.order_id
JOIN   {{ ref('stg_products') }}     p  ON oi.product_id = p.product_id
GROUP  BY 1, 2
ORDER  BY 2, 1
```

- [ ] **Step 2: Create marts.yml with data tests**

Create `dbt_project/models/marts/marts.yml`:

```yaml
version: 2

models:
  - name: monthly_sales_summary
    columns:
      - name: product_name
        tests:
          - not_null
      - name: month
        tests:
          - not_null
      - name: revenue_usd
        tests:
          - not_null
      - name: order_count
        tests:
          - not_null
      - name: avg_order_value_usd
        tests:
          - not_null
```

- [ ] **Step 3: Run dbt to build the mart**

```bash
cd dbt_project && dbt run --select marts
```

Expected: `monthly_sales_summary` shows `OK`, created as a table.

- [ ] **Step 4: Run all dbt tests**

```bash
dbt test
```

Expected: all tests PASS across staging and marts.

- [ ] **Step 5: Commit**

```bash
cd ..
git add dbt_project/models/marts/
git commit -m "feat: add monthly_sales_summary mart with data quality tests"
```

---

## Task 9: End-to-End Verification

- [ ] **Step 1: Run the full pipeline from scratch**

```bash
# Start Postgres (if not running)
docker compose up -d

# Extract
python extract/extract.py

# Transform + Load
cd dbt_project && dbt run && dbt test && cd ..
```

Expected: extract prints row counts, `dbt run` builds 4 models (3 staging + 1 mart), `dbt test` passes all tests.

- [ ] **Step 2: Spot-check the mart table**

```bash
docker exec -it basket-craft-pipeline-postgres-1 psql -U pipeline -d basket_craft_dw -c "
SELECT product_name, month, revenue_usd, order_count, avg_order_value_usd
FROM marts.monthly_sales_summary
ORDER BY month DESC, revenue_usd DESC
LIMIT 10;
"
```

Expected: rows with product names, monthly dates, and non-null numeric values.

- [ ] **Step 3: Cross-check one month against the source**

Pick one product_name and one month from the output above. Verify the row count against MySQL by running in a MySQL client:

```sql
SELECT COUNT(DISTINCT o.order_id) AS order_count
FROM   order_items oi
JOIN   orders      o ON oi.order_id   = o.order_id
JOIN   products    p ON oi.product_id = p.product_id
WHERE  p.product_name = '<product_name_from_output>'
  AND  DATE_FORMAT(o.created_at, '%Y-%m') = '<YYYY-MM_from_output>';
```

Expected: count matches `order_count` in `monthly_sales_summary`.

- [ ] **Step 4: Final commit and push**

```bash
git add .
git status  # confirm no sensitive files are staged (.env, profiles.yml)
git commit -m "feat: complete ETL pipeline with dbt mart and verification"
git push origin main
```

---

## Run Order (Reference)

```bash
# One-time setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d

# Each run
python extract/extract.py
cd dbt_project && dbt run && dbt test
```
