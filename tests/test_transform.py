import pandas as pd
import pytest

from src import transform


def make_payload(dates, temp_max, temp_min, precip):
    return {
        "daily": {
            "time": dates,
            "temperature_2m_max": temp_max,
            "temperature_2m_min": temp_min,
            "precipitation_sum": precip,
        }
    }


def test_flatten_page_produces_one_row_per_date_with_city_column():
    payload = make_payload(
        ["2023-01-01", "2023-01-02"], [5.0, 6.0], [1.0, 2.0], [0.0, 1.2]
    )
    df = transform.flatten_page("London", payload)
    assert list(df["city"]) == ["London", "London"]
    assert list(df["observation_date"]) == ["2023-01-01", "2023-01-02"]
    assert list(df["temperature_2m_max"]) == [5.0, 6.0]


def test_flatten_page_raises_on_missing_daily_block():
    with pytest.raises(transform.ValidationError):
        transform.flatten_page("London", {})


def test_combine_pages_concatenates_multiple_cities():
    pages = [
        ("London", make_payload(["2023-01-01"], [5.0], [1.0], [0.0])),
        ("Nairobi", make_payload(["2023-01-01"], [25.0], [15.0], [5.0])),
    ]
    df = transform.combine_pages(pages)
    assert len(df) == 2
    assert set(df["city"]) == {"London", "Nairobi"}


def _sample_df():
    return pd.DataFrame(
        {
            "city": ["London", "London", "London", "Nairobi"],
            "observation_date": ["2023-01-01", "2023-01-02", "2023-01-02", "2023-01-01"],
            "temperature_2m_max": [5.0, 200.0, None, 25.0],
            "temperature_2m_min": [1.0, 190.0, None, 15.0],
            "precipitation_sum": [0.0, 1.0, None, 5.0],
        }
    )


def test_validate_drops_out_of_range_values():
    clean, rejected = transform.validate(_sample_df())
    assert "value out of plausible range" in rejected["reason"].values


def test_validate_drops_missing_fields():
    clean, rejected = transform.validate(_sample_df())
    assert "missing or unparseable field" in rejected["reason"].values


def test_validate_drops_duplicate_city_date_pairs():
    df = pd.DataFrame(
        {
            "city": ["London", "London"],
            "observation_date": ["2023-01-01", "2023-01-01"],
            "temperature_2m_max": [5.0, 6.0],
            "temperature_2m_min": [1.0, 2.0],
            "precipitation_sum": [0.0, 0.5],
        }
    )
    clean, rejected = transform.validate(df)
    assert len(clean) == 1
    assert rejected.iloc[0]["reason"] == "duplicate city/date"


def test_validate_keeps_well_formed_rows():
    df = pd.DataFrame(
        {
            "city": ["London"],
            "observation_date": ["2023-01-01"],
            "temperature_2m_max": [5.0],
            "temperature_2m_min": [1.0],
            "precipitation_sum": [0.0],
        }
    )
    clean, rejected = transform.validate(df)
    assert len(clean) == 1
    assert rejected.empty


def test_validate_raises_on_missing_required_columns():
    df = pd.DataFrame({"city": ["London"]})
    with pytest.raises(transform.ValidationError):
        transform.validate(df)
