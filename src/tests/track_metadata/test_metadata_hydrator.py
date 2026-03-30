from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.track_metadata.matching import (
    _best_year,
    _extract_remixer,
    _merge_missing,
    _normalize_for_match,
    _parse_filename_seed,
    _similarity,
)
from src.track_metadata.models import SimpleMetadata
from src.track_metadata.sources import hydrator as hydrator_mod
from src.track_metadata.sources.discogs import (
    _coerce_year,
    _first_list_item,
    _first_non_empty,
    _split_discogs_title,
)
from src.track_metadata.sources.hydrator import MetadataHydrator
from src.track_metadata.sources.musicbrainz import (
    _extract_year_from_date,
    _first_release_id,
    _format_artist_credit,
    _musicbrainz_payload_to_metadata,
)

TEST_DATA_DIR = Path(__file__).resolve().parent / "test_data"


# ---------------------------------------------------------------------------
# _normalize_for_match
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Aphex Twin", "aphex twin"),
        ("Feat. Someone & Another", "someone and another"),
        ("Track (Extended Mix)", "track"),
        ("Track [Radio Edit]", "track"),
        ("  spaces  ", "spaces"),
        ("", ""),
        (None, ""),
        ("A&B feat. C (Remix)", "a and b c"),
    ],
)
def test_normalize_for_match(value: str | None, expected: str) -> None:
    assert _normalize_for_match(value) == expected


# ---------------------------------------------------------------------------
# _similarity
# ---------------------------------------------------------------------------


def test_similarity_identical() -> None:
    assert _similarity("Boards of Canada", "Boards of Canada") == pytest.approx(1.0)


def test_similarity_case_insensitive() -> None:
    assert _similarity("boards of canada", "BOARDS OF CANADA") == pytest.approx(1.0)


def test_similarity_empty_returns_zero() -> None:
    assert _similarity(None, "something") == pytest.approx(0.0)
    assert _similarity("something", None) == pytest.approx(0.0)
    assert _similarity(None, None) == pytest.approx(0.0)


def test_similarity_partial_match_between_zero_and_one() -> None:
    score = _similarity("Burial", "Actress")
    assert 0.0 < score < 1.0


# ---------------------------------------------------------------------------
# _extract_remixer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Track Title (Artist Name Remix)", "Artist Name"),
        ("Track Title [Artist Name Remix]", "Artist Name"),
        ("Track Title (REMIX)", None),  # no name before "remix"
        ("Plain Track Title", None),
        (None, None),
        ("", None),
        ("Track (DJ Sneak Remix)", "DJ Sneak"),
    ],
)
def test_extract_remixer(title: str | None, expected: str | None) -> None:
    assert _extract_remixer(title) == expected


# ---------------------------------------------------------------------------
# _parse_filename_seed
# ---------------------------------------------------------------------------


def test_parse_filename_seed_with_dash_separator() -> None:
    path = Path("Artist Name - Track Title.mp3")
    result = _parse_filename_seed(path)
    assert result.artist == "Artist Name"
    assert result.title == "Track Title"
    assert result.remixer is None


def test_parse_filename_seed_without_dash() -> None:
    path = Path("Some Track Title.mp3")
    result = _parse_filename_seed(path)
    assert result.artist is None
    assert result.title == "Some Track Title"


def test_parse_filename_seed_with_remix_in_title() -> None:
    path = Path("Artist - Title (DJ Someone Remix).mp3")
    result = _parse_filename_seed(path)
    assert result.artist == "Artist"
    assert result.title == "Title (DJ Someone Remix)"
    assert result.remixer == "DJ Someone"


def test_parse_filename_seed_underscores_become_spaces() -> None:
    path = Path("Artist_Name - Track_Title.mp3")
    result = _parse_filename_seed(path)
    assert result.artist == "Artist Name"
    assert result.title == "Track Title"


# ---------------------------------------------------------------------------
# _merge_missing
# ---------------------------------------------------------------------------


