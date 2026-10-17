import logging

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "city",
    "observation_date",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
]

# Sanity bounds for validation, not strict physical limits.
MIN_TEMP_C = -90.0
MAX_TEMP_C = 60.0


class ValidationError(Exception):
    """Raised when the data is malformed beyond what cleaning can fix."""


def flatten_page(city: str, payload: dict) -> pd.DataFrame:
    """Flatten one Open-Meteo 'daily' JSON page into a tidy DataFrame.

    The API nests same-length arrays under payload["daily"], keyed by
    variable name (e.g. "time", "temperature_2m_max"). pandas builds a
    row per date directly from that dict.
    """
    daily = payload.get("daily")
    if not daily or "time" not in daily:
        raise ValidationError(f"Missing 'daily.time' in payload for {city}")

    df = pd.DataFrame(daily)
    df = df.rename(columns={"time": "observation_date"})
    df.insert(0, "city", city)
    return df


def combine_pages(pages: list[tuple[str, dict]]) -> pd.DataFrame:
    """Flatten and concatenate every (city, raw_json_page) pair into one DataFrame."""
    frames = [flatten_page(city, payload) for city, payload in pages]
    if not frames:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate and clean the flattened weather data.

    Checks, in order:
      1. required columns are present
      2. observation_date parses as a date; numeric columns parse as numbers
      3. values fall in a physically plausible range
      4. duplicate (city, observation_date) rows are dropped, keeping the first

    Returns (clean_df, rejected_df). Rows failing checks 2-3 are moved to
    rejected_df along with a 'reason' column rather than silently dropped.
    """
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValidationError(f"Missing required columns: {sorted(missing)}")

    df = df.copy()
    df["observation_date"] = pd.to_datetime(df["observation_date"], errors="coerce")
    numeric_cols = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    reasons = pd.Series([""] * len(df), index=df.index)

    null_mask = df[REQUIRED_COLUMNS].isna().any(axis=1)
    reasons[null_mask] = "missing or unparseable field"

    range_mask = (
        (df["temperature_2m_max"] < MIN_TEMP_C)
        | (df["temperature_2m_max"] > MAX_TEMP_C)
        | (df["temperature_2m_min"] < MIN_TEMP_C)
        | (df["temperature_2m_min"] > MAX_TEMP_C)
        | (df["precipitation_sum"] < 0)
    )
    reasons[range_mask & ~null_mask] = "value out of plausible range"

    order_mask = df["temperature_2m_max"] < df["temperature_2m_min"]
    reasons[order_mask & ~null_mask & ~range_mask] = "temperature_2m_max < temperature_2m_min"

    invalid_mask = reasons != ""
    rejected = df[invalid_mask].assign(reason=reasons[invalid_mask])
    clean = df[~invalid_mask].copy()

    dup_mask = clean.duplicated(subset=["city", "observation_date"], keep="first")
    if dup_mask.any():
        duplicates = clean[dup_mask].assign(reason="duplicate city/date")
        rejected = pd.concat([rejected, duplicates], ignore_index=True)
        clean = clean[~dup_mask]

    if not rejected.empty:
        logger.warning("Rejected %d rows during validation", len(rejected))

    return clean.reset_index(drop=True), rejected.reset_index(drop=True)
