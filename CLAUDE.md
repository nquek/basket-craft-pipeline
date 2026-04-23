# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

Always use the Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

PostgreSQL runs in Docker — start it before running the extract or any integration tests:

```bash
docker compose up -d
```

On Apple Silicon with Python 3.14, `psycopg2-binary` may need Homebrew's libpq path at install time:
```bash
LDFLAGS="-L/opt/homebrew/opt/libpq/lib" CPPFLAGS="-I/opt/homebrew/opt/libpq/include" pip install psycopg2-binary --force-reinstall --no-cache-dir
```

## Common Commands

**Run the local pipeline (Docker PostgreSQL):**
```bash
source .venv/bin/activate
python extract/extract.py
cd dbt_project && dbt run --profiles-dir . && dbt test --profiles-dir .
```

**Load all MySQL tables into AWS RDS:**
```bash
source .venv/bin/activate
python extract/extract_rds.py
```

**Load all RDS tables into Snowflake:**
```bash
source .venv/bin/activate
python extract/extract_snowflake.py
```

**Run all tests:**
```bash
pytest tests/ -v
```

**Run unit tests only** (no live database required):
```bash
pytest tests/ -v -m "not integration"
```

**Run a single test:**
```bash
pytest tests/test_extract.py::test_load_table_returns_correct_row_count -v
```

**Run dbt models and tests individually:**
```bash
cd dbt_project
dbt run --select staging --profiles-dir .
dbt run --select marts --profiles-dir .
dbt test --profiles-dir .
```

## Architecture

This is a two-stage ETL pipeline:

**Stage 1 — Extract**

Two standalone scripts share the same MySQL source (`db.isba.co`) but write to different PostgreSQL targets:

- **`extract/extract.py`** — loads three hardcoded tables (`orders`, `order_items`, `products`) with explicit column lists into local Docker PostgreSQL (`POSTGRES_*` env vars). Used as the source for dbt.
- **`extract/extract_rds.py`** — auto-discovers all tables in MySQL via `INFORMATION_SCHEMA.TABLES` and bulk-loads them raw (`SELECT *`) into AWS RDS PostgreSQL (`RDS_*` env vars). Currently discovers 8 tables: `employees`, `order_item_refunds`, `order_items`, `orders`, `products`, `users`, `website_pageviews`, `website_sessions`. Not connected to dbt.
- **`extract/extract_snowflake.py`** — reads all tables from the RDS `public` schema via `information_schema.tables` and bulk-loads them into Snowflake (`SNOWFLAKE_*` env vars) using `snowflake-connector-python` and `write_pandas()`. Targets the database and schema specified by `SNOWFLAKE_DATABASE` and `SNOWFLAKE_SCHEMA` (both stored uppercase). Creates the target schema if it does not exist. Per-table failures are caught and reported; the script exits 1 if any table failed. Not connected to dbt.

All three extract scripts use SQLAlchemy + pandas for reads, truncate-and-reload each target table, and read credentials from `.env` via `python-dotenv`.

**Stage 2 — Transform (`dbt_project/`)**
dbt reads from `public` (the raw tables) and builds:
- **Staging views** (`stg_orders`, `stg_order_items`, `stg_products`) — cast types, enforce `NOT NULL` on primary keys
- **Mart table** (`monthly_sales_summary`) — joins all three staging models and aggregates revenue, order count, and avg order value by product and month

All dbt models and tests land in the `public` schema. `profiles.yml` (not committed) must be present at `dbt_project/profiles.yml` — always pass `--profiles-dir .` when running dbt commands from inside `dbt_project/`.

**Not committed:** `.env`, `dbt_project/profiles.yml`

`.env` must contain:
- `MYSQL_*` — source credentials (shared by `extract.py` and `extract_rds.py`)
- `POSTGRES_*` — local Docker PostgreSQL (used by `extract.py` and dbt)
- `RDS_*` — AWS RDS PostgreSQL (used by `extract_rds.py` and as the source for `extract_snowflake.py`)
- `SNOWFLAKE_*` — Snowflake target (used by `extract_snowflake.py`):
  - `SNOWFLAKE_ACCOUNT` — account identifier in `orgname-accountname` format (Admin → Accounts in Snowflake UI)
  - `SNOWFLAKE_USER`
  - `SNOWFLAKE_PASSWORD`
  - `SNOWFLAKE_WAREHOUSE`
  - `SNOWFLAKE_DATABASE` — target database; stored uppercase at runtime
  - `SNOWFLAKE_SCHEMA` — target schema (e.g. `raw`); stored uppercase at runtime as `RAW`

## Key Design Decisions

- `is_primary_item` is stored as `bigint` in PostgreSQL (MySQL `tinyint` migration artifact). The staging model uses `CASE WHEN is_primary_item = 1 THEN TRUE WHEN is_primary_item = 0 THEN FALSE ELSE NULL END` instead of a direct `::BOOLEAN` cast.
- Currency columns use `NUMERIC(10,2)` precision throughout staging.
- Tests marked `@pytest.mark.integration` require a live PostgreSQL connection. Unit tests mock all engines and connections and run without Docker or Snowflake credentials.
- `extract_snowflake.py` uppercases all Snowflake identifiers (database, schema, table, columns) before use. Values in `.env` may be any case — they are normalised at runtime.
