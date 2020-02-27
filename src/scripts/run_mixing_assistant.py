# noinspection PyUnresolvedReferences
import readline

from src.tools.mixing.command import CommandParsingException
from src.tools.mixing.mixing_assistant import MixingAssistant
from src.utils.errors import handle_error
from src.utils.mixing_assistant import print_error


def run_assistant():
    """ Accepts user input in an infinite loop until termination. """

    ma = MixingAssistant()
    print('Mixing assistant is now online.')

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
