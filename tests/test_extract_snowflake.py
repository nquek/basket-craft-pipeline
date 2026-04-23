import os
import pytest
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
