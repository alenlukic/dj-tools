from ast import literal_eval

from src.db import database
from src.definitions.data_management import *
from src.db.entities.track import Track as TrackEntity
from src.utils.errors import handle_error


LABEL_CANON = {
    'joof': 'JOOF',
    'shinemusic': 'Shine Music',
    'vii': 'VII',
    'rfr': 'RFR',
    'cdr': 'CDR',
    'knm': 'KNM',
    'umc': 'UMC',
    'uv': 'UV',
    'nx1': 'NX1',
    'srx': 'SRX',
    'kgg': 'KGG',
    'dpe': 'DPE',
    'kmx': 'KMX',
    'dbx': 'DBX',
    'x7m': 'X7M',
    'cr2': 'CR2',
    'dfc': 'DFC',
    'kd': 'KD',
    'tk': 'TK',
    'uk': 'UK',
    'l.i.e.s.': 'L.I.E.S.',
    'n.a.m.e': 'N.A.M.E',
    'd.o.c.': 'D.O.C.'
}


def get_canonical_form(segment):
    return LABEL_CANON.get(segment, segment.capitalize() if re.match(PAREN_REGEX, segment) is None else segment)


def transform_segments(segments):
    return [get_canonical_form(seg) for seg in segments]


def transform_parens(segment):
    phrase = segment[1:-1]
    return segment.upper() if len(phrase) == 2 else '(' + ' '.join(transform_segments(phrase.split())) + ')'


def transform_label(label):
    parent_label_parens = {'(Armada)', '(Armada Music)', '(Spinnin)'}
    for pl in parent_label_parens:
        if pl in label:
            return label.split(pl)[0].strip()

    label_lower = label.lower()
    if 'hommega' in label_lower:
        return 'HOMmega Productions'

    if 'pure trance' in label_lower and label_lower != 'pure trance progressive':
        return 'Pure Trance Recordings'

    paren_matches = re.findall(PAREN_REGEX, label_lower)
    if len(paren_matches) == 0:
        transformed_segments = transform_segments([lp.strip() for lp in label_lower.split()])
    else:
        paren_match = paren_matches[0]
        paren_begin = label_lower.index(paren_match)
        paren_end = paren_begin + len(paren_match)

        pre_segments = transform_segments([lp.strip() for lp in label_lower[0:paren_begin].split()])
        parens = [transform_parens(label_lower[paren_begin:paren_end])]
        post_segments = transform_segments(([] if paren_end == len(label_lower) - 1 else
                                            [lp.strip() for lp in label_lower[paren_end:].split()]))

        transformed_segments = pre_segments + parens + post_segments

    return ' '.join([seg.strip() for seg in transformed_segments])


def standardize_labels():
    session = database.create_session()
    error = False

    try:
        for track in session.query(TrackEntity).all():
            label = transform_label(track.label)
            track.label = label
            comment = literal_eval(track.comment or '{}')
            comment[TrackDBCols.LABEL.value] = label
            track.comment = str(comment)

    except Exception as e:
        handle_error(e)
        session.rollback()
        error = True

    finally:
        if not error:
            session.commit()
        session.close()


if __name__ == '__main__':
    standardize_labels()
