# Extract to AWS RDS — Design Spec

**Date:** 2026-04-14
**Status:** Approved

## Overview

A new standalone script `extract/extract_rds.py` that auto-discovers all tables in the Basket Craft MySQL database and bulk-loads them raw (no transformations, `SELECT *`) into the AWS RDS PostgreSQL instance (`basket-craft-db` in `us-east-2`). Runs independently of the existing `extract/extract.py`, which continues to target local Docker PostgreSQL.

## Architecture

Single file, three functions mirroring the structure of `extract.py`:

| Function | Responsibility |
|---|---|
| `_build_urls()` | Reads `MYSQL_*` and `RDS_*` env vars from `.env`, validates all are present, returns SQLAlchemy connection URLs |
| `discover_tables(mysql_engine)` | Queries `INFORMATION_SCHEMA.TABLES` filtered by `TABLE_SCHEMA` to get all table names dynamically |
| `load_table(mysql_engine, pg_engine, table_name)` | `SELECT *` from MySQL into a pandas DataFrame, drops the target table in `public` schema with `CASCADE`, writes with `to_sql` |
| `main()` | Connects both engines, runs discovery, loops tables, disposes engines in `finally` |

## Data Flow

```
MySQL (db.isba.co)
  └─ INFORMATION_SCHEMA.TABLES → discover all table names
  └─ SELECT * FROM <table>     → pandas DataFrame (one per table)
        ↓
extract_rds.py
        ↓
AWS RDS PostgreSQL (basket-craft-db.*.us-east-2.rds.amazonaws.com)
  └─ DROP TABLE IF EXISTS public.<table> CASCADE
  └─ df.to_sql → public.<table>  (replace, no index column)
```

## Environment Variables

The following must be added to `.env` alongside the existing `MYSQL_*` and `POSTGRES_*` vars:

```
RDS_HOST=<endpoint from AWS console after provisioning>
RDS_PORT=5432
RDS_USER=student
RDS_PASSWORD=go_lions
RDS_DB=basket_craft
```

## Error Handling

- Validate all required env vars at startup before any connection is attempted
- Test both MySQL and RDS connections before touching any data; print a clear error and exit on failure
- Print per-table progress (`Loading <table>... N rows loaded`)
- Always call `engine.dispose()` in a `finally` block

## What Is Not Included

- **No tests** — this is a thin ETL runner with no business logic; mocking would duplicate scaffolding from the existing test suite without adding confidence
- **No column filtering** — all columns loaded as-is from MySQL
- **No dbt integration** — this script only handles the extract step; dbt is not invoked
- **No schema changes** — tables land in `public` schema exactly as they come from MySQL
