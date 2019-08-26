class Command:
    """ Encapsulates a mixing assistant command. """

    def __init__(self, cmd, description, function, aliases={}, arguments=[]):
        """
        Initialize command with description, execution function, and any aliases or and/or required arguments.

        :param cmd: Command name.
        :param description: Command description.
        :param function: Mixing assistant function used to execute command.
        :param aliases: Command aliases (if any).
        :param arguments: Command arguments (if any).
        """
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
        """ Prints a well-formatted usage string for this command. """

        arg_summary = '' if self.num_args == 0 else (' [%s]' % ' '.join([a.get_name() for a in self.arguments]))
        arg_detail = '' if self.num_args == 0 else ('\n  Arguments:\n\t%s' % '\n\t'.join(
            [a.print() for a in self.arguments]))
        aliases = '' if self.num_aliases == 0 else ('\n  Command aliases: %s' % ', '.join(self.aliases))
        description = ' - %s' % self.description

        return '%s%s%s%s%s\n' % (self.cmd, arg_summary, description, aliases, arg_detail)


class CommandArgument:
    """ Encapsulates a mixing assistant command argument. """

    def __init__(self, name, typ, description, position, example):
        """
        Initialize command argument with type, description, position and an example input.

        :param name: Argument name.
        :param typ: Input type (e.g. string).
        :param description: Description of the argument.
        :param position: Position of the argument in the argument string.
        :param example: An example of a value this argument could have.
        """

        self.name = name
        self.typ = typ
        self.description = description
        self.position = position
        self.example = example

    def get_name(self):
        return self.name

    def get_type(self):
        return self.typ

    def get_description(self):
        return self.description

    def get_position(self):
        return self.position

    def get_example(self):
        return self.example

    def print(self):
        """ Prints a well-formatted description of the argument. """
        return '%s (%s): %s (example: %s)' % (self.name, self.typ, self.description, self.example)

    def __lt__(self, other):
        return self.position < other.position


class CommandParsingException(Exception):
    """ Exception class for command parsing errors. """
    pass
