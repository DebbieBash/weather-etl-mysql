import os
from dataclasses import dataclass
from datetime import date

from dotenv import load_dotenv

load_dotenv()

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# A handful of cities with varied climates, to give the validation/range
# checks something to actually catch.
CITIES = [
    {"name": "London", "latitude": 51.5072, "longitude": -0.1276},
    {"name": "Reykjavik", "latitude": 64.1466, "longitude": -21.9426},
    {"name": "Nairobi", "latitude": -1.2921, "longitude": 36.8219},
    {"name": "Singapore", "latitude": 1.3521, "longitude": 103.8198},
]

DAILY_VARIABLES = "temperature_2m_max,temperature_2m_min,precipitation_sum"

DEFAULT_START_DATE = date(2023, 1, 1)
DEFAULT_END_DATE = date(2023, 12, 31)

# Open-Meteo has no cursor/offset pagination, so a long date range is
# paginated manually by splitting it into fixed-size chunks and fetching
# one "page" (one HTTP request) per chunk.
PAGE_SIZE_DAYS = 90

REQUEST_TIMEOUT_SECONDS = 10
MAX_RETRIES = 3
BACKOFF_FACTOR = 0.5
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)


@dataclass(frozen=True)
class MySQLConfig:
    host: str
    port: int
    user: str
    password: str
    database: str

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"mysql+pymysql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


def load_mysql_config() -> MySQLConfig:
    return MySQLConfig(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "weather"),
        password=os.environ.get("MYSQL_PASSWORD", "weather_pw"),
        database=os.environ.get("MYSQL_DATABASE", "weather"),
    )
