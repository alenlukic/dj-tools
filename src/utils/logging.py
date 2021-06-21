import logging

from src.definitions.common import LOG_LOCATION


logging.basicConfig(filename=LOG_LOCATION)


class Logger:
    def __init__(self, prefix):
        self.prefix = prefix

    def print(self, message):
        print('%s %s' % (self.prefix, message))


def info(message):
    logging.log(logging.INFO, message)


def warn(message):
    logging.log(logging.WARN, message)


def error(message):
    logging.log(logging.ERROR, message)


def print_and_log(message, method, max_size=None):
    print(message if max_size is None else message[0:min(len(message), max_size)])
    method(message)
