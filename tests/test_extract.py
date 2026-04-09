import pytest
from unittest.mock import MagicMock, patch, call
import pandas as pd
from sqlalchemy import create_engine, text
import os

from extract.extract import create_raw_schema, load_table


PG_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://pipeline:pipeline@localhost:5432/basket_craft_dw"
)


def test_postgres_is_reachable():
    engine = create_engine(PG_URL)
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1
    finally:
        engine.dispose()


def test_create_raw_schema_creates_schema():
    """create_raw_schema should create the 'raw' schema in PostgreSQL."""
    engine = create_engine(PG_URL)
    create_raw_schema(engine)
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name = 'raw'"
        )).fetchone()
    assert result is not None, "Schema 'raw' was not created"


def test_load_table_returns_correct_row_count():
    """load_table should return the number of rows loaded."""
    mock_mysql = MagicMock()
    mock_pg = MagicMock()
    fake_df = pd.DataFrame({
        "order_id": [1, 2, 3],
        "created_at": pd.to_datetime(["2024-01-01"] * 3),
        "price_usd": [10.0, 20.0, 30.0],
    })

    with patch("extract.extract.pd.read_sql", return_value=fake_df):
        count = load_table(mock_mysql, mock_pg, "orders", ["order_id", "created_at", "price_usd"])

    assert count == 3


def test_load_table_calls_to_sql_with_correct_args():
    """load_table should write to the correct schema and table in PostgreSQL."""
    mock_mysql = MagicMock()
    mock_pg = MagicMock()
    fake_df = pd.DataFrame({"order_id": [1]})

    with patch("extract.extract.pd.read_sql", return_value=fake_df) as mock_read:
        with patch.object(fake_df.__class__, "to_sql") as mock_to_sql:
            load_table(mock_mysql, mock_pg, "orders", ["order_id"])
            mock_to_sql.assert_called_once_with(
                "orders", mock_pg, schema="raw", if_exists="replace", index=False
            )
