from math import log2

from src.utils.errors import handle_error


def get_with_fallbacks(sources, targets, default=None):
    """
    TODO.
    :param sources:
    :param targets:
    :param default:
    """

    for i, source in enumerate(sources):
        try:
            target = targets[i]
            if type(source) == dict and source.get(target) is not None:
                return source[target]
            else:
                value = getattr(source, target, None)
                if value is not None:
                    return value
        except Exception as e:
            handle_error(e)
            continue

    return default


def is_empty(value):
    """
    Returns True if the value is "empty," which is defined as one of the following:

    None, empty string, whitespace-only string, empty list/tuple, list/tuple with all empty elements,
    empty dictionary, dictionary with all empty elements

    :param value: Value to check.
    """

    typ = type(value)
    return ((value is None) or
            (typ == str and len(value.strip()) == 0) or
            ((typ == list or type == tuple) and all([is_empty(e) for e in value])) or
            (typ == dict and all([is_empty(v) for v in value.values()])))


def log2smooth(x):
    """
    Returns value of the log2 function applied to the input with a smoothing adjustment of 1.

    :param x: Value on which to apply the log2 function.
    """
    return log2(x + 1)
