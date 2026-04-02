import threading
import time
from sys import exit

from src.db import database
from src.assistant.config import ALIAS_MAPPING, ALL_ALIASES, COMMANDS, MATCH
from src.assistant.command import CommandParsingException
from src.harmonic_mixing.cosine_cache import CosineCache
from src.models.track import Track
from src.harmonic_mixing.transition_match_finder import TransitionMatchFinder
from src.utils.common import is_empty

_WARM_DEBOUNCE_SECONDS = 10.0


def parse_user_input(user_input):
    stripped_input = user_input.strip()
    if is_empty(stripped_input):
        return

    segments = [seg.strip() for seg in stripped_input.split()]
    if stripped_input[0] == "[":
        cmd_alias = MATCH
        segments = [MATCH] + segments
    else:
        cmd_alias = segments[0].lower()

    if cmd_alias not in ALL_ALIASES:
        raise CommandParsingException("%s is not a valid command." % cmd_alias)

    cmd_name = ALIAS_MAPPING.get(cmd_alias, cmd_alias)
    args = [" ".join(segments[1:])] if cmd_name == MATCH else segments[1:]

    return cmd_name, args


class Assistant:
    """Encapsulates the CLI mixing assistant."""

    def __init__(self):
        self.session = database.create_session()
        self.cosine_cache = CosineCache()
        self.transition_match_finder = TransitionMatchFinder(
            self.session, cosine_cache=self.cosine_cache
        )
        self._last_warm_times: dict[int, float] = {}

    def execute(self, user_input):
        cmd_name, args = parse_user_input(user_input)
        command = COMMANDS[cmd_name]
        num_args = len(args)
        expected_args = command.get_arguments()
        num_expected_args = len([arg for arg in expected_args if arg.required])

        if num_args != num_expected_args:
            formatted_args = "" if num_args == 0 else " - got: %s" % " ".join(args)
            raise CommandParsingException(
                "%s expects %d arguments%s."
                % (cmd_name, num_expected_args, formatted_args)
            )

        cmd_function = command.get_function()
        cmd_args = {
            expected_args[i].get_name(): args[i].strip() for i in range(num_args)
        }
        return getattr(self, cmd_function)(**cmd_args)

    def print_transition_matches(self, track_title):
        self.transition_match_finder.print_transition_matches(track_title)
        self._warm_cache_async(track_title)

    def _warm_cache_async(self, track_title):
        """Start BFS cache warming in a daemon thread so the CLI returns immediately.

        Warming is debounced per track_id: a second call for the same track
        within ``_WARM_DEBOUNCE_SECONDS`` is suppressed.
        """
        track_row = (
            self.session.query(Track).filter_by(title=track_title).first()
        )
        if track_row is None:
            return

        now = time.monotonic()
        last = self._last_warm_times.get(track_row.id, 0.0)
        if now - last < _WARM_DEBOUNCE_SECONDS:
            return

        self._last_warm_times[track_row.id] = now
        t = threading.Thread(
            target=self.cosine_cache.warm_from_db,
            args=(track_row.id,),
            daemon=True,
        )
        t.start()

    def reload_track_data(self):
        self.transition_match_finder.reload_track_data()
        print("Track data reloaded.")

    def shutdown(self):
        """Exits the CLI."""
        print("Goodbye.")
        exit()
