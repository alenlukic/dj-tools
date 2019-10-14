from sys import exit

from src.definitions.mixing_assistant import *
from src.tools.data_management.data_manager import DataManager
from src.tools.dj_tools import DJTools
from src.tools.file_management.file_manager import FileManager
from src.utils.mixing_assistant import CommandParsingException


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


class MixingAssistant:
    """" CLI mixing assistant functions."""

    def __init__(self):
        """ Initializes DJ tools class. """
        self.tools = DJTools()
        self.dm = DataManager()
        self.fm = FileManager()

    def execute(self, user_input):
        """
        Parses and validates user input and executes corresponding command.

        :param user_input: Raw user input.
        """

        # Validate command
        segments = user_input.split()
        cmd_alias = segments[0].lower()
        if cmd_alias not in ALL_ALIASES:
            raise CommandParsingException('%s is not a valid command.' % cmd_alias)

        # Validate arguments
        cmd_name = ALIAS_MAPPING.get(cmd_alias, cmd_alias)
        command = COMMANDS[cmd_name]
        args = segments[1:]
        expected_args = command.get_arguments()
        num_args = len(args)
        num_expected_args = len(expected_args)
        if num_args != num_expected_args:
            formatted_args = '' if num_args == 0 else ' - got: %s' % ' '.join(args)
            raise CommandParsingException('%s expects %d arguments%s.' % (cmd_name, num_args, formatted_args))

        # Execute command
        cmd_function = command.get_function()
        cmd_args = {expected_args[i].get_name(): args[i] for i in range(num_args)}
        return getattr(self, cmd_function)(**cmd_args)

    def get_transition_matches(self, bpm, camelot_code):
        """
        Prints transition matches for given BPM and Camelot code.

        :param bpm: Track BPM.
        :param camelot_code: Track Camelot code.
        """
        self.tools.get_transition_matches(int(bpm), camelot_code)

    def print_malformed_tracks(self):
        """ Prints malformed track names to stdout to facilitate corrections. """
        self.dm.show_malformed_tracks()

    def reload_track_data(self):
        """ Reloads tracks from the audio directory and regenerates Camelot map. """
        self.tools.reload_track_data()
        print('Track data reloaded.')

    def rename_tracks(self):
        """ Rename tracks in tmp directory. """
        self.dm.rename_songs()
        print('\nSongs renamed.')

    def shutdown(self):
        """ Exits the CLI. """
        print('Goodbye.')
        exit()


if __name__ == '__main__':
    run_assistant()
