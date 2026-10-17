import logging
from datetime import date, timedelta
from typing import Iterator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src import config

logger = logging.getLogger(__name__)


class ExtractError(Exception):
    """Raised when a page of data cannot be fetched after retries."""


def build_session() -> requests.Session:
    """A requests Session with a retry-with-backoff adapter mounted.

    Retries on connection errors and on the given status codes, with
    exponential backoff between attempts.
    """
    session = requests.Session()
    retry = Retry(
        total=config.MAX_RETRIES,
        backoff_factor=config.BACKOFF_FACTOR,
        status_forcelist=config.RETRY_STATUS_CODES,
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def iter_date_pages(
    start: date, end: date, page_size_days: int
) -> Iterator[tuple[date, date]]:
    """Split [start, end] into consecutive (page_start, page_end) chunks.

    Open-Meteo's archive endpoint has no cursor/offset pagination of its
    own, so a long date range is paginated manually here: each chunk is
    fetched as a separate page via `fetch_page`.
    """
    if start > end:
        raise ValueError("start date must not be after end date")

    page_start = start
    while page_start <= end:
        page_end = min(page_start + timedelta(days=page_size_days - 1), end)
        yield page_start, page_end
        page_start = page_end + timedelta(days=1)


def fetch_page(
    session: requests.Session,
    latitude: float,
    longitude: float,
    start: date,
    end: date,
    timeout: int = config.REQUEST_TIMEOUT_SECONDS,
) -> dict:
    """Fetch one page (one date-range chunk) of daily weather for a location."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": config.DAILY_VARIABLES,
        "timezone": "UTC",
    }
    try:
        response = session.get(
            config.ARCHIVE_URL, params=params, timeout=timeout
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ExtractError(
            f"Failed to fetch {start}..{end} at ({latitude}, {longitude}): {exc}"
        ) from exc
    return response.json()


def fetch_city_history(
    session: requests.Session,
    city: dict,
    start: date,
    end: date,
    page_size_days: int = config.PAGE_SIZE_DAYS,
) -> Iterator[dict]:
    """Yield one raw JSON page per date-range chunk for a single city."""
    for page_start, page_end in iter_date_pages(start, end, page_size_days):
        logger.info(
            "Fetching %s page %s..%s", city["name"], page_start, page_end
        )
        payload = fetch_page(
            session,
            latitude=city["latitude"],
            longitude=city["longitude"],
            start=page_start,
            end=page_end,
        )
        yield payload


def extract_all(
    cities: list[dict] = config.CITIES,
    start: date = config.DEFAULT_START_DATE,
    end: date = config.DEFAULT_END_DATE,
) -> list[tuple[str, dict]]:
    """Fetch all pages for all cities, returning (city_name, raw_json) pairs."""
    session = build_session()
    results = []
    for city in cities:
        for payload in fetch_city_history(session, city, start, end):
            results.append((city["name"], payload))
    return results
