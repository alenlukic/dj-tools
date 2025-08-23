from src.db import database
from src.lib.assistant.definitions.command import CommandParsingException
from src.lib.assistant.service import Assistant
from src.lib.error_management.service import handle
from src.utils.assistant import print_error


def run_assistant():
    assistant = Assistant()
    print("Assistant is now online.")

    while True:
        print("\n$ ", end="")
        try:
            assistant.execute(input())
        except CommandParsingException as e:
            handle(e, "Failed to parse command:", print_error)
        except Exception as e:
            handle(e, "An unexpected exception occurred:", print_error)


if __name__ == "__main__":
    try:
        run_assistant()
    finally:
        database.close_all_sessions()
