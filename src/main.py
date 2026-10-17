import argparse
import logging
from datetime import date

from src import config
from src.extract import extract_all
from src.load import get_engine, load_dataframe
from src.logging_config import setup_logging
from src.transform import combine_pages, validate

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Weather ETL into MySQL")
    parser.add_argument(
        "--start-date",
        type=date.fromisoformat,
        default=config.DEFAULT_START_DATE,
        help="YYYY-MM-DD, defaults to %(default)s",
    )
    parser.add_argument(
        "--end-date",
        type=date.fromisoformat,
        default=config.DEFAULT_END_DATE,
        help="YYYY-MM-DD, defaults to %(default)s",
    )
    return parser.parse_args()


def run(start: date, end: date) -> None:
    logger.info("Starting weather ETL for %s..%s", start, end)

    pages = extract_all(config.CITIES, start, end)
    logger.info("Extracted %d pages across %d cities", len(pages), len(config.CITIES))

    raw_df = combine_pages(pages)
    clean_df, rejected_df = validate(raw_df)
    logger.info(
        "Validated %d rows (%d accepted, %d rejected)",
        len(raw_df),
        len(clean_df),
        len(rejected_df),
    )
    if not rejected_df.empty:
        logger.warning("Rejected row reasons:\n%s", rejected_df["reason"].value_counts())

    engine = get_engine()
    loaded = load_dataframe(clean_df, engine)
    logger.info("ETL complete: %d rows loaded", loaded)


if __name__ == "__main__":
    setup_logging()
    args = parse_args()
    run(args.start_date, args.end_date)
