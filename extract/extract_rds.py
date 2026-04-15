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
