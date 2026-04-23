# RDS → Snowflake Extract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `extract/extract_snowflake.py` — a script that reads all tables from AWS RDS PostgreSQL and bulk-loads them into a Snowflake raw schema using `snowflake-connector-python`.

**Architecture:** Auto-discovers all tables in the RDS `public` schema via `information_schema.tables`, reads each into a pandas DataFrame using SQLAlchemy, then truncates and reloads each Snowflake target table using `write_pandas()`. Per-table errors are caught and collected; a summary is printed at the end. The script exits 1 if any table failed, 0 if all succeeded.

**Tech Stack:** `snowflake-connector-python[pandas]` (write_pandas), SQLAlchemy + psycopg2 (RDS read), pandas, python-dotenv

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `extract/extract_snowflake.py` | All extract logic: env validation, connections, discovery, load, main |
| Create | `tests/test_extract_snowflake.py` | Unit tests (no live credentials) |
| Modify | `requirements.txt` | Add `snowflake-connector-python[pandas]` |

---

## Task 1: Add Snowflake dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add the dependency**

Open `requirements.txt` and append:
```
snowflake-connector-python[pandas]
```

The full file should now be:
```
sqlalchemy==2.0.36
pymysql==1.1.1
psycopg2-binary==2.9.10
python-dotenv==1.0.1
pandas==2.2.3
dbt-postgres==1.9.0
pytest==8.3.4
snowflake-connector-python[pandas]
```

- [ ] **Step 2: Install it**

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: pip installs `snowflake-connector-python` and its extras without errors.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add snowflake-connector-python[pandas] dependency"
```

---

## Task 2: Env validation — test then implement

**Files:**
- Create: `tests/test_extract_snowflake.py`
- Create: `extract/extract_snowflake.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_extract_snowflake.py`:

```python
import os
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd


def test_validate_env_missing_vars():
    """_validate_env raises EnvironmentError listing all missing vars."""
    with patch.dict(os.environ, {}, clear=True):
        from extract.extract_snowflake import _validate_env
        with pytest.raises(EnvironmentError) as exc_info:
            _validate_env()
        assert "RDS_USER" in str(exc_info.value)
        assert "SNOWFLAKE_ACCOUNT" in str(exc_info.value)
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
source .venv/bin/activate
pytest tests/test_extract_snowflake.py::test_validate_env_missing_vars -v
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'extract.extract_snowflake'`

- [ ] **Step 3: Create the implementation file**

Create `extract/extract_snowflake.py`:

```python
import os
import sys
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

load_dotenv()

REQUIRED_ENV_VARS = [
    "RDS_USER", "RDS_PASSWORD", "RDS_HOST", "RDS_PORT", "RDS_DB",
    "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE", "SNOWFLAKE_SCHEMA",
]


def _validate_env():
    missing = [k for k in REQUIRED_ENV_VARS if not os.getenv(k)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}"
        )


def _connect_rds():
    rds_url = (
        f"postgresql+psycopg2://{os.getenv('RDS_USER')}:{os.getenv('RDS_PASSWORD')}"
        f"@{os.getenv('RDS_HOST')}:{os.getenv('RDS_PORT')}/{os.getenv('RDS_DB')}"
    )
    engine = create_engine(rds_url)
    with engine.connect():
        pass
    return engine


def _connect_snowflake():
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
    )
```

- [ ] **Step 4: Run the test to confirm it passes**

```bash
pytest tests/test_extract_snowflake.py::test_validate_env_missing_vars -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add extract/extract_snowflake.py tests/test_extract_snowflake.py
git commit -m "feat: add env validation and connection helpers for Snowflake extract"
```

---

## Task 3: Table discovery — test then implement

**Files:**
- Modify: `extract/extract_snowflake.py`
- Modify: `tests/test_extract_snowflake.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_extract_snowflake.py`:

```python
def test_discover_tables_returns_table_names():
    """discover_tables queries information_schema and returns a list of table name strings."""
    from extract.extract_snowflake import discover_tables

    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn.execute.return_value = [("orders",), ("products",)]

    tables = discover_tables(mock_engine)

    assert tables == ["orders", "products"]
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
pytest tests/test_extract_snowflake.py::test_discover_tables_returns_table_names -v
```

Expected: `FAILED` — `ImportError: cannot import name 'discover_tables'`

- [ ] **Step 3: Add the implementation**

Append to `extract/extract_snowflake.py`:

```python
def discover_tables(rds_engine):
    with rds_engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
        )
        return [row[0] for row in result]
