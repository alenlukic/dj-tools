from src.db import database


def invoke_with_session(fn, sesh, *args):
    session = sesh or database.create_session()
    try:
        return fn(sesh, args)
    finally:
        if sesh is None:
            session.close()
