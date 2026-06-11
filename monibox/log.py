import logging

_FORMAT = "[%(levelname)s] %(asctime)s - %(name)s - %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    """配置根日志器格式，供 CLI 入口统一调用。"""
    logging.basicConfig(level=level, format=_FORMAT)


def get_logger(name: str = "monibox"):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(h)
    return logger
