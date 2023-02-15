class Command:
    """ Encapsulates a mixing assistant command. """
    def __init__(self, cmd, description, function, aliases={}, arguments=[]):
        self.cmd = cmd
        self.description = description
        self.function = function
        self.aliases = aliases
        self.arguments = arguments
        self.num_aliases = len(self.aliases)
        self.num_args = len(self.arguments)

    def get_cmd(self):
        return self.cmd

    def get_function(self):
        return self.function

    def get_aliases(self):
        return self.aliases

    def get_arguments(self):
        return sorted(self.arguments)

    def print_usage(self):
        arg_summary = '' if self.num_args == 0 else (' [%s]' % ' '.join([a.get_name() for a in self.arguments]))
        arg_detail = '' if self.num_args == 0 else ('\n  Arguments:\n\t%s' % '\n\t'.join(
            [a.print() for a in self.arguments]))
        aliases = '' if self.num_aliases == 0 else ('\n  Command aliases: %s' % ', '.join(self.aliases))
        description = ' - %s' % self.description

        return '%s%s%s%s%s\n' % (self.cmd, arg_summary, description, aliases, arg_detail)


class CommandParsingException(Exception):
    pass
