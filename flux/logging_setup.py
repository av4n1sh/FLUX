import logging
from logging.handlers import RotatingFileHandler
from .config import DATA


def configure_logging():
    DATA.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(DATA / "flux.log", maxBytes=500_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger("flux").setLevel(logging.INFO)
    logging.getLogger("flux").addHandler(handler)
