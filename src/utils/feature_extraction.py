import json
from os.path import exists

from src.utils.errors import handle_error


def load_json_from_file(path):
    """
    Load feature JSON from file.

    :param path: Path to the file.
    """

    try:
        with open(path, 'r+' if exists(path) else 'w+') as fp:
            return json.load(fp)
    except Exception as e:
        handle_error(e, '(Path: %s' % path + ')')
        return {}