def test_merge_missing_fills_none_fields() -> None:
    target = SimpleMetadata(title="Existing Title", artist=None)
    candidate = SimpleMetadata(title="Candidate Title", artist="Candidate Artist", genre="Techno")
    merged = _merge_missing(target, candidate)
    assert merged.title == "Existing Title"  # not overwritten
    assert merged.artist == "Candidate Artist"  # filled from candidate
    assert merged.genre == "Techno"  # filled from candidate


def test_merge_missing_returns_target_if_candidate_is_none() -> None:
    target = SimpleMetadata(title="Title")
    result = _merge_missing(target, None)
    assert result.title == "Title"


def test_merge_missing_with_fields_filter() -> None:
    target = SimpleMetadata(title=None, artist=None, genre=None, label=None)
    candidate = SimpleMetadata(title="New Title", artist="New Artist", genre="House", label="Label")
    merged = _merge_missing(target, candidate, fields={"genre", "label"})
    assert merged.title is None  # filtered out
    assert merged.artist is None  # filtered out
    assert merged.genre == "House"
    assert merged.label == "Label"


# ---------------------------------------------------------------------------
# _best_year
# ---------------------------------------------------------------------------


def test_best_year_returns_first_truthy() -> None:
    assert _best_year(2020, 2021, 2022) == 2020


def test_best_year_skips_none() -> None:
    assert _best_year(None, None, 2018) == 2018


def test_best_year_all_none_returns_none() -> None:
    assert _best_year(None, None) is None


# ---------------------------------------------------------------------------
# _format_artist_credit
# ---------------------------------------------------------------------------


def test_format_artist_credit_simple_list() -> None:
    credit = [{"name": "Artist One", "joinphrase": " & "}, {"name": "Artist Two", "joinphrase": ""}]
    assert _format_artist_credit(credit) == "Artist One & Artist Two"


def test_format_artist_credit_string_items() -> None:
    credit = ["Artist One", " & ", "Artist Two"]
    assert _format_artist_credit(credit) == "Artist One & Artist Two"


def test_format_artist_credit_not_list_returns_none() -> None:
    assert _format_artist_credit("not a list") is None
    assert _format_artist_credit(None) is None


def test_format_artist_credit_empty_list_returns_none() -> None:
    assert _format_artist_credit([]) is None


# ---------------------------------------------------------------------------
# _first_release_id
# ---------------------------------------------------------------------------


def test_first_release_id_present() -> None:
    payload = {"releases": [{"id": "abc-123", "title": "Some Album"}]}
    assert _first_release_id(payload) == "abc-123"


def test_first_release_id_missing() -> None:
    assert _first_release_id({}) is None
    assert _first_release_id({"releases": []}) is None
    assert _first_release_id({"releases": [{"title": "No ID"}]}) is None


# ---------------------------------------------------------------------------
# _extract_year_from_date
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2021-05-01", 2021),
        ("1998", 1998),
        ("2000-01", 2000),
        ("no year here", None),
        (None, None),
        ("", None),
    ],
)
def test_extract_year_from_date(value: Any, expected: int | None) -> None:
    assert _extract_year_from_date(value) == expected


# ---------------------------------------------------------------------------
# _coerce_year
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (2021, 2021),
        ("2021", 2021),
        ("2021-01-01", 2021),
        (None, None),
        ("bad", None),
    ],
)
def test_coerce_year(value: Any, expected: int | None) -> None:
    assert _coerce_year(value) == expected


# ---------------------------------------------------------------------------
# _first_non_empty
# ---------------------------------------------------------------------------


def test_first_non_empty_returns_first_non_empty_string() -> None:
    assert _first_non_empty(None, "", "  ", "found") == "found"
    assert _first_non_empty(None, None) is None


def test_first_non_empty_strips_whitespace() -> None:
    assert _first_non_empty("  hello  ") == "hello"


# ---------------------------------------------------------------------------
# _first_list_item
# ---------------------------------------------------------------------------


def test_first_list_item_returns_first_string() -> None:
    assert _first_list_item(["Techno", "Electronic"]) == "Techno"


