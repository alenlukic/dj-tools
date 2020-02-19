import os
import sys
import traceback

from src.utils.common import is_empty


def handle_error(error, err_message_prefix='', err_log_function=print):
    """
    Handles error and prints debug info/stack trace to stdout.

    :param error: The error to handle.
    :param err_message_prefix: (optional) Prefix to append to stringified error.
    :param err_log_function: (optional) Function to use to log error message.
    """
    _, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

    print('Function: %s\tLine:%d\nTraceback:\n' % (fname, exc_tb.tb_lineno))
    traceback.print_tb(exc_tb)
    err_log_function(' '.join(list(filter(lambda s: not is_empty(s), [err_message_prefix, str(error)]))))
