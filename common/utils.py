import logging
from pathlib import Path

LOG_FILE = Path.home() / ".mystical" / "mystical.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def log_info(msg: str):
    logging.info(msg)

def log_error(msg: str):
    logging.error(msg)

def log_debug(msg: str):
    logging.debug(msg)