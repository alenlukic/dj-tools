from src.definitions.assistant import COMMANDS

# test
def print_error(message):
    print(message)
    print('\n--- Usage ---\n')
    for cmd in COMMANDS.values():
        print(cmd.print_usage())
