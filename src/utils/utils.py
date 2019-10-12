def is_empty(value):
    """
    Returns True if the value is "empty," which is defined as:

    - None
    - empty string
    - whitespace-only string
    - empty list
    - list for whose elements this function returns True recursively
    - empty dictionary
    - dictionary for whose values this function returns True recursively

    :param value - value to check.
    """

    if value is None:
        return True

    typ = type(value)
    if typ == str and len(value.strip()) == 0:
        return True
    if typ == list and all([is_empty(e) for e in value]):
        return True
    if typ == dict and all([is_empty(v) for v in value.values()]):
        return True

    return False
