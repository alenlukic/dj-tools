import os
import sys
import traceback

from src.utils.common import get_banner
from src.utils.logging import *


def handle_error(err, err_message_prefix='Exception occurred', err_log_function=print):
    """
    Handles error and prints debug info/stack trace to stdout.

    :param err: The error to handle.
    :param err_message_prefix: (optional) Prefix to append to stringified error.
    :param err_log_function: (optional) Function to use to log error message.
    """
    _, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

    banner = get_banner(err_message_prefix)
    prefix = '\n' + '\n'.join([banner, err_message_prefix, banner]) + '\n'
    err_log_function('\n'.join([prefix, 'Message:', str(err)]))
    print_and_log('\n', error)
    print_and_log('\n'.join(['Function: %s' % fname, 'Line: %d' % exc_tb.tb_lineno, 'Traceback:']), error)
    traceback.print_tb(exc_tb)
