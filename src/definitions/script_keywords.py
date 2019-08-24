EXIT = 'exit'
MATCH = 'match'
RELOAD = 'reload'

EXIT_KEYWORDS = {EXIT, 'done', 'bye', 'kill'}
RELOAD_KEYWORDS = {RELOAD, 'refresh'}

ALL_VALID_COMMANDS = EXIT_KEYWORDS.union({MATCH}).union(RELOAD_KEYWORDS)


def keyword_map(keywords, canonical_form):
    return {k: canonical_form for k in keywords}
