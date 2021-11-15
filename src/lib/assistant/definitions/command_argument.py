class CommandArgument:
    """ Encapsulates a mixing assistant command argument. """

    def __init__(self, name, typ, description, position, example, required=True):
        """
        Initialize command argument with type, description, position and an example input.

        :param name: Argument name.
        :param typ: Input type (e.g. string).
        :param description: Description of the argument.
        :param position: Position of the argument in the argument string.
        :param example: An example of a value this argument could have.
        :param required: Whether this is a required argument or not.
        """

        self.name = name
        self.typ = typ
        self.description = description
        self.position = position
        self.example = example
        self.required = required

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
        return '%s (%s): %s (example: %s)%s' % (self.name, self.typ, self.description, self.example,
                                                '' if self.required else ' (optional)')

    def __lt__(self, other):
        return self.position < other.position
