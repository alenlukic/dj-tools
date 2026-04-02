"""Tests for assistant service warm-cache debounce logic.

Run with:
    python -m pytest src/tests/test_assistant_service.py -v
"""

from unittest.mock import MagicMock, patch

import pytest

from src.assistant.service import Assistant, _WARM_DEBOUNCE_SECONDS


def _make_track(track_id, title="Test Track"):
    row = MagicMock()
    row.id = track_id
    row.title = title
    return row


@pytest.fixture()
def assistant():
    with patch("src.assistant.service.database") as mock_db, \
         patch("src.assistant.service.CosineCache"), \
         patch("src.assistant.service.TransitionMatchFinder"):
        mock_session = MagicMock()
        mock_db.create_session.return_value = mock_session
        a = Assistant()
        yield a


class TestWarmCacheDebounce:
    """Verify per-track debounce gating in _warm_cache_async."""

    def test_first_call_launches_warm(self, assistant):
        track = _make_track(42)
        assistant.session.query.return_value.filter_by.return_value.first.return_value = track

        with patch("src.assistant.service.time") as mock_time, \
             patch("src.assistant.service.threading.Thread") as mock_thread_cls:
            mock_time.monotonic.return_value = 100.0
            assistant._warm_cache_async("Some Track")

            mock_thread_cls.assert_called_once()
            mock_thread_cls.return_value.start.assert_called_once()

    def test_same_track_within_window_is_suppressed(self, assistant):
        track = _make_track(42)
        assistant.session.query.return_value.filter_by.return_value.first.return_value = track

        with patch("src.assistant.service.time") as mock_time, \
             patch("src.assistant.service.threading.Thread") as mock_thread_cls:
            mock_time.monotonic.return_value = 100.0
            assistant._warm_cache_async("Some Track")
            assert mock_thread_cls.call_count == 1

            mock_time.monotonic.return_value = 105.0
            assistant._warm_cache_async("Some Track")
            assert mock_thread_cls.call_count == 1

    def test_different_track_not_suppressed(self, assistant):
        track_a = _make_track(42)
        track_b = _make_track(99)

        def lookup_track(**kwargs):
            filtered = MagicMock()
            if kwargs.get("title") == "Track A":
                filtered.first.return_value = track_a
            else:
                filtered.first.return_value = track_b
            return filtered

        assistant.session.query.return_value.filter_by.side_effect = lookup_track

        with patch("src.assistant.service.time") as mock_time, \
             patch("src.assistant.service.threading.Thread") as mock_thread_cls:
            mock_time.monotonic.return_value = 100.0
            assistant._warm_cache_async("Track A")
            assert mock_thread_cls.call_count == 1

            mock_time.monotonic.return_value = 101.0
            assistant._warm_cache_async("Track B")
            assert mock_thread_cls.call_count == 2

    def test_debounce_resets_after_window(self, assistant):
        track = _make_track(42)
        assistant.session.query.return_value.filter_by.return_value.first.return_value = track

        with patch("src.assistant.service.time") as mock_time, \
             patch("src.assistant.service.threading.Thread") as mock_thread_cls:
            mock_time.monotonic.return_value = 100.0
            assistant._warm_cache_async("Some Track")
            assert mock_thread_cls.call_count == 1

            mock_time.monotonic.return_value = 100.0 + _WARM_DEBOUNCE_SECONDS
            assistant._warm_cache_async("Some Track")
            assert mock_thread_cls.call_count == 2

    def test_unknown_track_skips_warm(self, assistant):
        assistant.session.query.return_value.filter_by.return_value.first.return_value = None

        with patch("src.assistant.service.threading.Thread") as mock_thread_cls:
            assistant._warm_cache_async("Nonexistent Track")
            mock_thread_cls.assert_not_called()


class TestWarmDebounceConstant:
    def test_constant_value(self):
        assert _WARM_DEBOUNCE_SECONDS == 10.0
