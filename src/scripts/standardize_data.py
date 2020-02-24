from os.path import splitext

from src.db import database
from src.definitions.data_management import *
from src.db.entities.track import columns, Track as TrackEntity
from src.tools.data_management.formats.aiff_file import AIFFFile
from src.tools.data_management.formats.mp3_file import MP3File
from src.utils.errors import handle_error


GENERAL_CANON = {
    'joof': 'JOOF',
    'j00f': 'JOOF'
}
GENRE_CANON = {
    'electrinica': 'Electronica',
    'psy-trance': 'Psytrance',
    'd&b': 'D&B',
    'dj': 'DJ'
}
LABEL_CANON = {
    'vii': 'VII',
    'rfr': 'RFR',
    'cdr': 'CDR',
    'l.i.e.s.': 'L.I.E.S.',
    'fsoe': 'Future Sound Of Egypt',
    'knm': 'KNM',
    'umc': 'UMC'
}


def apply_canonical_mappings(segment, canon, fallback_canon=GENERAL_CANON):
    if segment in canon:
        return canon[segment]
    if segment in fallback_canon:
        return fallback_canon[segment]

    return segment.capitalize()


def capitalize(entity, canon, fallback_canon=GENERAL_CANON):
    return ' '.join([apply_canonical_mappings(seg, canon, fallback_canon) for seg in entity.split()])


def transform_parens(segment, canon, fallback_canon=GENERAL_CANON):
    phrase = segment[1:-1]
    return segment.upper() if len(phrase) == 2 else '(' + capitalize(phrase, canon, fallback_canon) + ')'


def transform_label(label):
    paren_matches = re.findall(PAREN_REGEX, label)

    if len(paren_matches) == 0:
        transformed_segments = [capitalize(segment, LABEL_CANON) for segment in [lp.strip() for lp in label.split()]]
    else:
        paren_match = paren_matches[0]
        paren_begin = label.index(paren_match)
        paren_end = paren_begin + len(paren_match)

        pre_segments = [lp.strip() for lp in label[0:paren_begin].split()]
        pre_segments = [capitalize(segment, LABEL_CANON) for segment in pre_segments]
        parens = [transform_parens(label[paren_begin:paren_end], LABEL_CANON)]
        post_segments = [] if paren_end == len(label) - 1 else [lp.strip() for lp in label[paren_end:].split()]
        post_segments = [capitalize(segment, LABEL_CANON) for segment in post_segments]

        transformed_segments = pre_segments + parens + post_segments

    return ' '.join([seg.strip() for seg in transformed_segments])


def transform_genre(genre):
    hyphen_matches = re.findall(HYPHEN_REGEX, genre)

    if len(hyphen_matches) > 0:
        hyphen_split = genre.split('|')
        parent_genre = hyphen_split[0].strip().capitalize()
        if parent_genre == 'House':
            return ' '.join([g.strip().capitalize() for g in hyphen_split[1].strip().split()])
        if parent_genre == 'Trance' and hyphen_split[1].strip() == 'psytrance':
            return 'Psytrance'

        return parent_genre

    return capitalize(genre, GENRE_CANON)


def standardize_data():
    session = database.create_session()
    cols = [c for c in columns if c not in {'file_path', 'date_added'}]

    try:
        tracks = session.query(TrackEntity).all()
        for track in tracks:
            file_path = track.file_path
            _, file_ext = splitext(file_path)
            track_model = MP3File(file_path) if file_ext == '.mp3' else AIFFFile(file_path)
            gen_metadata = track_model.get_metadata()

            for col in cols:
                try:
                    col_value = gen_metadata.get(col, getattr(track, col, None))
                    if col_value is None:
                        raise Exception('No value for column %s for track %s (%d)' % (col, file_path, track.id))

                    if type(col_value) == int:
                        setattr(track, col, col_value)
                        continue

                    col_value = col_value.strip()
                    if col == 'label':
                        col_value = transform_label(col_value.lower())
                    elif col == 'genre':
                        col_value = transform_genre(col_value.lower())

                    setattr(track, col, col_value)

                except Exception as e:
                    handle_error(e)
                    session.rollback()
                    break

            session.commit()

    except Exception as e:
        handle_error(e)
        session.rollback()

    finally:
        session.close()


if __name__ == '__main__':
    standardize_data()
