# noinspection PyUnresolvedReferences
import readline

from src.tools.assistant.command import CommandParsingException
from src.tools.assistant.assistant import Assistant
from src.utils.errors import handle_error
from src.utils.assistant import print_error


def run_assistant():
    """ Accepts user input in an infinite loop until termination. """

    ma = Assistant()
    print('Assistant is now online.')

    while True:
        print('\n$ ', end='')
        try:
            ma.execute(input())
        except CommandParsingException as e:
            handle_error(e, 'Failed to parse command:', print_error)
        except Exception as e:
            handle_error(e, 'An unexpected exception occurred:', print_error)


if __name__ == '__main__':
    run_assistant()
