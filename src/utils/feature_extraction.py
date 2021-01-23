import json
from os.path import exists


def load_json_from_file(path):
    if not exists(path):
        return {}

    try:
        with open(path, 'r+') as fp:
            return json.load(fp)
    except Exception:
        return {}
