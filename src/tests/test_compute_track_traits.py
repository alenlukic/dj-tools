"""Unit tests for compute_track_traits helpers."""

from src.scripts.feature_extraction.compute_track_traits import (
    _chunkify,
    _resolve_audio_path,
)


# ---------------------------------------------------------------------------
# _chunkify
# ---------------------------------------------------------------------------


class TestChunkify:
    def test_even_split(self):
        result = _chunkify([1, 2, 3, 4], 2)
        assert len(result) == 2
        assert result[0] == [1, 2]
        assert result[1] == [3, 4]

    def test_uneven_split_distributes_remainder(self):
        result = _chunkify([1, 2, 3, 4, 5], 3)
        assert len(result) == 3
        total = sum(len(c) for c in result)
        assert total == 5
        assert len(result[0]) >= len(result[-1])

    def test_n_larger_than_list_caps_at_list_length(self):
        result = _chunkify([1, 2, 3], 10)
        assert len(result) == 3
        assert all(len(c) == 1 for c in result)

    def test_n_equals_one_returns_single_chunk(self):
        result = _chunkify([1, 2, 3], 1)
        assert result == [[1, 2, 3]]

    def test_empty_list_returns_empty(self):
        result = _chunkify([], 3)
        assert result == []

    def test_single_element(self):
        result = _chunkify([42], 1)
        assert result == [[42]]

    def test_all_items_present(self):
        items = list(range(20))
        chunks = _chunkify(items, 7)
        assert sorted(i for c in chunks for i in c) == items


# ---------------------------------------------------------------------------
# _resolve_audio_path — non-ASCII fallback only
#
# _resolve_audio_path is NOT called for the direct/happy path; the caller
# constructs join(PROCESSED_MUSIC_DIR, file_name) and passes it straight to
# extractor.compute(). _resolve_audio_path is only invoked when that raises
# an OSError, to attempt a prefix-based fallback for non-ASCII filenames.
# ---------------------------------------------------------------------------


class TestResolveAudioPath:
    def test_pure_ascii_returns_none(self, tmp_path):
        # Pure ASCII filenames have no non-ASCII fallback — return None.
        audio = tmp_path / "track.mp3"
        audio.write_bytes(b"data")
        result = _resolve_audio_path(str(tmp_path), "track.mp3")
        assert result is None

    def test_non_ascii_fallback_finds_match(self, tmp_path):
        actual = tmp_path / "Artist - Traçk.mp3"
        actual.write_bytes(b"data")

        # Stored file_name has a non-ASCII byte at position 12; prefix "Artist - Tra"
        # matches the actual filename.
        stored_name = "Artist - Tra\x80k.mp3"
        result = _resolve_audio_path(str(tmp_path), stored_name)
        assert result == str(actual)

    def test_non_ascii_no_match_returns_none(self, tmp_path):
        stored_name = "XYZ\x80something.mp3"
        result = _resolve_audio_path(str(tmp_path), stored_name)
        assert result is None

    def test_non_ascii_in_subdirectory(self, tmp_path):
        subdir = tmp_path / "Albums"
        subdir.mkdir()
        audio = subdir / "Traçk.mp3"
        audio.write_bytes(b"data")

        stored_name = "Albums/Tra\x80k.mp3"
        result = _resolve_audio_path(str(tmp_path), stored_name)
        assert result == str(audio)

    def test_non_ascii_at_position_zero_returns_none(self, tmp_path):
        other = tmp_path / "SomeOtherFile.mp3"
        other.write_bytes(b"data")

        stored_name = "\x80track.mp3"
        result = _resolve_audio_path(str(tmp_path), stored_name)
        assert result is None

    # --- ? placeholder handling ---

    def test_question_mark_triggers_fallback(self, tmp_path):
        actual = tmp_path / "Artist - Trück.mp3"
        actual.write_bytes(b"data")

        stored_name = "Artist - Tr?ck.mp3"
        result = _resolve_audio_path(str(tmp_path), stored_name)
        assert result == str(actual)

    def test_question_mark_at_position_zero_returns_none(self, tmp_path):
        other = tmp_path / "SomeFile.mp3"
        other.write_bytes(b"data")

        stored_name = "?track.mp3"
        result = _resolve_audio_path(str(tmp_path), stored_name)
        assert result is None

    def test_question_mark_no_match_returns_none(self, tmp_path):
        stored_name = "NoMatch?file.mp3"
        result = _resolve_audio_path(str(tmp_path), stored_name)
        assert result is None

    def test_question_mark_before_non_ascii_uses_earlier_position(self, tmp_path):
        actual = tmp_path / "AB_rest.mp3"
        actual.write_bytes(b"data")

        stored_name = "AB?cd\x80ef.mp3"
        result = _resolve_audio_path(str(tmp_path), stored_name)
        assert result == str(actual)

    def test_non_ascii_before_question_mark_uses_earlier_position(self, tmp_path):
        actual = tmp_path / "AB_rest.mp3"
        actual.write_bytes(b"data")

        stored_name = "AB\x80cd?ef.mp3"
        result = _resolve_audio_path(str(tmp_path), stored_name)
        assert result == str(actual)
