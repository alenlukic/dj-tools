from src.definitions.mixing_assistant import COMMANDS


def print_error(message):
    """
    Prints error message along with usage descriptions for each command.

    :param message: Error message.
    """

    print(message)
    print('\n--- Usage ---\n')
    for cmd in COMMANDS.values():
        print(cmd.print_usage())