def test_first_list_item_skips_empty_strings() -> None:
    assert _first_list_item(["", "  ", "House"]) == "House"


def test_first_list_item_not_a_list_returns_none() -> None:
    assert _first_list_item("not a list") is None
    assert _first_list_item(None) is None


# ---------------------------------------------------------------------------
# _split_discogs_title
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected_artist", "expected_title"),
    [
        ("Artist - Album Title", "Artist", "Album Title"),
        ("Album Without Artist", None, "Album Without Artist"),
        ("", None, None),
        (None, None, None),
        (42, None, None),
    ],
)
def test_split_discogs_title(
    value: Any, expected_artist: str | None, expected_title: str | None
) -> None:
    artist, title = _split_discogs_title(value)
    assert artist == expected_artist
    assert title == expected_title


# ---------------------------------------------------------------------------
# _musicbrainz_payload_to_metadata
# ---------------------------------------------------------------------------


def test_musicbrainz_payload_to_metadata_with_release() -> None:
    recording = {
        "title": "My Track",
        "artist-credit": [{"name": "Great Artist", "joinphrase": ""}],
        "first-release-date": "2019-06-01",
        "genres": [],
    }
    release = {
        "title": "My Album",
        "date": "2019-06-01",
        "genres": [{"name": "Electronic"}],
        "label-info": [{"label": {"name": "Warp Records"}}],
    }
    result = _musicbrainz_payload_to_metadata(recording, release)
    assert result.title == "My Track"
    assert result.artist == "Great Artist"
    assert result.album == "My Album"
    assert result.label == "Warp Records"
    assert result.genre == "Electronic"
    assert result.year == 2019


def test_musicbrainz_payload_to_metadata_without_release() -> None:
    recording = {
        "title": "Solo Track",
        "artist-credit": [{"name": "Solo Artist", "joinphrase": ""}],
        "first-release-date": "2022",
        "genres": [{"name": "Ambient"}],
    }
    result = _musicbrainz_payload_to_metadata(recording, None)
    assert result.title == "Solo Track"
    assert result.artist == "Solo Artist"
    assert result.album is None
    assert result.label is None
    assert result.genre == "Ambient"
    assert result.year == 2022


# ---------------------------------------------------------------------------
# MetadataHydrator - cache
# ---------------------------------------------------------------------------


def test_hydrator_load_cache_returns_empty_dict_on_missing_file(tmp_path) -> None:
    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "nonexistent_cache.json"):
        hydrator = MetadataHydrator()
        assert hydrator.cache == {}


def test_hydrator_save_and_load_cache(tmp_path) -> None:
    cache_path = tmp_path / "cache.json"
    with patch.object(hydrator_mod, "CACHE_PATH", cache_path):
        hydrator = MetadataHydrator()
        hydrator.cache["key1"] = {"final": {"title": "Cached Track", "artist": "Artist"}}
        hydrator._save_cache()

        assert cache_path.exists()
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        assert raw["key1"]["final"]["title"] == "Cached Track"


def test_hydrator_file_cache_key_is_deterministic(tmp_path) -> None:
    test_file = tmp_path / "sample.mp3"
    test_file.write_bytes(b"fake audio data")

    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()
        key1 = hydrator._file_cache_key(test_file)
        key2 = hydrator._file_cache_key(test_file)
        assert key1 == key2
        assert len(key1) == 40  # sha1 hex


def test_hydrator_hydrate_uses_cache_hit(tmp_path) -> None:
    mp3 = tmp_path / "artist - track.mp3"
    shutil.copy2(TEST_DATA_DIR / "[01A - Abm - 086.00] Cell - Traffic (Live).mp3", mp3)

    cache_path = tmp_path / "cache.json"
    with patch.object(hydrator_mod, "CACHE_PATH", cache_path):
        hydrator = MetadataHydrator()
        cache_key = hydrator._file_cache_key(mp3)
        hydrator.cache[cache_key] = {"final": {"title": "Cached Title", "artist": "Cached Artist"}}

        result = hydrator.hydrate(mp3, SimpleMetadata())
        assert result.title == "Cached Title"
        assert result.artist == "Cached Artist"


