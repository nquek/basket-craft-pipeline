import pytest
from sqlalchemy import create_engine, text


PG_URL = "postgresql+psycopg2://pipeline:pipeline@localhost:5432/basket_craft_dw"


def test_postgres_is_reachable():
    engine = create_engine(PG_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
    assert result == 1