```

- [ ] **Step 4: Run the test to confirm it passes**

```bash
pytest tests/test_extract_snowflake.py::test_discover_tables_returns_table_names -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add extract/extract_snowflake.py tests/test_extract_snowflake.py
git commit -m "feat: add discover_tables for Snowflake extract"
```

---

## Task 4: Per-table load — test then implement

**Files:**
- Modify: `extract/extract_snowflake.py`
- Modify: `tests/test_extract_snowflake.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_extract_snowflake.py`:

```python
def test_load_table_returns_row_count_and_calls_truncate():
    """load_table truncates the Snowflake table, writes via write_pandas, returns row count."""
    from extract.extract_snowflake import load_table

    mock_rds_engine = MagicMock()
    mock_sf_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_sf_conn.cursor.return_value = mock_cursor

    fake_df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})

    with patch("extract.extract_snowflake.pd.read_sql", return_value=fake_df), \
         patch("extract.extract_snowflake.write_pandas") as mock_write:
        count = load_table(mock_rds_engine, mock_sf_conn, "orders", "MYDB", "RAW")

    assert count == 3
    mock_cursor.execute.assert_called_once_with(
        'TRUNCATE TABLE IF EXISTS "RAW"."ORDERS"'
    )
    mock_write.assert_called_once_with(
        mock_sf_conn, fake_df, "ORDERS",
        database="MYDB",
        schema="RAW",
        auto_create_table=True,
        quote_identifiers=False,
    )
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
pytest tests/test_extract_snowflake.py::test_load_table_returns_row_count_and_calls_truncate -v
```

Expected: `FAILED` — `ImportError: cannot import name 'load_table'`

- [ ] **Step 3: Add the implementation**

Append to `extract/extract_snowflake.py`:

```python
def load_table(rds_engine, sf_conn, table_name, database, schema):
    df = pd.read_sql(f'SELECT * FROM public."{table_name}"', rds_engine)
    row_count = len(df)
    sf_table = table_name.upper()
    cursor = sf_conn.cursor()
    cursor.execute(f'TRUNCATE TABLE IF EXISTS "{schema}"."{sf_table}"')
    write_pandas(
        sf_conn, df, sf_table,
        database=database,
        schema=schema,
        auto_create_table=True,
        quote_identifiers=False,
    )
    return row_count
```

- [ ] **Step 4: Run the test to confirm it passes**

```bash
pytest tests/test_extract_snowflake.py::test_load_table_returns_row_count_and_calls_truncate -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add extract/extract_snowflake.py tests/test_extract_snowflake.py
git commit -m "feat: add load_table with truncate-and-reload for Snowflake extract"
```

---

## Task 5: main() with error handling and summary — test then implement

**Files:**
- Modify: `extract/extract_snowflake.py`
- Modify: `tests/test_extract_snowflake.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_extract_snowflake.py`:

```python
_FULL_ENV = {
    "RDS_USER": "u", "RDS_PASSWORD": "p", "RDS_HOST": "h",
    "RDS_PORT": "5432", "RDS_DB": "db",
    "SNOWFLAKE_ACCOUNT": "acc", "SNOWFLAKE_USER": "su",
    "SNOWFLAKE_PASSWORD": "sp", "SNOWFLAKE_WAREHOUSE": "wh",
    "SNOWFLAKE_DATABASE": "DB", "SNOWFLAKE_SCHEMA": "RAW",
}


