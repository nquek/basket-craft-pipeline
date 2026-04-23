# Design: RDS PostgreSQL → Snowflake Extract

**Date:** 2026-04-22
**Status:** Approved

## Overview

A new extract script reads all raw tables from AWS RDS PostgreSQL and bulk-loads them into a Snowflake raw schema using Snowflake's official Python connector (`snowflake-connector-python`). It is a peer of the two existing extract scripts and follows their same structural pattern.

## Architecture

### File location

`extract/extract_snowflake.py`

### Data flow

```
AWS RDS PostgreSQL (public schema)
        │  SQLAlchemy + pandas  (read)
        ▼
   pandas DataFrame  (in memory)
        │  snowflake.connector write_pandas()  (write)
        ▼
Snowflake  (<SNOWFLAKE_DATABASE>.<SNOWFLAKE_SCHEMA>)
```

No intermediate files or external staging required — `write_pandas()` manages an internal Snowflake stage transparently (uploads compressed Parquet, then issues `COPY INTO`).

### Dependencies

Add to `requirements.txt`:
```
snowflake-connector-python[pandas]
```

The `[pandas]` extra is required for `write_pandas` support.

## Environment Variables

All variables are validated at startup. The script exits with a clear error message listing any missing vars.

**Existing (RDS source):**
```
RDS_USER
RDS_PASSWORD
RDS_HOST
RDS_PORT
RDS_DB
```

**New (Snowflake target):**
```
SNOWFLAKE_ACCOUNT=
SNOWFLAKE_USER=
SNOWFLAKE_PASSWORD=
SNOWFLAKE_WAREHOUSE=
SNOWFLAKE_DATABASE=
SNOWFLAKE_SCHEMA=
```

## Table Discovery

Query RDS `information_schema.tables` for all `BASE TABLE` rows in the `public` schema — the same query used in `extract_rds.py`. No hardcoded table list; picks up whatever tables are present at runtime.

## Per-Table Load Sequence

For each discovered table:

1. `pd.read_sql("SELECT * FROM public.<table>", rds_engine)` — read full table into DataFrame
2. `cursor.execute("TRUNCATE TABLE IF EXISTS <schema>.<table>")` — clear existing rows; no-op on first run if table does not yet exist
3. `write_pandas(sf_conn, df, table_name, schema=..., database=..., auto_create_table=True, quote_identifiers=False)` — create table if missing, then bulk-load

## Error Handling

- **Startup:** Missing env vars → `EnvironmentError`, `sys.exit(1)`. Connection failures → print error, `sys.exit(1)`.
- **Per-table:** Each load is wrapped in `try/except`. On failure the error is printed immediately and the table name + message is recorded. The loop continues to the next table.
- **End-of-run summary** (always printed):
  ```
  Extract complete. 7/8 tables loaded successfully.
  Failed: order_item_refunds — <error message>
  ```
- **Exit code:** `sys.exit(1)` if any table failed, `sys.exit(0)` if all succeeded.

## Testing

File: `tests/test_extract_snowflake.py`

All unit tests mock RDS and Snowflake connections — no live credentials required. Integration tests (requiring live credentials) are marked `@pytest.mark.integration` and skipped by default.

| Test | What it verifies |
|------|-----------------|
| `test_validate_env_missing_vars` | `_build_connections()` raises `EnvironmentError` when a required env var is absent |
| `test_load_table_success` | Mocked RDS read + `write_pandas` returns correct row count; TRUNCATE was called |
| `test_load_table_failure_continues` | Per-table exception is caught, recorded in `failed`, loop continues |
| `test_summary_output` | Final summary reflects correct success/failure counts |

## What This Script Does NOT Do

- No dbt integration — this feeds a Snowflake raw schema, not the dbt project
- No column filtering — loads `SELECT *` like `extract_rds.py`
- No incremental loads — full truncate-and-reload on every run
