import os
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from extract.extract_snowflake import _validate_env


def test_validate_env_missing_vars():
    """_validate_env raises EnvironmentError listing all missing vars."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(EnvironmentError) as exc_info:
            _validate_env()
        assert "RDS_USER" in str(exc_info.value)
        assert "SNOWFLAKE_ACCOUNT" in str(exc_info.value)


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