def test_load_table_failure_continues(capsys):
    """main() records a failing table and continues loading the next one."""
    from extract.extract_snowflake import main

    with patch.dict(os.environ, _FULL_ENV), \
         patch("extract.extract_snowflake._connect_rds"), \
         patch("extract.extract_snowflake._connect_snowflake"), \
         patch("extract.extract_snowflake.discover_tables", return_value=["orders", "products"]), \
         patch("extract.extract_snowflake.load_table") as mock_load, \
         pytest.raises(SystemExit) as exc_info:
        mock_load.side_effect = [Exception("type mismatch"), 5]
        main()

    captured = capsys.readouterr()
    assert "orders" in captured.out
    assert "products" in captured.out
    assert "type mismatch" in captured.out
    assert exc_info.value.code == 1


def test_summary_all_success(capsys):
    """main() prints a 2/2 success summary and exits 0 when all tables load."""
    from extract.extract_snowflake import main

    with patch.dict(os.environ, _FULL_ENV), \
         patch("extract.extract_snowflake._connect_rds"), \
         patch("extract.extract_snowflake._connect_snowflake"), \
         patch("extract.extract_snowflake.discover_tables", return_value=["orders", "products"]), \
         patch("extract.extract_snowflake.load_table", return_value=10):
        main()

    captured = capsys.readouterr()
    assert "2/2 tables loaded successfully" in captured.out
```

- [ ] **Step 2: Run them to confirm they fail**

```bash
pytest tests/test_extract_snowflake.py::test_load_table_failure_continues tests/test_extract_snowflake.py::test_summary_all_success -v
```

Expected: both `FAILED` — `ImportError: cannot import name 'main'`

- [ ] **Step 3: Add the implementation**

Append to `extract/extract_snowflake.py`:

```python
def main():
    try:
        _validate_env()
    except EnvironmentError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    try:
        rds_engine = _connect_rds()
    except Exception as e:
        print(f"ERROR: Cannot connect to RDS at {os.getenv('RDS_HOST')}: {e}")
        sys.exit(1)

    try:
        sf_conn = _connect_snowflake()
    except Exception as e:
        print(f"ERROR: Cannot connect to Snowflake account {os.getenv('SNOWFLAKE_ACCOUNT')}: {e}")
        rds_engine.dispose()
        sys.exit(1)

    database = os.getenv("SNOWFLAKE_DATABASE")
    schema = os.getenv("SNOWFLAKE_SCHEMA")
    failed = []

    try:
        tables = discover_tables(rds_engine)
        print(f"Discovered {len(tables)} tables: {', '.join(tables)}")

        for table_name in tables:
            print(f"Loading {table_name}...", end=" ", flush=True)
            try:
                count = load_table(rds_engine, sf_conn, table_name, database, schema)
                print(f"{count} rows loaded into {schema}.{table_name.upper()}")
            except Exception as e:
                print(f"FAILED — {e}")
                failed.append((table_name, str(e)))

        total = len(tables)
        succeeded = total - len(failed)
        print(f"\nExtract complete. {succeeded}/{total} tables loaded successfully.")
        if failed:
            for name, err in failed:
                print(f"  Failed: {name} — {err}")
    finally:
        rds_engine.dispose()
        sf_conn.close()

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all tests to confirm they pass**

```bash
pytest tests/test_extract_snowflake.py -v
```

Expected: all 5 tests `PASSED`

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
pytest tests/ -v -m "not integration"
```

Expected: all unit tests `PASSED`

- [ ] **Step 6: Commit**

```bash
git add extract/extract_snowflake.py tests/test_extract_snowflake.py
git commit -m "feat: add main() with per-table error handling and summary for Snowflake extract"
```

---

## Post-Implementation: Add Snowflake env vars to .env

Add the following to your `.env` file (not committed — already in `.gitignore`):

```
SNOWFLAKE_ACCOUNT=<your-account-identifier>
SNOWFLAKE_USER=<your-username>
SNOWFLAKE_PASSWORD=<your-password>
SNOWFLAKE_WAREHOUSE=<your-warehouse>
SNOWFLAKE_DATABASE=<your-database>
SNOWFLAKE_SCHEMA=<your-raw-schema>
```

The account identifier format Snowflake expects is `orgname-accountname` (found in Snowflake UI under Admin → Accounts).

To run the completed script:

```bash
source .venv/bin/activate
python extract/extract_snowflake.py
```