# ---------------------------------------------------------------------------
# MetadataHydrator._lookup_acoustid
# ---------------------------------------------------------------------------


def test_lookup_acoustid_skips_without_api_key(tmp_path) -> None:
    mp3 = tmp_path / "track.mp3"
    mp3.write_bytes(b"fake")

    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

    with patch.dict("os.environ", {}, clear=True):
        # ACOUSTID_API_KEY not set
        result = hydrator._lookup_acoustid(mp3)
        assert result is None


def test_lookup_acoustid_skips_when_pyacoustid_not_installed(tmp_path, monkeypatch) -> None:
    mp3 = tmp_path / "track.mp3"
    mp3.write_bytes(b"fake")

    monkeypatch.setenv("ACOUSTID_API_KEY", "fakekey")

    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

    import sys

    # Temporarily make acoustid unimportable
    original = sys.modules.get("acoustid", "SENTINEL")
    sys.modules["acoustid"] = None  # type: ignore[assignment]
    try:
        result = hydrator._lookup_acoustid(mp3)
        assert result is None
    finally:
        if original == "SENTINEL":
            del sys.modules["acoustid"]
        else:
            sys.modules["acoustid"] = original


def test_lookup_acoustid_returns_none_on_low_confidence(tmp_path, monkeypatch) -> None:
    mp3 = tmp_path / "track.mp3"
    mp3.write_bytes(b"fake")

    monkeypatch.setenv("ACOUSTID_API_KEY", "fakekey")

    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

    mock_acoustid = MagicMock()
    mock_acoustid.match.return_value = [(0.50, "rec-id", "Title", "Artist")]

    with patch.dict("sys.modules", {"acoustid": mock_acoustid}):
        result = hydrator._lookup_acoustid(mp3)
        assert result is None


def test_lookup_acoustid_returns_metadata_on_high_confidence(tmp_path, monkeypatch) -> None:
    mp3 = tmp_path / "track.mp3"
    mp3.write_bytes(b"fake")

    monkeypatch.setenv("ACOUSTID_API_KEY", "fakekey")

    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

    mock_acoustid = MagicMock()
    mock_acoustid.match.return_value = [(0.95, "rec-abc", "Matched Title", "Matched Artist")]

    # Stub out the follow-up MB recording lookup to avoid HTTP
    with patch.object(hydrator, "_lookup_musicbrainz_recording", return_value=None), \
         patch.dict("sys.modules", {"acoustid": mock_acoustid}):
        result = hydrator._lookup_acoustid(mp3)

    assert result is not None
    assert result.title == "Matched Title"
    assert result.artist == "Matched Artist"


# ---------------------------------------------------------------------------
# MetadataHydrator._lookup_musicbrainz
# ---------------------------------------------------------------------------


def test_lookup_musicbrainz_returns_none_without_title(tmp_path, monkeypatch) -> None:
    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

    result = hydrator._lookup_musicbrainz(SimpleMetadata(), Path("no_title.mp3"))
    assert result is None


def test_lookup_musicbrainz_handles_http_error(tmp_path, monkeypatch) -> None:
    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

    hydrator.http.get = MagicMock(side_effect=requests.RequestException("timeout"))
    result = hydrator._lookup_musicbrainz(
        SimpleMetadata(title="Some Track", artist="Some Artist"), Path("track.mp3")
    )
    assert result is None


def test_lookup_musicbrainz_returns_none_when_no_recordings_match(tmp_path, monkeypatch) -> None:
    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

    mock_response = MagicMock()
    mock_response.json.return_value = {"recordings": []}
    mock_response.raise_for_status.return_value = None
    hydrator.http.get = MagicMock(return_value=mock_response)

    result = hydrator._lookup_musicbrainz(
        SimpleMetadata(title="Obscure Track"), Path("obscure.mp3")
    )
    assert result is None


