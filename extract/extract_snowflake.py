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
