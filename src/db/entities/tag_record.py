from sqlalchemy import Column, Integer, Sequence

from src.db import metadata
from src.db import Base


class InitialTagRecord(Base):
    """
    Postgres schema:

                         Table "public.initial_tags"
      Column  |       Type        | Collation | Nullable | Default
    ----------+-------------------+-----------+----------+---------
     id       | integer           |           | not null |
     track_id | integer           |           | not null |
     TITLE    | character varying |           |          |
     ARTIST   | character varying |           |          |
     REMIXER  | character varying |           |          |
     GENRE    | character varying |           |          |
     KEY      | character varying |           |          |
     LABEL    | character varying |           |          |
     BPM      | integer           |           |          |
     ENERGY   | integer           |           |          |
    Indexes:
        "initial_tags_pkey" PRIMARY KEY, btree (id, track_id)
        "ix_initial_tags_id" UNIQUE, btree (id)
        "ix_initial_tags_track_id" UNIQUE, btree (track_id)
        "ix_initial_tags_ARTIST" btree ("ARTIST")
        "ix_initial_tags_BPM" btree ("BPM")
        "ix_initial_tags_ENERGY" btree ("ENERGY")
        "ix_initial_tags_GENRE" btree ("GENRE")
        "ix_initial_tags_KEY" btree ("KEY")
        "ix_initial_tags_LABEL" btree ("LABEL")
        "ix_initial_tags_REMIXER" btree ("REMIXER")
        "ix_initial_tags_TITLE" btree ("TITLE")
    Foreign-key constraints:
        "initial_tags_track_id_fkey" FOREIGN KEY (track_id) REFERENCES track(id)
    """

    __tablename__ = 'initial_tags'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, Sequence('initial_tags_seq', metadata=metadata), primary_key=True, index=True, unique=True)


class PostMIKTagRecord(Base):
    """
    Postgres schema:

                        Table "public.post_mik_tags"
      Column  |       Type        | Collation | Nullable | Default
    ----------+-------------------+-----------+----------+---------
     id       | integer           |           | not null |
     track_id | integer           |           | not null |
     TITLE    | character varying |           |          |
     ARTIST   | character varying |           |          |
     REMIXER  | character varying |           |          |
     GENRE    | character varying |           |          |
     KEY      | character varying |           |          |
     LABEL    | character varying |           |          |
     BPM      | integer           |           |          |
     ENERGY   | integer           |           |          |
    Indexes:
        "post_mik_tags_pkey" PRIMARY KEY, btree (id, track_id)
        "ix_post_mik_tags_id" UNIQUE, btree (id)
        "ix_post_mik_tags_track_id" UNIQUE, btree (track_id)
        "ix_post_mik_tags_ARTIST" btree ("ARTIST")
        "ix_post_mik_tags_BPM" btree ("BPM")
        "ix_post_mik_tags_ENERGY" btree ("ENERGY")
        "ix_post_mik_tags_GENRE" btree ("GENRE")
        "ix_post_mik_tags_KEY" btree ("KEY")
        "ix_post_mik_tags_LABEL" btree ("LABEL")
        "ix_post_mik_tags_REMIXER" btree ("REMIXER")
        "ix_post_mik_tags_TITLE" btree ("TITLE")
    Foreign-key constraints:
        "post_mik_tags_track_id_fkey" FOREIGN KEY (track_id) REFERENCES track(id)
    """

    __tablename__ = 'post_mik_tags'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, Sequence('post_mik_tags_seq', metadata=metadata), primary_key=True, index=True, unique=True)


class PostRekordboxTagRecord(Base):
    """
    Postgres schema:

                     Table "public.post_rekordbox_tags"
      Column  |       Type        | Collation | Nullable | Default
    ----------+-------------------+-----------+----------+---------
     id       | integer           |           | not null |
     track_id | integer           |           | not null |
     TITLE    | character varying |           |          |
     ARTIST   | character varying |           |          |
     REMIXER  | character varying |           |          |
     GENRE    | character varying |           |          |
     KEY      | character varying |           |          |
     LABEL    | character varying |           |          |
     BPM      | integer           |           |          |
     ENERGY   | integer           |           |          |
    Indexes:
        "post_rekordbox_tags_pkey" PRIMARY KEY, btree (id, track_id)
        "ix_post_rekordbox_tags_id" UNIQUE, btree (id)
        "ix_post_rekordbox_tags_track_id" UNIQUE, btree (track_id)
        "ix_post_rekordbox_tags_ARTIST" btree ("ARTIST")
        "ix_post_rekordbox_tags_BPM" btree ("BPM")
        "ix_post_rekordbox_tags_ENERGY" btree ("ENERGY")
        "ix_post_rekordbox_tags_GENRE" btree ("GENRE")
        "ix_post_rekordbox_tags_KEY" btree ("KEY")
        "ix_post_rekordbox_tags_LABEL" btree ("LABEL")
        "ix_post_rekordbox_tags_REMIXER" btree ("REMIXER")
        "ix_post_rekordbox_tags_TITLE" btree ("TITLE")
    Foreign-key constraints:
        "post_rekordbox_tags_track_id_fkey" FOREIGN KEY (track_id) REFERENCES track(id)
    """

    __tablename__ = 'post_rekordbox_tags'
    __table_args__ = {'extend_existing': True}

    id = Column(
        Integer,
        Sequence('post_rekordbox_tags_seq', metadata=metadata),
        primary_key=True,
        index=True,
        unique=True
    )


class FinalTagRecord(Base):
    """
    Postgres schema:

                          Table "public.final_tags"
      Column  |       Type        | Collation | Nullable | Default
    ----------+-------------------+-----------+----------+---------
     id       | integer           |           | not null |
     track_id | integer           |           | not null |
     TITLE    | character varying |           |          |
     ARTIST   | character varying |           |          |
     REMIXER  | character varying |           |          |
     GENRE    | character varying |           |          |
     KEY      | character varying |           |          |
     LABEL    | character varying |           |          |
     BPM      | integer           |           |          |
     ENERGY   | integer           |           |          |
    Indexes:
        "final_tags_pkey" PRIMARY KEY, btree (id, track_id)
        "ix_final_tags_id" UNIQUE, btree (id)
        "ix_final_tags_track_id" UNIQUE, btree (track_id)
        "ix_final_tags_ARTIST" btree ("ARTIST")
        "ix_final_tags_BPM" btree ("BPM")
        "ix_final_tags_ENERGY" btree ("ENERGY")
        "ix_final_tags_GENRE" btree ("GENRE")
        "ix_final_tags_KEY" btree ("KEY")
        "ix_final_tags_LABEL" btree ("LABEL")
        "ix_final_tags_REMIXER" btree ("REMIXER")
        "ix_final_tags_TITLE" btree ("TITLE")
    Foreign-key constraints:
        "final_tags_track_id_fkey" FOREIGN KEY (track_id) REFERENCES track(id)
    """

    __tablename__ = 'final_tags'
    __table_args__ = {'extend_existing': True}

    id = Column(
        Integer,
        Sequence('final_tags_seq', metadata=metadata),
        primary_key=True,
        index=True,
        unique=True
    )