def test_lookup_musicbrainz_returns_metadata_on_match(tmp_path, monkeypatch) -> None:
    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

    search_response = MagicMock()
    search_response.raise_for_status.return_value = None
    search_response.json.return_value = {
        "recordings": [
            {
                "id": "rec-xyz",
                "title": "Windowlicker",
                "artist-credit": [{"name": "Aphex Twin", "joinphrase": ""}],
                "releases": [{"title": "Windowlicker"}],
            }
        ]
    }

    recording_response = MagicMock()
    recording_response.raise_for_status.return_value = None
    recording_response.json.return_value = {
        "id": "rec-xyz",
        "title": "Windowlicker",
        "artist-credit": [{"name": "Aphex Twin", "joinphrase": ""}],
        "first-release-date": "1999",
        "genres": [{"name": "Electronic"}],
        "releases": [{"id": "rel-abc", "title": "Windowlicker"}],
    }

    release_response = MagicMock()
    release_response.raise_for_status.return_value = None
    release_response.json.return_value = {
        "title": "Windowlicker",
        "date": "1999-03-22",
        "genres": [{"name": "Electronic"}],
        "label-info": [{"label": {"name": "Warp Records"}}],
    }

    call_count = [0]

    def fake_get(url: str, **kwargs: Any) -> MagicMock:
        call_count[0] += 1
        if "/recording/rec-xyz" in url:
            return recording_response
        if "/release/rel-abc" in url:
            return release_response
        return search_response

    hydrator.http.get = fake_get  # type: ignore[method-assign]

    # Override rate limit to not sleep in tests
    with patch.object(hydrator, "_respect_rate_limit", return_value=None):
        result = hydrator._lookup_musicbrainz(
            SimpleMetadata(title="Windowlicker", artist="Aphex Twin"), Path("windowlicker.mp3")
        )

    assert result is not None
    assert result.title == "Windowlicker"
    assert result.artist == "Aphex Twin"
    assert result.label == "Warp Records"


# ---------------------------------------------------------------------------
# MetadataHydrator._select_best_musicbrainz_recording
# ---------------------------------------------------------------------------


def test_select_best_musicbrainz_recording_returns_none_below_threshold(tmp_path) -> None:
    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

    recordings = [
        {
            "id": "rec-1",
            "title": "Completely Different",
            "artist-credit": [{"name": "Another Artist", "joinphrase": ""}],
            "releases": [],
        }
    ]
    seed = SimpleMetadata(title="My Track", artist="My Artist")
    result = hydrator._select_best_musicbrainz_recording(recordings, seed)
    assert result is None


def test_select_best_musicbrainz_recording_returns_best_match(tmp_path) -> None:
    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

    recordings = [
        {
            "id": "rec-1",
            "title": "Windowlicker",
            "artist-credit": [{"name": "Aphex Twin", "joinphrase": ""}],
            "releases": [{"title": "Windowlicker"}],
        },
        {
            "id": "rec-2",
            "title": "Come to Daddy",
            "artist-credit": [{"name": "Aphex Twin", "joinphrase": ""}],
            "releases": [{"title": "Come to Daddy"}],
        },
    ]
    seed = SimpleMetadata(title="Windowlicker", artist="Aphex Twin")
    result = hydrator._select_best_musicbrainz_recording(recordings, seed)
    assert result is not None
    assert result["id"] == "rec-1"


# ---------------------------------------------------------------------------
# MetadataHydrator._lookup_discogs
# ---------------------------------------------------------------------------


def test_lookup_discogs_returns_none_without_token(tmp_path) -> None:
    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

    env_without_token = {
        k: v for k, v in __import__("os").environ.items() if k != "DISCOGS_TOKEN"
    }
    with patch.dict("os.environ", env_without_token, clear=True):
        result = hydrator._lookup_discogs(SimpleMetadata(title="Track"))
        assert result is None


