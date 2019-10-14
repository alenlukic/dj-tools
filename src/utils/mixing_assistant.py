from src.definitions.mixing_assistant import COMMANDS
from src.tools.mixing.command import CommandParsingException
from src.tools.mixing.mixing_assistant import MixingAssistant


def print_error(message):
    """
    Prints error message along with usage descriptions for each command.

    :param message: Error message.
    """

    print(message)
    print('\n--- Usage ---\n')
    for cmd in COMMANDS.values():
        print(cmd.print_usage())


def run_assistant():
    """ Accepts user input in an infinite loop until termination. """

    ma = MixingAssistant()
    print('Mixing assistant is now online.')

    while True:
        print('\n$ ', end='')
        try:
            ma.execute(input())
        except CommandParsingException as e:
            print_error('Failed to parse command: %s' % (str(e)))
        except Exception as e:
            print_error('An unexpected exception occurred: %s' % str(e))
