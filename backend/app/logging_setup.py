"""Write JSON logs to the terminal and a rotating local file."""

import logging
from logging.handlers import TimedRotatingFileHandler

import structlog

from app.config import BACKEND_DIR


def configure_logging(level: str) -> None:
    log_directory = BACKEND_DIR / "logs"
    log_directory.mkdir(exist_ok=True)
    file_handler = TimedRotatingFileHandler(
        log_directory / "aurevon.log",
        when="midnight",
        backupCount=90,
        encoding="utf-8",
        utc=True,
    )
    logger = logging.getLogger("aurevon")
    # Recreating the app in tests must not duplicate handlers or hold files open.
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(level)
    logger.propagate = False
    for handler in (logging.StreamHandler(), file_handler):
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
