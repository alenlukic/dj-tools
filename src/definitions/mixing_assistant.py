from collections import ChainMap

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
            CommandArgument('track_path', 'string', 'Qualified path of the current track.', 0,
                            '/Users/user/Music/[05A - Cm - 140] Leftfield - Song Of Life (John Askew Remix).mp3')
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

RESULT_COLUMN_HEADER = '\t\t\t'.join(['Score', 'Track'])
