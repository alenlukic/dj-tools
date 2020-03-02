import sys

from src.tools.data_management.data_manager import DataManager


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Scripts requires IDs of tracks to delete')
        sys.exit(1)

    track_ids_to_delete = set([int(x) for x in sys.argv[1:]])
    dm = DataManager()
    dm.delete_tracks(track_ids_to_delete)
