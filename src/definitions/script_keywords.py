from collections import ChainMap

EXIT = 'exit'
HELP = 'help'
MATCH = 'match'
RELOAD = 'reload'
RENAME = 'rename'

EXIT_ALIASES = {EXIT, 'done', 'bye', 'kill'}
HELP_ALIASES = {HELP, 'usage'}
MATCH_ALIASES = {MATCH, 'find'}
RELOAD_ALIASES = {RELOAD, 'refresh'}
RENAME_ALIASES = {RENAME}
ALIASES = [EXIT_ALIASES, MATCH_ALIASES, RELOAD_ALIASES, RENAME_ALIASES]

EXIT_MAP = {k: EXIT for k in EXIT_ALIASES}
HELP_MAP = {k: HELP for k in HELP_ALIASES}
MATCH_MAP = {k: MATCH for k in MATCH_ALIASES}
RELOAD_MAP = {k: RELOAD for k in RELOAD_ALIASES}
RENAME_MAP = {k: RENAME for k in RENAME_ALIASES}

CANONICAL_COMMANDS = dict(ChainMap(EXIT_MAP, HELP_MAP, MATCH_MAP, RELOAD_MAP, RENAME_MAP))
ALL_VALID_COMMANDS = set(CANONICAL_COMMANDS.keys())
