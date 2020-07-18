from ast import literal_eval
import json


def load_json_from_file(path):
    with open(path, 'r') as fp:
        try:
            return literal_eval(json.load(fp))
        except Exception:
            return {}
