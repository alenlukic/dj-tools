from os import system
from os.path import join, splitext
import shlex
import sys

from src.utils.file_operations import get_lossless_files


def convert_lossless_to_aiff(input_dir):
    lossless_files = get_lossless_files(input_dir)
    sanitized_input_dir = input_dir.strip()
    for ll in lossless_files:
        track_name = splitext(ll)[0].strip()
        input_name = join(sanitized_input_dir, ll)
        output_name = join(sanitized_input_dir, track_name + '.aiff')

        print(input_name, output_name)

        command = "ffmpeg -i %s -write_id3v2 1 -id3v2_version 3 -c:v copy %s" % (
            shlex.quote(input_name),
            shlex.quote(output_name),
        )
        system(command)


if __name__ == '__main__':
    convert_lossless_to_aiff(sys.argv[1])
