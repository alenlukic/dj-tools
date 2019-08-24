from collections import ChainMap
from sys import exit

from src.definitions.script_keywords import *
from src.tools.dj_tools import DJTools


CANONICAL_COMMANDS = dict(
    ChainMap({MATCH: MATCH}, keyword_map(EXIT_KEYWORDS, EXIT), keyword_map(RELOAD_KEYWORDS, RELOAD))
)

COMMAND_ARGS = {
    EXIT: [],
    MATCH: [(0, 'bpm', 'BPM'), (1, 'camelot_code', 'Camelot code')],
    RELOAD: []
}

COMMAND_FUNCTIONS = {
    EXIT: EXIT,
    MATCH: 'get_transition_matches',
    RELOAD: 'reload_track_data'
}


class CommandParsingException(Exception):
    pass


def is_valid_command(cmd):
    return cmd in ALL_VALID_COMMANDS


def parse(user_input):
    segments = user_input.split()

    # Validate that command is valid
    cmd = segments[0].lower()
    if not is_valid_command(cmd):
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


class MixingAssistant:
    """" Assistant. """

    def __init__(self):
        self.tools = DJTools()

    def execute(self, cmd, args):
        getattr(self, cmd)(**args)

    def exit(self):
        print('Goodbye.')
        exit()

    def get_transition_matches(self, bpm, camelot_code):
        self.tools.get_transition_matches(int(bpm), camelot_code)

    def reload_track_data(self):
        self.tools.reload_track_data()
        print('Track data reloaded.')


def run_assistant():
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


if __name__ == '__main__':
    run_assistant()
