import logging
import sys
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = "."
MAX_BYTES = 10 * 1024 * 1024  # 10MB


def _get_handler(filename, level=logging.INFO):
    handler = RotatingFileHandler(
        filename,
        maxBytes=MAX_BYTES,
        backupCount=1,
        mode="a",
        encoding="utf-8",
    )
    handler.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    return handler


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        _get_handler("server.log"),
        _get_handler("server_err.log", level=logging.ERROR),
    ],
)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)