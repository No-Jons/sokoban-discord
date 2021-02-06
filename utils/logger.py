import logging
import sys


def setup_logger(name, debug):
    _logger = logging.getLogger(name)

    if debug:
        level = logging.DEBUG
    else:
        level = logging.INFO

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(
        logging.Formatter('[%(asctime)s]: %(name)s - %(levelname)s - %(message)s')
    )

    _logger.addHandler(stream_handler)
    _logger.setLevel(level)
    return _logger
