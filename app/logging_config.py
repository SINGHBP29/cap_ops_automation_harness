import logging
import sys
from pythonjsonlogger import jsonlogger


def configure_logging():

    logger = logging.getLogger()

    logger.setLevel(logging.INFO)

    log_handler = logging.StreamHandler(sys.stdout)

    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s'
    )

    log_handler.setFormatter(formatter)

    logger.addHandler(log_handler)

    return logger