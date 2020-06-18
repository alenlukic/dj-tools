from sqlalchemy import Column, Integer, Sequence

from src.db import metadata
from src.db import Base


class InitialTagRecord(Base):
    """
    Postgres schema:

                         Table "public.initial_tags"
         Column     |       Type        | Collation | Nullable | Default
    ----------------+-------------------+-----------+----------+---------
     id             | integer           |           | not null |
     track_id       | integer           |           | not null |
     ID3Tag.TITLE   | character varying |           |          |
     ID3Tag.ARTIST  | character varying |           |          |
     ID3Tag.REMIXER | character varying |           |          |
     ID3Tag.GENRE   | character varying |           |          |
     ID3Tag.KEY     | character varying |           |          |
     ID3Tag.LABEL   | character varying |           |          |
     ID3Tag.BPM     | integer           |           |          |
     ID3Tag.ENERGY  | integer           |           |          |
    Indexes:
        "initial_tags_pkey" PRIMARY KEY, btree (id, track_id)
        "ix_initial_tags_id" UNIQUE, btree (id)
        "ix_initial_tags_track_id" UNIQUE, btree (track_id)
        "ix_initial_tags_ID3Tag.ARTIST" btree ("ID3Tag.ARTIST")
        "ix_initial_tags_ID3Tag.BPM" btree ("ID3Tag.BPM")
        "ix_initial_tags_ID3Tag.ENERGY" btree ("ID3Tag.ENERGY")
        "ix_initial_tags_ID3Tag.GENRE" btree ("ID3Tag.GENRE")
        "ix_initial_tags_ID3Tag.KEY" btree ("ID3Tag.KEY")
        "ix_initial_tags_ID3Tag.LABEL" btree ("ID3Tag.LABEL")
        "ix_initial_tags_ID3Tag.REMIXER" btree ("ID3Tag.REMIXER")
        "ix_initial_tags_ID3Tag.TITLE" btree ("ID3Tag.TITLE")
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
         Column     |       Type        | Collation | Nullable | Default
    ----------------+-------------------+-----------+----------+---------
     id             | integer           |           | not null |
     track_id       | integer           |           | not null |
     ID3Tag.TITLE   | character varying |           |          |
     ID3Tag.ARTIST  | character varying |           |          |
     ID3Tag.REMIXER | character varying |           |          |
     ID3Tag.GENRE   | character varying |           |          |
     ID3Tag.KEY     | character varying |           |          |
     ID3Tag.LABEL   | character varying |           |          |
     ID3Tag.BPM     | integer           |           |          |
     ID3Tag.ENERGY  | integer           |           |          |
    Indexes:
        "post_mik_tags_pkey" PRIMARY KEY, btree (id, track_id)
        "ix_post_mik_tags_id" UNIQUE, btree (id)
        "ix_post_mik_tags_track_id" UNIQUE, btree (track_id)
        "ix_post_mik_tags_ID3Tag.ARTIST" btree ("ID3Tag.ARTIST")
        "ix_post_mik_tags_ID3Tag.BPM" btree ("ID3Tag.BPM")
        "ix_post_mik_tags_ID3Tag.ENERGY" btree ("ID3Tag.ENERGY")
        "ix_post_mik_tags_ID3Tag.GENRE" btree ("ID3Tag.GENRE")
        "ix_post_mik_tags_ID3Tag.KEY" btree ("ID3Tag.KEY")
        "ix_post_mik_tags_ID3Tag.LABEL" btree ("ID3Tag.LABEL")
        "ix_post_mik_tags_ID3Tag.REMIXER" btree ("ID3Tag.REMIXER")
        "ix_post_mik_tags_ID3Tag.TITLE" btree ("ID3Tag.TITLE")
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
         Column     |       Type        | Collation | Nullable | Default
    ----------------+-------------------+-----------+----------+---------
     id             | integer           |           | not null |
     track_id       | integer           |           | not null |
     ID3Tag.TITLE   | character varying |           |          |
     ID3Tag.ARTIST  | character varying |           |          |
     ID3Tag.REMIXER | character varying |           |          |
     ID3Tag.GENRE   | character varying |           |          |
     ID3Tag.KEY     | character varying |           |          |
     ID3Tag.LABEL   | character varying |           |          |
     ID3Tag.BPM     | integer           |           |          |
     ID3Tag.ENERGY  | integer           |           |          |
    Indexes:
        "post_rekordbox_tags_pkey" PRIMARY KEY, btree (id, track_id)
        "ix_post_rekordbox_tags_id" UNIQUE, btree (id)
        "ix_post_rekordbox_tags_track_id" UNIQUE, btree (track_id)
        "ix_post_rekordbox_tags_ID3Tag.ARTIST" btree ("ID3Tag.ARTIST")
        "ix_post_rekordbox_tags_ID3Tag.BPM" btree ("ID3Tag.BPM")
        "ix_post_rekordbox_tags_ID3Tag.ENERGY" btree ("ID3Tag.ENERGY")
        "ix_post_rekordbox_tags_ID3Tag.GENRE" btree ("ID3Tag.GENRE")
        "ix_post_rekordbox_tags_ID3Tag.KEY" btree ("ID3Tag.KEY")
        "ix_post_rekordbox_tags_ID3Tag.LABEL" btree ("ID3Tag.LABEL")
        "ix_post_rekordbox_tags_ID3Tag.REMIXER" btree ("ID3Tag.REMIXER")
        "ix_post_rekordbox_tags_ID3Tag.TITLE" btree ("ID3Tag.TITLE")
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
         Column     |       Type        | Collation | Nullable | Default
    ----------------+-------------------+-----------+----------+---------
     id             | integer           |           | not null |
     track_id       | integer           |           | not null |
     ID3Tag.TITLE   | character varying |           |          |
     ID3Tag.ARTIST  | character varying |           |          |
     ID3Tag.REMIXER | character varying |           |          |
     ID3Tag.GENRE   | character varying |           |          |
     ID3Tag.KEY     | character varying |           |          |
     ID3Tag.LABEL   | character varying |           |          |
     ID3Tag.BPM     | integer           |           |          |
     ID3Tag.ENERGY  | integer           |           |          |
    Indexes:
        "final_tags_pkey" PRIMARY KEY, btree (id, track_id)
        "ix_final_tags_id" UNIQUE, btree (id)
        "ix_final_tags_track_id" UNIQUE, btree (track_id)
        "ix_final_tags_ID3Tag.ARTIST" btree ("ID3Tag.ARTIST")
        "ix_final_tags_ID3Tag.BPM" btree ("ID3Tag.BPM")
        "ix_final_tags_ID3Tag.ENERGY" btree ("ID3Tag.ENERGY")
        "ix_final_tags_ID3Tag.GENRE" btree ("ID3Tag.GENRE")
        "ix_final_tags_ID3Tag.KEY" btree ("ID3Tag.KEY")
        "ix_final_tags_ID3Tag.LABEL" btree ("ID3Tag.LABEL")
        "ix_final_tags_ID3Tag.REMIXER" btree ("ID3Tag.REMIXER")
        "ix_final_tags_ID3Tag.TITLE" btree ("ID3Tag.TITLE")
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
