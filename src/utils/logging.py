import logging

from src.definitions.common import LOG_LOCATION


logging.basicConfig(filename=LOG_LOCATION)


def info(message):
    """
    Log message at info log level.

    :param message: Message to log.
    """
    logging.log(logging.INFO, message)


def warn(message):
    """
    Log message at warning log level.

    :param message: Message to log.
    """
    logging.log(logging.WARN, message)


def error(message):
    """
    Log message at error log level.

    :param message: Message to log.
    """
    logging.log(logging.ERROR, message)


def print_and_log(message, method, max_size=None):
    print(message if max_size is None else message[0:min(len(message), max_size)])
    method(message)
