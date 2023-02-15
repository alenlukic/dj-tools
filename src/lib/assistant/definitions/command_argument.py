class CommandArgument:
    """ Encapsulates a mixing assistant command argument. """
    def __init__(self, name, typ, description, position, example, required=True):
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
        return '%s (%s): %s (example: %s)%s' % (self.name, self.typ, self.description, self.example,
                                                '' if self.required else ' (optional)')

    def __lt__(self, other):
        return self.position < other.position
