from ast import literal_eval
import json
from os.path import exists


def load_json_from_file(path):
    try:
        with open(path, 'r+' if exists(path) else 'w+') as fp:
            return literal_eval(json.load(fp))
    except Exception:
        return {}
