from collections import ChainMap

EXIT = 'exit'
MATCH = 'match'
RELOAD = 'reload'

EXIT_KEYWORDS = {k: EXIT for k in {EXIT, 'done', 'bye', 'kill'}}
MATCH_KEYWORDS = {k: MATCH for k in {MATCH, 'find'}}
RELOAD_KEYWORDS = {k: RELOAD for k in {RELOAD, 'refresh'}}

CANONICAL_COMMANDS = dict(ChainMap(EXIT_KEYWORDS, MATCH_KEYWORDS, RELOAD_KEYWORDS))
ALL_VALID_COMMANDS = set(CANONICAL_COMMANDS.keys())
