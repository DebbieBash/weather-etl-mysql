from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import Engine, create_engine, text

from src.config import MySQLConfig, load_mysql_config

logger = logging.getLogger(__name__)

UPSERT_SQL = text(
    """
    INSERT INTO weather_daily
        (city, observation_date, temperature_2m_max, temperature_2m_min, precipitation_sum)
    VALUES
        (:city, :observation_date, :temperature_2m_max, :temperature_2m_min, :precipitation_sum)
    ON DUPLICATE KEY UPDATE
        temperature_2m_max = VALUES(temperature_2m_max),
        temperature_2m_min = VALUES(temperature_2m_min),
        precipitation_sum = VALUES(precipitation_sum)
    """
)


def get_engine(mysql_config: MySQLConfig | None = None) -> Engine:
    mysql_config = mysql_config or load_mysql_config()
    return create_engine(mysql_config.sqlalchemy_url)


def load_dataframe(df: pd.DataFrame, engine: Engine) -> int:
    """Upsert each row of df into weather_daily, keyed on (city, observation_date).

    Using INSERT ... ON DUPLICATE KEY UPDATE makes re-running the pipeline
    over an overlapping date range idempotent instead of erroring or
    duplicating rows.
    """
    if df.empty:
        logger.info("Nothing to load, dataframe is empty")
        return 0

    records = df.assign(
        observation_date=df["observation_date"].dt.strftime("%Y-%m-%d")
    ).to_dict(orient="records")

    with engine.begin() as conn:
        conn.execute(UPSERT_SQL, records)

    logger.info("Upserted %d rows into weather_daily", len(records))
    return len(records)
