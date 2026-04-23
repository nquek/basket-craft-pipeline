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
