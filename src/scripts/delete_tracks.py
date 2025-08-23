import sys

from src.lib.data_management.service import delete_tracks


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Scripts requires IDs of tracks to delete")
        sys.exit(1)

    id_args = sys.argv[1:]
    if "..." in id_args[0]:
        start, end = tuple(id_args[0].split("..."))
        track_ids_to_delete = set(range(int(start), int(end) + 1))
    else:
        track_ids_to_delete = set([int(x) for x in id_args])

    delete_tracks(track_ids_to_delete)
