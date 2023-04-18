from src.db.entities.attribute import Attribute
from src.db.entities.track_attribute import TrackAttribute
from src.utils.db import invoke_with_session


def get_attributes(attribute_names, sesh=None):
    return invoke_with_session(
        lambda session: session.query(Attribute).filter(Attribute.id.in_(attribute_names)),
        sesh
    )


def create_attributes(attribute_names, sesh=None):
    return invoke_with_session(
        lambda session: session.query(Attribute).filter(Attribute.id.in_(attribute_names)),
        sesh
    )


def get_track_attributes(track_id, sesh=None):
    return invoke_with_session(
        lambda session: session.query(Attribute).filter(Attribute.id.in_(
            [att.attribute_id for att in session.query(TrackAttribute).filter_by(track_id=track_id)])
        ),
        sesh
    )


def get_track_attribute(track_id, attribute_name, sesh=None):
    attributes = filter(lambda x: x.name == attribute_name, get_track_attributes(track_id, sesh))
    return next(iter(attributes), None)


def save_track_attributes(track_id, attribute_names, sesh=None):
    def save_fn(session):
        existing_attributes = get_attributes(attribute_names)
        new_attributes = set(attribute_names).difference(set([att.name for att in existing_attributes]))

        for new_att in new_attributes:
            session.add(Attribute(**{'name': new_att}))
            session.commit()

            att_row = session.query(Attribute).filter_by(name=new_att).first()
            session.add(TrackAttribute(**{'track_id': track_id, 'attribute_id': att_row.id}))

        for att in existing_attributes:
            session.add(TrackAttribute(**{'track_id': track_id, 'attribute_id': att.id}))

        session.commit()

        return get_track_attributes(track_id, session)

    return invoke_with_session(save_fn, sesh)

