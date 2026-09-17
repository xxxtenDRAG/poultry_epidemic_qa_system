"""统一日志配置。"""
import logging
import sys

FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format=FORMAT, stream=sys.stdout)


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
