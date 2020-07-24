from sqlalchemy import Column, Integer, Sequence

from src.db import metadata
from src.db import Base


class FeatureValue(Base):
    """
    Represents row in feature_value table in the sqlalchemy ORM. Postgres schema:

                Table "public.feature_value"
      Column  |  Type   | Collation | Nullable | Default
    ----------+---------+-----------+----------+---------
     id       | integer |           | not null |
     track_id | integer |           | not null |
     features | json    |           | not null |
    Indexes:
        "feature_value_pkey" PRIMARY KEY, btree (id, track_id)
        "ix_feature_value_id" UNIQUE, btree (id)
        "ix_feature_value_track_id" UNIQUE, btree (track_id)
    Foreign-key constraints:
        "feature_value_track_id_fkey" FOREIGN KEY (track_id) REFERENCES track(id)
    Referenced by:
        TABLE "transition_match" CONSTRAINT "transition_match_candidate_id_fkey" FOREIGN KEY (candidate_id) REFERENCES
            feature_value(track_id)
        TABLE "transition_match" CONSTRAINT "transition_match_on_deck_id_fkey" FOREIGN KEY (on_deck_id) REFERENCES
            feature_value(track_id)
    """

    __tablename__ = 'feature_value'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, Sequence('feature_value_seq', metadata=metadata), primary_key=True, index=True, unique=True)
