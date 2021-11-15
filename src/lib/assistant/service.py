from sys import exit

from src.db import database
from src.definitions.assistant import *
from src.lib.assistant.definitions.command import CommandParsingException
from src.lib.harmonic_mixing.definitions.transition_match_finder import TransitionMatchFinder
from src.utils.harmonic_mixing import *
from src.utils.assistant import *


def parse_user_input(user_input):
    """
    Parses user input and returns command name and arguments to execute.

    :param user_input: Raw text input.
    """

    stripped_input = user_input.strip()
    if is_empty(stripped_input):
        return

    segments = [seg.strip() for seg in stripped_input.split()]
    if stripped_input[0] == '[':
        cmd_alias = MATCH
        segments = [MATCH] + segments
    else:
        cmd_alias = segments[0].lower()

    if cmd_alias not in ALL_ALIASES:
        raise CommandParsingException('%s is not a valid command.' % cmd_alias)

    cmd_name = ALIAS_MAPPING.get(cmd_alias, cmd_alias)
    args = [' '.join(segments[1:])] if cmd_name == MATCH else segments[1:]

    return cmd_name, args


class Assistant:
    """" CLI assistant functions."""

    def __init__(self):
        """ Initialize the assistant. """
        self.session = database.create_session()
        self.transition_match_finder = TransitionMatchFinder(self.session)

    def execute(self, user_input):
        """
        Parses and validates user input and executes corresponding command.

        :param user_input: Raw user input.
        """

        cmd_name, args = parse_user_input(user_input)
        command = COMMANDS[cmd_name]
        num_args = len(args)
        expected_args = command.get_arguments()
        num_expected_args = len([arg for arg in expected_args if arg.required])

        if num_args != num_expected_args:
            formatted_args = '' if num_args == 0 else ' - got: %s' % ' '.join(args)
            raise CommandParsingException('%s expects %d arguments%s.' % (cmd_name, num_expected_args, formatted_args))

        cmd_function = command.get_function()
        cmd_args = {expected_args[i].get_name(): args[i].strip() for i in range(num_args)}
        return getattr(self, cmd_function)(**cmd_args)

    def print_transition_matches(self, track_title):
        """
        Prints transition matches for the given track.

        :param track_title - Formatted track title (with metadata)
        """

        self.transition_match_finder.print_transition_matches(track_title)

    def reload_track_data(self):
        """ Reloads tracks from the audio directory and regenerates Camelot map and metadata. """

        self.transition_match_finder.reload_track_data()
        print('Track data reloaded.')

    def shutdown(self):
        """ Exits the CLI. """
        print('Goodbye.')
        exit()
