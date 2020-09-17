# noinspection PyUnresolvedReferences
import readline

from src.db import database
from src.lib.assistant.command import CommandParsingException
from src.lib.assistant.assistant import Assistant
from src.utils.errors import handle_error
from src.utils.assistant import print_error


def run_assistant():
    """ Accepts user input in an infinite loop until termination. """

    assistant = Assistant()
    print('Assistant is now online.')

    while True:
        print('\n$ ', end='')
        try:
            assistant.execute(input())
        except CommandParsingException as e:
            handle_error(e, 'Failed to parse command:', print_error)
        except Exception as e:
            handle_error(e, 'An unexpected exception occurred:', print_error)


if __name__ == '__main__':
    try:
        run_assistant()
    finally:
        database.close_all_sessions()
