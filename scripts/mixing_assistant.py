from sys import exit

from src.definitions.script_keywords import *
from src.tools.dj_tools import DJTools


COMMAND_ARGS = {
    EXIT: [],
    MATCH: [(0, 'bpm', 'BPM'), (1, 'camelot_code', 'Camelot code')],
    RELOAD: []
}

COMMAND_FUNCTIONS = {
    EXIT: 'shutdown',
    MATCH: 'get_transition_matches',
    RELOAD: 'reload_track_data'
}


class CommandParsingException(Exception):
    pass


def parse(user_input):
    """
    Parses and validates user input and returns command name and argument map.

    :param user_input: Raw user input.
    """

    segments = user_input.split()
    # Validate that command is valid
    cmd = segments[0].lower()
    if cmd not in ALL_VALID_COMMANDS:
        raise CommandParsingException('%s is not a valid command' % cmd)
    cmd = CANONICAL_COMMANDS[cmd]

    # Validate correct number of arguments
    args = segments[1:]
    expected_args = sorted(COMMAND_ARGS[cmd])
    num_args = len(args)
    num_expected_args = len(expected_args)
    if num_args != num_expected_args:
        formatted_args = '' if num_args == 0 else ' - got: %s' % ' '.join(args)
        formatted_expected_args = '' if num_expected_args == 0 else ' (%s)' % ' '.join([a[2] for a in expected_args])
        raise CommandParsingException('%s expects %d arguments%s%s' % (cmd, num_args, formatted_expected_args,
                                                                       formatted_args))

    arg_map = {expected_args[i][1]: args[i] for i in range(num_args)}
    return COMMAND_FUNCTIONS[cmd], arg_map


def run_assistant():
    """ Accepts user input in an infinite loop until termination. """

    print('Mixing assistant is now online.')
    ma = MixingAssistant()

    while True:
        print('\n$ ', end='')
        try:
            cmd, args = parse(input())
            ma.execute(cmd, args)
        except CommandParsingException as e:
            print('Failed to parse command: %s' % (str(e)))
        except Exception as e:
            print('An unexpected exception occurred: %s' % str(e))


class MixingAssistant:
    """" CLI mixing assistant functions."""

    def __init__(self):
        """ Initializes DJ tools class. """
        self.tools = DJTools()

    def execute(self, cmd, args):
        """
        Execute command with arguments.

        :param cmd: Command.
        :param args: Arguments.
        """
        getattr(self, cmd)(**args)

    def get_transition_matches(self, bpm, camelot_code):
        """
        Prints transition matches for given BPM and Camelot code.

        :param bpm: Track BPM.
        :param camelot_code: Track Camelot code.
        """
        self.tools.get_transition_matches(int(bpm), camelot_code)

    def reload_track_data(self):
        """ Reloads tracks from the audio directory and regenerates Camelot map. """
        self.tools.reload_track_data()
        print('Track data reloaded.')

    def shutdown(self):
        """ Exits the CLI. """
        print('Goodbye.')
        exit()


if __name__ == '__main__':
    run_assistant()
