from datetime import datetime
from functools import reduce
from math import log2
from os.path import join

from src.definitions.common import CONFIG, TIMESTAMP_FORMAT


def default_transform(value):
    return value


def datetime_transform(value):
    return (
        None
        if value is None
        else datetime.strptime(value, TIMESTAMP_FORMAT).timestamp()
    )


def float_transform(value):
    return None if value is value is None else float(value)


def int_transform(value):
    return None if value is value is None else int(value)


def string_transform(value):
    return None if value is value is None else str(value)


def get_config_value(path):
    if len(path) == 0:
        return None

    return reduce(lambda x, y: x.get(y, {}), path, CONFIG)


def get_or_default(source, target, transform=default_transform, default=None):
    value = getattr(source, target, default)
    return transform(value)


def get_banner(message):
    return "=" * min(120, len(message))


def is_empty(value):
    """
    Returns True if the value is "empty," which is defined as one of the following:

    None, empty string, whitespace-only string, empty list/tuple, list/tuple with all empty elements,
    empty dictionary, dictionary with all empty elements
    """

    typ = type(value)
    return (
        (value is None)
        or (typ == str and (len(value.strip()) == 0 or value.strip() == "\x00"))
        or ((typ == list or type == tuple) and all([is_empty(e) for e in value]))
        or (typ == dict and all([is_empty(v) for v in value.values()]))
    )


def join_config_paths(paths):
    if len(paths) == 0:
        return None

    return reduce(
        lambda x, y: join(get_config_value(x), get_config_value(y)), paths[1:], paths[0]
    )


def log2smooth(x, smoother=1):
    return log2(x + smoother)


def print_progress(batch_name, cur_iteration, batch_size, frequency=100):
    if cur_iteration % frequency == 0:
        print("Processed %d of %d %s" % (cur_iteration, batch_size, batch_name))
