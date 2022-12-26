from os import system
from os.path import join, splitext
import sys

from src.utils.file_operations import get_flac_files


def convert_flac_to_aiff(input_dir):
    flac_files = get_flac_files(input_dir)
    for ff in flac_files:
        track_name = splitext(ff)[0]
        input_name = join(input_dir, ff)
        output_name = join(input_dir, track_name + '.aiff')

        print(input_name, output_name)

        system("ffmpeg -i '%s' -write_id3v2 1 -id3v2_version 3 -c:v copy '%s'" % (input_name, output_name))


if __name__ == '__main__':
    convert_flac_to_aiff(sys.argv[1])
