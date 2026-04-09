import os
import sys
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

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


def _build_urls():
    required = [
        "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE",
        "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB",
    ]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")
    mysql_url = (
        f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}"
        f"@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DATABASE')}"
    )
    pg_url = (
        f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
        f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )
    return mysql_url, pg_url


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
    mysql_url, pg_url = _build_urls()

    try:
        mysql_engine = create_engine(mysql_url)
        with mysql_engine.connect():
            pass
    except Exception as e:
        print(f"ERROR: Cannot connect to MySQL at {os.getenv('MYSQL_HOST')}: {e}")
        sys.exit(1)

    try:
        pg_engine = create_engine(pg_url)
        with pg_engine.connect():
            pass
    except Exception as e:
        print(f"ERROR: Cannot connect to PostgreSQL at {os.getenv('POSTGRES_HOST')}: {e}")
        sys.exit(1)

    try:
        print("Creating raw schema...")
        create_raw_schema(pg_engine)

        for table_name, columns in TABLES.items():
            print(f"Loading {table_name}...", end=" ", flush=True)
            count = load_table(mysql_engine, pg_engine, table_name, columns)
            print(f"{count} rows loaded into raw.{table_name}")

        print("Extract complete.")
    finally:
        mysql_engine.dispose()
        pg_engine.dispose()


if __name__ == "__main__":
    main()
