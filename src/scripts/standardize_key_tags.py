from src.definitions.data_management import *
from src.utils.file_operations import *


def standardize_key_tags():
    """ Uses track titles to set a standard ID3 key tag for all audio files. """

    warnings = []
    errors = []
    for track in get_audio_files():
        try:
            md = load(join(PROCESSED_MUSIC_DIR, track))
            if md is None:
                warnings.append('Could not load ID3 data for %s' % track)
                continue
            md = md.tag
            key_frame = list(filter(lambda frame: frame.id.decode('utf-8') == ID3Tag.KEY.value, md.frameiter()))

            if len(key_frame) == 1:
                track_md = re.findall(MD_FORMAT_REGEX, track)
                _, key, _ = track_md[0]
                key_frame[0].text = key
                md.save()
            else:
                warnings.append('No key frame found for %s' % track)
        except Exception as e:
            errors.append('Error with track %s: %s' % (track, str(e)))
            continue

    warnings = '\n'.join(sorted(warnings))
    errors = '\n'.join(sorted(errors))
    print('Warnings:\n%s' % warnings)
    print('\n\nErrors:\n%s' % errors)


if __name__ == '__main__':
    standardize_key_tags()
