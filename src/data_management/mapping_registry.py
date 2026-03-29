"""Registry that loads artist/genre/label canonicalization mappings from the DB.

Call MappingRegistry.load(session) once before processing audio files.
If not loaded, all getters return empty structures (no canonicalization, no crash).
"""

from src.models.artist_mapping import ArtistMapping
from src.models.genre_mapping import GenreMapping
from src.models.label_mapping import LabelMapping


class MappingRegistry:
    _genre_exact: dict = {}
    _label_word: dict = {}
    _label_strip_suffix: list = []
    _label_substring: list = []
    _artist_exact: dict = {}
    _artist_contains: list = []

    @classmethod
    def load(cls, session) -> None:
        """Load all mappings from the DB. Idempotent — safe to call multiple times."""
        genre_rows = session.query(GenreMapping).all()
        cls._genre_exact = {gm.raw_genre: gm.canonical_genre for gm in genre_rows}

        label_rows = session.query(LabelMapping).all()
        cls._label_word = {
            lm.raw_label: lm.canonical_label
            for lm in label_rows
            if lm.match_type == "word"
        }
        cls._label_strip_suffix = [
            lm.raw_label for lm in label_rows if lm.match_type == "strip_suffix"
        ]
        cls._label_substring = [
            (lm.raw_label, lm.canonical_label, lm.exclude_pattern)
            for lm in label_rows
            if lm.match_type == "substring"
        ]

        artist_rows = session.query(ArtistMapping).all()
        cls._artist_exact = {
            am.raw_artist: am.canonical_artist
            for am in artist_rows
            if am.match_type == "exact"
        }
        cls._artist_contains = [
            (am.raw_artist, am.canonical_artist)
            for am in artist_rows
            if am.match_type == "contains"
        ]

    @classmethod
    def genre_exact(cls) -> dict:
        return cls._genre_exact

    @classmethod
    def label_word(cls) -> dict:
        return cls._label_word

    @classmethod
    def label_strip_suffix(cls) -> list:
        return cls._label_strip_suffix

    @classmethod
    def label_substring(cls) -> list:
        return cls._label_substring

    @classmethod
    def artist_exact(cls) -> dict:
        return cls._artist_exact

    @classmethod
    def artist_contains(cls) -> list:
        return cls._artist_contains
