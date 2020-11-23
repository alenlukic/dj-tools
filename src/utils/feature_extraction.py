import json
from os.path import exists


def load_json_from_file(path):
    """
    Load feature JSON from file.

    :param path: Path to the file.
    """

    try:
        with open(path, 'r+' if exists(path) else 'w+') as fp:
            return json.load(fp)
    except Exception:
        return {}
