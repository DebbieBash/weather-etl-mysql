from datetime import date

import pytest
import requests

from src import extract


def test_iter_date_pages_splits_range_into_fixed_size_chunks():
    pages = list(
        extract.iter_date_pages(date(2023, 1, 1), date(2023, 1, 10), page_size_days=3)
    )
    assert pages == [
        (date(2023, 1, 1), date(2023, 1, 3)),
        (date(2023, 1, 4), date(2023, 1, 6)),
        (date(2023, 1, 7), date(2023, 1, 9)),
        (date(2023, 1, 10), date(2023, 1, 10)),
    ]


def test_iter_date_pages_rejects_inverted_range():
    with pytest.raises(ValueError):
        list(extract.iter_date_pages(date(2023, 1, 10), date(2023, 1, 1), page_size_days=3))


def test_build_session_mounts_retry_adapter_with_configured_policy():
    session = extract.build_session()
    adapter = session.get_adapter("https://archive-api.open-meteo.com")
    retry = adapter.max_retries
    assert retry.total == extract.config.MAX_RETRIES
    assert set(retry.status_forcelist) == set(extract.config.RETRY_STATUS_CODES)


def test_fetch_page_returns_json_on_success(requests_mock):
    requests_mock.get(
        extract.config.ARCHIVE_URL,
        json={"daily": {"time": ["2023-01-01"], "temperature_2m_max": [5.0]}},
    )
    session = extract.build_session()
    result = extract.fetch_page(session, 51.5, -0.1, date(2023, 1, 1), date(2023, 1, 1))
    assert result["daily"]["time"] == ["2023-01-01"]


def test_fetch_page_raises_extract_error_on_connection_failure(requests_mock):
    requests_mock.get(
        extract.config.ARCHIVE_URL, exc=requests.exceptions.ConnectTimeout
    )
    session = extract.build_session()
    with pytest.raises(extract.ExtractError):
        extract.fetch_page(session, 51.5, -0.1, date(2023, 1, 1), date(2023, 1, 1))


def test_fetch_city_history_yields_one_page_per_date_chunk(requests_mock):
    requests_mock.get(
        extract.config.ARCHIVE_URL,
        json={"daily": {"time": [], "temperature_2m_max": []}},
    )
    session = extract.build_session()
    city = {"name": "London", "latitude": 51.5, "longitude": -0.1}
    pages = list(
        extract.fetch_city_history(
            session, city, date(2023, 1, 1), date(2023, 1, 7), page_size_days=3
        )
    )
    assert len(pages) == 3
