def is_empty(value):
    """
    Returns True if the value is "empty," which is defined as:

    - None
    - empty string
    - string containing only whitespace characters
    - empty list
    - list iff this function returns True recursively for all elements
    - empty dictionary
    - dictionary iff this function returns True recursively for all values

    :param value - value to check.
    """

    typ = type(value)
    return ((value is None) or
            (typ == str and len(value.strip()) == 0) or
            (typ == list and all([is_empty(e) for e in value])) or
            (typ == dict and all([is_empty(v) for v in value.values()])))