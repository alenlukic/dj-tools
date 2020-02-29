from collections import ChainMap
import re

from src.definitions.common import PROCESSED_MUSIC_DIR
from src.tools.mixing.command import Command
from src.tools.mixing.command_argument import CommandArgument


EXIT = 'exit'
MATCH = 'match'
LINT = 'lint'
RELOAD = 'reload'
RENAME = 'rename'

EXIT_ALIASES = {'done', 'bye', 'kill'}
MATCH_ALIASES = {'find'}
RELOAD_ALIASES = {'refresh'}

ALL_ALIASES = {EXIT, MATCH, LINT, RELOAD, RENAME}.union(EXIT_ALIASES).union(MATCH_ALIASES).union(RELOAD_ALIASES)

ALIAS_MAPPING = dict(
    ChainMap(
        {a: EXIT for a in EXIT_ALIASES},
        {a: MATCH for a in MATCH_ALIASES},
        {a: RELOAD for a in RELOAD_ALIASES}
    )
)

COMMANDS = {
    EXIT: Command(EXIT, 'Shut the assistant down.', 'shutdown', EXIT_ALIASES),
    MATCH: Command(
        MATCH,
        'Find harmonic mixing matches for the given BPM and Camelot code.', 'get_transition_matches',
        MATCH_ALIASES,
        [
            CommandArgument('track_title', 'string', 'Current track title.', 0,
                            '[05A - Cm - 140] Leftfield - Song Of Life (John Askew Remix)')
        ]
    ),
    LINT: Command(LINT, 'Prints malformed track names to stdout.', 'print_malformed_tracks'),
    RELOAD: Command(RELOAD, 'Reload processed tracks.', 'reload_track_data', RELOAD_ALIASES),
    RENAME: Command(
        RENAME,
        'Rename tracks in the unprocessed audio directory.',
        'rename_tracks',
        {},
        [CommandArgument('upsert', 'boolean', 'Indicates whether to upsert.', 0, 'False')]
    )
}

DASHED_LINE = ''.join(['-'] * 148)

QUALIFIED_PATH_REGEX = re.compile(r'%s.*' % PROCESSED_MUSIC_DIR)

RESULT_COLUMN_HEADER = '    '.join(['Score', 'Track'])
