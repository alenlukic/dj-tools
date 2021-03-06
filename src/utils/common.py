from datetime import datetime
from math import log2

from src.definitions.harmonic_mixing import TIMESTAMP_FORMAT


def default_transform(value):
    return value


def datetime_transform(value):
    return None if value is None else datetime.strptime(value, TIMESTAMP_FORMAT).timestamp()


def float_transform(value):
    return None if value is value is None else float(value)


def int_transform(value):
    return None if value is value is None else int(value)


def string_transform(value):
    return None if value is value is None else str(value)


def get_or_default(source, target, transform=default_transform, default=None):
    """
    Transformed and return desired value.

    :param source: Source object.
    :param target: Attribute name to get.
    :param transform: Function to transform the value.
    :param default: Default value.
    """
    value = getattr(source, target, default)
    return transform(value)


def get_banner(message):
    """
    Returns a 'banner' of repeated '=' characters of length equivalent to given message or 120 - whichever is smaller.
    :param message: Message on whch to base banner length
    """
    return '=' * min(120, len(message))


def is_empty(value):
    """
    Returns True if the value is "empty," which is defined as one of the following:

    None, empty string, whitespace-only string, empty list/tuple, list/tuple with all empty elements,
    empty dictionary, dictionary with all empty elements

    :param value: Value to check.
    """

    typ = type(value)
    return ((value is None) or
            (typ == str and (len(value.strip()) == 0 or value.strip() == '\x00')) or
            ((typ == list or type == tuple) and all([is_empty(e) for e in value])) or
            (typ == dict and all([is_empty(v) for v in value.values()])))


def log2smooth(x):
    """
    Returns value of the log2 function applied to the input with a smoothing adjustment of 1.

    :param x: Value on which to apply the log2 function.
    """
    return log2(x + 1)


def print_progress(batch_name, cur_iteration, batch_size, frequency=100):
    """
    Prints iteration progress for some batched task.

    :param batch_name: Descriptive name of batch task
    :param cur_iteration: The current iteration
    :param batch_size: Total batch size
    :param frequency: How frequently to output progress
    """
    if cur_iteration % frequency == 0:
        print('Processed %d of %d %s' % (cur_iteration, batch_size, batch_name))
