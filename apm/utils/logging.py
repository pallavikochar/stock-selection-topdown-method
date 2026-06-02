"""Structured per-agent logging setup."""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    fmt = "%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    # Silence noisy third-party loggers
    for noisy in ("yfinance", "urllib3", "requests", "peewee"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
