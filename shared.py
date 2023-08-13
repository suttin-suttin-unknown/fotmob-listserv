import json
import logging
import time


def write_json(path=""):
    if len(path) == 0:
        path = int(time.time())
    with open(path, "w") as f:
        json.dump()


def configure_logger(logger):
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


logger = logging.getLogger(__name__)
