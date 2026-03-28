from os.path import splitext
from pydub import AudioSegment, effects
import sys

PRINT_FREQ = 30
OVERLAP_COEFFICIENT = 16


def print_progress(normalized_audio, original_audio_len, window_len, print_counter):
    updated_print_counter = print_counter + 1

    if updated_print_counter == PRINT_FREQ:
        print(
            "Processed %d of %d ms of audio (window size: %d ms)"
            % (len(normalized_audio), original_audio_len, window_len)
        )
        return 0

    return updated_print_counter


def normalize_segment(
    original_audio, normalized_audio, audio_len_millis, pos, unidirectional_len
):
    start = pos - unidirectional_len
    end = min(pos + unidirectional_len, audio_len_millis)
    segment = normalized_audio[start:pos].append(original_audio[pos:end], 0)

    return normalized_audio[0:start].append(effects.normalize(segment), 0)


def apply_sliding_normalization(original_audio, window_len):
    # TODO: performance is garbage, attempt improvements
    normalized_audio = AudioSegment.empty()
    audio_len_millis = len(original_audio)
    overlap_len = int(window_len / OVERLAP_COEFFICIENT)

    print_counter = 0
    normalized_audio_empty = True
    for pos in range(0, audio_len_millis, overlap_len):
        if normalized_audio_empty:
            segment = original_audio[pos : min(window_len, audio_len_millis)]
            normalized_audio = normalized_audio.append(effects.normalize(segment), 0)
            normalized_audio_empty = False
        else:
            normalized_audio = normalize_segment(
                original_audio, normalized_audio, audio_len_millis, pos, overlap_len
            )

        print_counter = print_progress(
            normalized_audio, audio_len_millis, window_len, print_counter
        )

    if pos < audio_len_millis:
        normalized_audio = normalize_segment(
            original_audio, normalized_audio, audio_len_millis, pos, overlap_len
        )

    return normalized_audio


if __name__ == "__main__":
    args = sys.argv[1:]
    file_paths = []
    window_lens = []
    for i, arg in enumerate(args):
        try:
            window_lens.append(int(arg))
        except:
            file_paths.append(arg)

    for file_path in file_paths:
        name_ext = splitext(file_path)
        name = name_ext[0]
        ext = name_ext[1][1:]
        audio = AudioSegment.from_file(file_path, ext)

        for i in range(len(window_lens)):
            audio = apply_sliding_normalization(audio, window_lens[i] * 1000)

        audio.export(name + "_normalized." + ext, format=ext)
