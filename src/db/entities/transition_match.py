from sqlalchemy import Column, Integer, Sequence

from src.db import metadata
from src.db import Base


class TransitionMatch(Base):
    """
    Represents row in transition_match table in the sqlalchemy ORM. Postgres schema:

                  Table "public.transition_match"
        Column     |       Type        | Collation | Nullable | Default
    ---------------+-------------------+-----------+----------+---------
     id            | integer           |           | not null |
     on_deck_id    | integer           |           | not null |
     candidate_id  | integer           |           | not null |
     match_factors | json              |           | not null |
     relative_key  | character varying |           | not null |
    Indexes:
        "transition_match_pkey" PRIMARY KEY, btree (id, on_deck_id, candidate_id)
        "ix_transition_match_id" UNIQUE, btree (id)
        "transition_match_on_deck_id_candidate_id_idx" UNIQUE, btree (on_deck_id, candidate_id)
    Foreign-key constraints:
        "transition_match_candidate_id_fkey" FOREIGN KEY (candidate_id) REFERENCES feature_value(track_id)
        "transition_match_on_deck_id_fkey" FOREIGN KEY (on_deck_id) REFERENCES feature_value(track_id)
    """

    __tablename__ = 'transition_match'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, Sequence('transition_match_seq', metadata=metadata), primary_key=True, index=True, unique=True)