def test_lookup_discogs_returns_none_without_title(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DISCOGS_TOKEN", "faketoken")

    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

    result = hydrator._lookup_discogs(SimpleMetadata(artist="Artist"))
    assert result is None


def test_lookup_discogs_returns_metadata_on_match(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DISCOGS_TOKEN", "faketoken")

    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "results": [
            {
                "title": "Aphex Twin - Selected Ambient Works",
                "year": 1992,
                "genre": ["Electronic"],
                "label": ["R&S Records"],
            }
        ]
    }
    hydrator.http.get = MagicMock(return_value=mock_response)

    with patch.object(hydrator, "_respect_rate_limit", return_value=None):
        result = hydrator._lookup_discogs(
            SimpleMetadata(title="Selected Ambient Works", artist="Aphex Twin")
        )

    assert result is not None
    assert result.year == 1992
    assert result.genre == "Electronic"
    assert result.label == "R&S Records"


def test_lookup_discogs_returns_none_below_threshold(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DISCOGS_TOKEN", "faketoken")

    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "results": [
            {
                "title": "Completely Unrelated - Release Name",
                "year": 2005,
                "genre": ["Pop"],
                "label": ["Some Label"],
            }
        ]
    }
    hydrator.http.get = MagicMock(return_value=mock_response)

    with patch.object(hydrator, "_respect_rate_limit", return_value=None):
        result = hydrator._lookup_discogs(
            SimpleMetadata(title="Very Different Track", artist="Unknown Artist")
        )

    assert result is None


# ---------------------------------------------------------------------------
# MetadataHydrator._resolve_from_candidates
# ---------------------------------------------------------------------------


def test_resolve_from_candidates_returns_none_without_openai_client(tmp_path) -> None:
    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()
    hydrator.openai_client = None

    result = hydrator._resolve_from_candidates(
        Path("track.mp3"),
        SimpleMetadata(title="Track", artist="Artist"),
        [{"source": "musicbrainz", "metadata": {"title": "Track"}}],
    )
    assert result is None


def test_resolve_from_candidates_returns_none_when_no_missing_fields(tmp_path) -> None:
    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()
    hydrator.openai_client = MagicMock()

    full_metadata = SimpleMetadata(
        title="Title",
        artist="Artist",
        album="Album",
        label="Label",
        genre="Genre",
        remixer="Remixer",
        year=2020,
    )
    result = hydrator._resolve_from_candidates(
        Path("track.mp3"),
        full_metadata,
        [{"source": "musicbrainz", "metadata": {}}],
    )
    assert result is None


def test_resolve_from_candidates_returns_none_when_no_sources(tmp_path) -> None:
    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()
    hydrator.openai_client = MagicMock()

    result = hydrator._resolve_from_candidates(
        Path("track.mp3"),
        SimpleMetadata(title=None),
        [],  # no sources
    )
    assert result is None


# ---------------------------------------------------------------------------
# MetadataHydrator._respect_rate_limit
# ---------------------------------------------------------------------------


def test_respect_rate_limit_sleeps_when_needed(tmp_path) -> None:
    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

    # Force the last request timestamp to be "just now" so rate limit kicks in
    hydrator_mod._last_musicbrainz_request_ts = time.monotonic()

    with patch("time.sleep") as mock_sleep:
        hydrator._respect_rate_limit("musicbrainz")
        assert mock_sleep.called
        delay = mock_sleep.call_args[0][0]
        assert delay > 0


def test_respect_rate_limit_no_sleep_when_enough_time_passed(tmp_path) -> None:
    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

    # Simulate enough time having elapsed
    hydrator_mod._last_musicbrainz_request_ts = time.monotonic() - 10.0

    with patch("time.sleep") as mock_sleep:
        hydrator._respect_rate_limit("musicbrainz")
        mock_sleep.assert_not_called()


def test_respect_rate_limit_unknown_provider_is_noop(tmp_path) -> None:
    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

    with patch("time.sleep") as mock_sleep:
        hydrator._respect_rate_limit("unknown_provider")
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# MetadataHydrator.hydrate - integration (no real network)
# ---------------------------------------------------------------------------


def test_hydrate_uses_filename_seed_when_no_existing_metadata(tmp_path) -> None:
    mp3 = tmp_path / "Great Artist - Great Track.mp3"
    shutil.copy2(TEST_DATA_DIR / "[01A - Abm - 086.00] Cell - Traffic (Live).mp3", mp3)

    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

        # Stub out all remote lookups
        with patch.object(hydrator, "_lookup_acoustid", return_value=None), \
             patch.object(hydrator, "_lookup_musicbrainz", return_value=None), \
             patch.object(hydrator, "_lookup_discogs", return_value=None), \
             patch.object(hydrator, "_resolve_from_candidates", return_value=None):
            result = hydrator.hydrate(mp3, SimpleMetadata())

    assert result.artist == "Great Artist"
    assert result.title == "Great Track"


def test_hydrate_does_not_overwrite_existing_metadata(tmp_path) -> None:
    mp3 = tmp_path / "SomeFile.mp3"
    shutil.copy2(TEST_DATA_DIR / "[01A - Abm - 086.00] Cell - Traffic (Live).mp3", mp3)

    existing = SimpleMetadata(title="Existing Title", artist="Existing Artist", bpm=128.0)

    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

        candidate = SimpleMetadata(
            title="Candidate Title", artist="Candidate Artist", genre="Techno"
        )
        with patch.object(hydrator, "_lookup_acoustid", return_value=None), \
             patch.object(hydrator, "_lookup_musicbrainz", return_value=candidate), \
             patch.object(hydrator, "_lookup_discogs", return_value=None), \
             patch.object(hydrator, "_resolve_from_candidates", return_value=None):
            result = hydrator.hydrate(mp3, existing)

    # Existing data preserved
    assert result.title == "Existing Title"
    assert result.artist == "Existing Artist"
    assert result.bpm == 128.0
    # Missing genre filled from candidate
    assert result.genre == "Techno"


def test_hydrate_writes_and_reads_cache(tmp_path) -> None:
    mp3 = tmp_path / "Track.mp3"
    shutil.copy2(TEST_DATA_DIR / "[01A - Abm - 086.00] Cell - Traffic (Live).mp3", mp3)

    cache_path = tmp_path / "cache.json"

    with patch.object(hydrator_mod, "CACHE_PATH", cache_path):
        hydrator = MetadataHydrator()

        with patch.object(hydrator, "_lookup_acoustid", return_value=None), \
             patch.object(hydrator, "_lookup_musicbrainz", return_value=None), \
             patch.object(hydrator, "_lookup_discogs", return_value=None), \
             patch.object(hydrator, "_resolve_from_candidates", return_value=None):
            result1 = hydrator.hydrate(mp3, SimpleMetadata(title="Cached Track", artist="Artist"))

        # Second hydrate should hit cache (no lookup calls)
        _not_called = AssertionError("Should not be called")
        with patch.object(hydrator, "_lookup_acoustid", side_effect=_not_called):
            with patch.object(hydrator, "_lookup_musicbrainz", side_effect=_not_called):
                result2 = hydrator.hydrate(mp3, SimpleMetadata())

    assert result1.title == result2.title
    assert result1.artist == result2.artist


def test_hydrate_applies_label_fallback(tmp_path) -> None:
    mp3 = tmp_path / "Track.mp3"
    shutil.copy2(TEST_DATA_DIR / "[01A - Abm - 086.00] Cell - Traffic (Live).mp3", mp3)

    with patch.object(hydrator_mod, "CACHE_PATH", tmp_path / "cache.json"):
        hydrator = MetadataHydrator()

        existing = SimpleMetadata(title="Track", artist="Artist", label="White Label")

        with patch.object(hydrator, "_lookup_acoustid", return_value=None), \
             patch.object(hydrator, "_lookup_musicbrainz", return_value=None), \
             patch.object(hydrator, "_lookup_discogs", return_value=None), \
             patch.object(hydrator, "_resolve_from_candidates", return_value=None):
            result = hydrator.hydrate(mp3, existing)

    assert result.label == "CDR"
