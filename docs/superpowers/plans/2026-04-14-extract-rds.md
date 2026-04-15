# Extract to AWS RDS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `extract/extract_rds.py` that auto-discovers all tables in the Basket Craft MySQL database and bulk-loads them raw into AWS RDS PostgreSQL.

**Architecture:** A standalone script alongside the existing `extract/extract.py`. Uses `INFORMATION_SCHEMA.TABLES` to discover tables dynamically, then `SELECT *` + `pandas.to_sql` to load each one into the `public` schema of the RDS instance. MySQL credentials reuse the existing `MYSQL_*` env vars; RDS credentials use a new `RDS_*` prefix.

**Tech Stack:** Python 3, pandas, SQLAlchemy, pymysql, psycopg2, python-dotenv

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `.env` | All connection credentials (not committed) |
| Create | `extract/extract_rds.py` | Full extract script: URL builder, table discovery, loader, main |

---

### Task 1: Populate .env with all credentials

**Files:**
- Create: `.env` (not committed — already in `.gitignore`)

> **Note:** `MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_DATABASE` are provided by your instructor. Fill them in from your course materials.

- [ ] **Step 1: Create `.env` in the project root**

```bash
cat > .env << 'EOF'
# MySQL source (remote)
MYSQL_USER=<your_mysql_user>
MYSQL_PASSWORD=<your_mysql_password>
MYSQL_HOST=db.isba.co
MYSQL_PORT=3306
MYSQL_DATABASE=<your_mysql_database>

# Local Docker PostgreSQL (used by existing extract.py)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=basket_craft

# AWS RDS PostgreSQL (used by extract_rds.py)
RDS_HOST=basket-craft-db.cxgsok2qkthe.us-east-2.rds.amazonaws.com
RDS_PORT=5432
RDS_USER=student
RDS_PASSWORD=go_lions
RDS_DB=basket_craft
EOF
```

Replace `<your_mysql_user>`, `<your_mysql_password>`, and `<your_mysql_database>` with the credentials from your course materials before continuing.

- [ ] **Step 2: Verify .env is not tracked by git**

```bash
git status .env
```

Expected: `.env` does not appear (it is in `.gitignore`). If it does appear, stop and add `.env` to `.gitignore` before proceeding.

---

### Task 2: Create extract/extract_rds.py

**Files:**
- Create: `extract/extract_rds.py`

- [ ] **Step 1: Activate the virtual environment**

```bash
source .venv/bin/activate
```

- [ ] **Step 2: Create `extract/extract_rds.py` with the full implementation**

```python
import os
import sys
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


def _build_urls():
    required = [
        "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE",
        "RDS_USER", "RDS_PASSWORD", "RDS_HOST", "RDS_PORT", "RDS_DB",
    ]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")
    mysql_url = (
        f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}"
        f"@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DATABASE')}"
    )
    rds_url = (
        f"postgresql+psycopg2://{os.getenv('RDS_USER')}:{os.getenv('RDS_PASSWORD')}"
        f"@{os.getenv('RDS_HOST')}:{os.getenv('RDS_PORT')}/{os.getenv('RDS_DB')}"
    )
    return mysql_url, rds_url


def discover_tables(mysql_engine):
    db = os.getenv("MYSQL_DATABASE")
    with mysql_engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA = :db AND TABLE_TYPE = 'BASE TABLE'"
            ),
            {"db": db},
        )
        return [row[0] for row in result]


def load_table(mysql_engine, pg_engine, table_name):
    df = pd.read_sql(f"SELECT * FROM {table_name}", mysql_engine)
    row_count = len(df)
    with pg_engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS public.{table_name} CASCADE"))
        conn.commit()
    df.to_sql(table_name, pg_engine, schema="public", if_exists="replace", index=False)
    return row_count


def main():
    mysql_url, rds_url = _build_urls()

    try:
        mysql_engine = create_engine(mysql_url)
        with mysql_engine.connect():
            pass
    except Exception as e:
        print(f"ERROR: Cannot connect to MySQL at {os.getenv('MYSQL_HOST')}: {e}")
        sys.exit(1)

    try:
        rds_engine = create_engine(rds_url)
        with rds_engine.connect():
            pass
    except Exception as e:
        print(f"ERROR: Cannot connect to RDS at {os.getenv('RDS_HOST')}: {e}")
        sys.exit(1)

    try:
        tables = discover_tables(mysql_engine)
        print(f"Discovered {len(tables)} tables: {', '.join(tables)}")

        for table_name in tables:
            print(f"Loading {table_name}...", end=" ", flush=True)
            count = load_table(mysql_engine, rds_engine, table_name)
            print(f"{count} rows loaded into public.{table_name}")

        print("Extract complete.")
    finally:
        mysql_engine.dispose()
        rds_engine.dispose()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Commit the new script**

```bash
git add extract/extract_rds.py
git commit -m "feat: add extract_rds.py with auto-discovery for AWS RDS load"
```

---

### Task 3: Run the extract and verify

**Files:**
- Run: `extract/extract_rds.py`

- [ ] **Step 1: Run the script**

```bash
source .venv/bin/activate
python extract/extract_rds.py
```

Expected output (table names and row counts will vary):
```
Discovered N tables: orders, order_items, products, ...
Loading orders... 12345 rows loaded into public.orders
Loading order_items... 45678 rows loaded into public.order_items
Loading products... 12 rows loaded into public.products
...
Extract complete.
```

If you see `ERROR: Cannot connect to MySQL` — double-check `MYSQL_*` values in `.env`.
If you see `ERROR: Cannot connect to RDS` — verify the RDS instance is `available` in the AWS Console and that port 5432 is open in the `basket-craft-sg` security group.

- [ ] **Step 2: Spot-check a table in RDS**

Connect to RDS using psql (or DBeaver) and verify a table exists with data:

```bash
psql "host=basket-craft-db.cxgsok2qkthe.us-east-2.rds.amazonaws.com port=5432 dbname=basket_craft user=student password=go_lions sslmode=require" \
  -c "\dt public.*" \
  -c "SELECT COUNT(*) FROM public.orders;"
```

Expected: `\dt` lists all discovered tables; `COUNT(*)` returns a non-zero row count matching the script output.
