import logging
import sys


def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler(sys.stdout)
    fmt = "%(asctime)s %(name)s %(levelname)s %(message)s"
    try:
        handler.setFormatter(logging.Formatter(fmt))
    except Exception:
        pass
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelprefix)s %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
