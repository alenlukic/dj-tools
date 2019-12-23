from math import log2


def is_empty(value):
    """
    Returns True if the value is "empty," which is defined as:

    - None
    - empty string
    - string containing only whitespace characters
    - empty list/tuple
    - list/tuple iff this function returns True recursively for all elements
    - empty dictionary
    - dictionary iff this function returns True recursively for all values

    :param value - value to check.
    """

    typ = type(value)
    return ((value is None) or
            (typ == str and len(value.strip()) == 0) or
            ((typ == list or type == tuple) and all([is_empty(e) for e in value])) or
            (typ == dict and all([is_empty(v) for v in value.values()])))


def log2smooth(x):
    """
    Returns value of the log2 function applied to the input with a smoothing adjustment of 1.

    :param x - value on which to apply the log2 function.
    """
    return log2(x + 1)
