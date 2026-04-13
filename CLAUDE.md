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

## Common Commands

**Run the full pipeline:**
```bash
source .venv/bin/activate
python extract/extract.py
cd dbt_project && dbt run --profiles-dir . && dbt test --profiles-dir .
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

**Stage 1 — Extract (`extract/extract.py`)**
Connects to a remote MySQL database (`db.isba.co`) and bulk-loads three tables (`orders`, `order_items`, `products`) into the local PostgreSQL `public` schema using SQLAlchemy + pandas. Credentials are read from `.env` via `python-dotenv`. The loader drops each table with `CASCADE` before reloading so dependent dbt views are not left dangling.

**Stage 2 — Transform (`dbt_project/`)**
dbt reads from `public` (the raw tables) and builds:
- **Staging views** (`stg_orders`, `stg_order_items`, `stg_products`) — cast types, enforce `NOT NULL` on primary keys
- **Mart table** (`monthly_sales_summary`) — joins all three staging models and aggregates revenue, order count, and avg order value by product and month

All dbt models and tests land in the `public` schema. `profiles.yml` (not committed) must be present at `dbt_project/profiles.yml` — always pass `--profiles-dir .` when running dbt commands from inside `dbt_project/`.

**Not committed:** `.env`, `dbt_project/profiles.yml`

## Key Design Decisions

- `is_primary_item` is stored as `bigint` in PostgreSQL (MySQL `tinyint` migration artifact). The staging model uses `CASE WHEN is_primary_item = 1 THEN TRUE WHEN is_primary_item = 0 THEN FALSE ELSE NULL END` instead of a direct `::BOOLEAN` cast.
- Currency columns use `NUMERIC(10,2)` precision throughout staging.
- Tests marked `@pytest.mark.integration` require a live PostgreSQL connection. Unit tests mock both engines and run without Docker.
