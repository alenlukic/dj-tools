from datetime import datetime
from functools import reduce
import json
from math import log2
from os.path import join
from shutil import copyfile

from src.definitions.common import CONFIG
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


def get_config_value(path):
    if len(path) == 0:
        return None

    return reduce(lambda x, y: x.get(y, {}), path, CONFIG)


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
    return '=' * min(120, len(message))


def is_empty(value):
    """
    Returns True if the value is "empty," which is defined as one of the following:

    None, empty string, whitespace-only string, empty list/tuple, list/tuple with all empty elements,
    empty dictionary, dictionary with all empty elements
    """

    typ = type(value)
    return ((value is None) or
            (typ == str and (len(value.strip()) == 0 or value.strip() == '\x00')) or
            ((typ == list or type == tuple) and all([is_empty(e) for e in value])) or
            (typ == dict and all([is_empty(v) for v in value.values()])))


def join_config_paths(paths):
    if len(paths) == 0:
        return None

    return reduce(lambda x, y: join(get_config_value(x), get_config_value(y)), paths[1:], paths[0])


def log2smooth(x, smoother=1):
    """ Returns value of the log2 function applied to the input with a smoothing adjustment. """
    return log2(x + smoother)


def print_progress(batch_name, cur_iteration, batch_size, frequency=100):
    if cur_iteration % frequency == 0:
        print('Processed %d of %d %s' % (cur_iteration, batch_size, batch_name))


def update_config(path, new_val):
    num_segments = len(path)
    if num_segments == 0:
        return

    copyfile('config/config.json', 'config/config_old.json')

    update_target = CONFIG
    for segment in path[0:num_segments - 1]:
        update_target = update_target[segment]

    update_target[path[-1]] = new_val
    with open('config/config.json', 'w') as w:
        json.dump(CONFIG, w, indent=2)
