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


def discover_tables(rds_engine):
    with rds_engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
        )
        return [row[0] for row in result]


def load_table(rds_engine, sf_conn, table_name, database, schema):
    df = pd.read_sql(f'SELECT * FROM public."{table_name}"', rds_engine)
    row_count = len(df)
    sf_table = table_name.upper()
    sf_schema = schema.upper()
    sf_database = database.upper()
    with sf_conn.cursor() as cursor:
        cursor.execute(f'TRUNCATE TABLE IF EXISTS {sf_database}.{sf_schema}.{sf_table}')
    write_pandas(
        sf_conn, df, sf_table,
        database=sf_database,
        schema=sf_schema,
        auto_create_table=True,
        quote_identifiers=False,
    )
    return row_count


def main():
    rds_engine = None
    sf_conn = None

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

    database = os.getenv("SNOWFLAKE_DATABASE").upper()
    schema = os.getenv("SNOWFLAKE_SCHEMA").upper()
    failed = []

    try:
        with sf_conn.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {database}.{schema}")

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
        if rds_engine:
            rds_engine.dispose()
        if sf_conn:
            sf_conn.close()

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
