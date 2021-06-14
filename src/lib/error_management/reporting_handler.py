import os
import sys
import traceback

from src.definitions.error_management import MAX_ERROR_MESSAGE_SIZE
from src.utils.common import get_banner
from src.utils.logging import *


def handle(err, err_message_prefix='Exception occurred', err_log_function=print, print_traceback=True):
    """
    Handles error and prints debug info/stack trace to stdout.

    :param err: The error to handle.
    :param err_message_prefix: (optional) Prefix to append to stringified error.
    :param err_log_function: (optional) Function to use to log error message.
    :param print_traceback: (optional) Controls whether the stack trace will be printed.
    """
    _, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

    banner = get_banner(err_message_prefix)
    prefix = '\n' + '\n'.join([banner, err_message_prefix, banner]) + '\n'
    message = '\n'.join([prefix, 'Message:', str(err)])
    err_log_function(message[0:min(MAX_ERROR_MESSAGE_SIZE, len(message))])

    print_and_log('\n', error)
    print_and_log('\n'.join(['Function: %s' % fname, 'Line: %d' % exc_tb.tb_lineno]), error)
    if print_traceback:
        print_and_log('\nTraceback:', error)
        traceback.print_tb(exc_tb)
