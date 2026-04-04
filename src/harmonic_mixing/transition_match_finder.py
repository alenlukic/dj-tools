import logging

from src.db import database
from src.models.track import Track
from src.assistant.config import DASHED_LINE
from src.data_management.config import TrackDBCols
from src.data_management.mapping_registry import MappingRegistry
from src.harmonic_mixing.config import (
    CamelotPriority,
    DOWN_KEY_LOWER_BOUND,
    DOWN_KEY_UPPER_BOUND,
    SAME_LOWER_BOUND,
    SAME_UPPER_BOUND,
    UP_KEY_LOWER_BOUND,
    UP_KEY_UPPER_BOUND,
)
from src.data_management.service import load_tracks
from src.harmonic_mixing.transition_match import TransitionMatch
from src.errors import handle
from src.utils.common import get_config_value
from src.harmonic_mixing.utils import (
    flip_camelot_letter,
    format_camelot_number,
    generate_camelot_map,
    get_bpm_bound,
)

logger = logging.getLogger(__name__)


class TransitionMatchFinder:
    """Encapsulates functionality for finding transition matches."""

    def __init__(self, session=None, cosine_cache=None):
        self.session = session if session is not None else database.create_session()
        self.cosine_cache = cosine_cache
        MappingRegistry.load(self.session)
        self.tracks = load_tracks(self.session)
        self.camelot_map, self.collection_metadata = generate_camelot_map(self.tracks)
        self.max_results = get_config_value(["HARMONIC_MIXING", "MAX_RESULTS"])
        self.cutoff_threshold_score = get_config_value(
            ["HARMONIC_MIXING", "SCORE_THRESHOLD"]
        )
        self.result_threshold = get_config_value(
            ["HARMONIC_MIXING", "RESULT_THRESHOLD"]
        )

        TransitionMatch.db_session = self.session
        TransitionMatch.collection_metadata = self.collection_metadata
        TransitionMatch.cosine_cache = self.cosine_cache
        self._sync_effective_weights()

    def reload_track_data(self):
        MappingRegistry.load(self.session)
        self.tracks = load_tracks(self.session)
        self.camelot_map, self.collection_metadata = generate_camelot_map(self.tracks)
        TransitionMatch.collection_metadata = self.collection_metadata
        TransitionMatch.clear_descriptor_caches()
        self._sync_effective_weights()

    @staticmethod
    def _sync_effective_weights():
        try:
            from src.harmonic_mixing.weight_service import WeightService
            TransitionMatch.effective_weights = (
                WeightService.instance().get_effective_weights_for_scoring()
            )
        except Exception:
            logger.warning("Failed to sync effective weights from WeightService", exc_info=True)

    def get_transition_matches(self, track, sort_results=True):
        TransitionMatch.clear_descriptor_caches()
        try:
            db_row = (
                track
                if isinstance(track, Track)
                else self.session.query(Track).filter_by(title=track).first()
            )
            title_mismatch_message = ""

            if db_row is None:
                db_row = (
                    self.session.query(Track)
                    .filter(Track.file_name.like("%{}%".format(track)))
                    .first()
                )

                if db_row is not None:
                    file_name = db_row.file_name
                    title_mismatch_message = (
                        "\n\nWarning: found %s in file name %s (but not title)"
                        % (track, file_name)
                    )
                else:
                    raise Exception("%s not found in database." % track)

            # Validate BPM and Camelot code exist and are well-formatted
            title = db_row.title
            bpm = float(db_row.bpm)
            camelot_code = db_row.camelot_code
            if bpm is None:
                raise Exception("Did not find a BPM for %s." % title)
            if camelot_code is None:
                raise Exception("Did not find a Camelot code for %s." % title)

            camelot_map_entry = self.camelot_map[camelot_code][bpm]
            cur_track_md = [
                md for md in camelot_map_entry if md.get(TrackDBCols.TITLE) == title
            ]
            if len(cur_track_md) == 0:
                raise Exception("%s metadata not found in Camelot map." % title)

            cur_track_md = cur_track_md[0]

            # Generate and rank matches
            harmonic_codes = TransitionMatchFinder._get_all_harmonic_codes(cur_track_md)
            same_key, higher_key, lower_key = self._get_matches_for_code(
                harmonic_codes, cur_track_md, sort_results
            )

            return (same_key, higher_key, lower_key), title_mismatch_message

        except Exception as e:
            handle(e)

    def print_transition_matches(self, track):
        (same_key, higher_key, lower_key), title_mismatch_message = (
            self.get_transition_matches(track)
        )

        self._print_transition_ranks("Higher key (step down)", higher_key)
        self._print_transition_ranks("Lower key (step up)", lower_key)
        self._print_transition_ranks("Same key", same_key, 1)
        print(title_mismatch_message)

    @staticmethod
    def _get_all_harmonic_codes(cur_track_md):
        camelot_code = cur_track_md[TrackDBCols.CAMELOT_CODE]
        code_number = int(camelot_code[0:2])
        code_letter = camelot_code[-1].upper()

        return [
            # Same key
            (code_number, code_letter, CamelotPriority.SAME_KEY.value),
            # One key jump
            ((code_number + 1) % 12, code_letter, CamelotPriority.ONE_KEY_JUMP.value),
            # Two key jump
            (
                (code_number + 2) % 12,
                code_letter,
                CamelotPriority.TWO_OCTAVE_JUMP.value,
            ),
            # One octave jump
            (
                (code_number + 7) % 12,
                code_letter,
                CamelotPriority.ONE_OCTAVE_JUMP.value,
            ),
            # Major/minor jump
            (
                (code_number + (3 if code_letter == "A" else -3)) % 12,
                flip_camelot_letter(code_letter),
                CamelotPriority.MAJOR_MINOR_JUMP.value,
            ),
            # Adjacent key jumps
            (
                (code_number + (1 if code_letter == "B" else -1)) % 12,
                flip_camelot_letter(code_letter),
                CamelotPriority.ADJACENT_JUMP.value,
            ),
            (
                code_number,
                flip_camelot_letter(code_letter),
                CamelotPriority.ADJACENT_JUMP.value,
            ),
        ]

    def _get_matches(self, bpm, camelot_code, upper_bound, lower_bound):
        upper_bpm = get_bpm_bound(bpm, lower_bound)
        lower_bpm = get_bpm_bound(bpm, upper_bound)

        results = []
        code_map = self.camelot_map[camelot_code]
        matching_bpms = sorted(
            [b for b in code_map.keys() if lower_bpm <= b <= upper_bpm]
        )
        for b in matching_bpms:
            results.extend(code_map[b])

        return results

    def _get_matches_for_code(self, harmonic_codes, cur_track_md, sort_results):
        bpm = cur_track_md[TrackDBCols.BPM]
        source_id = cur_track_md.get(TrackDBCols.ID)
        same_key = []
        higher_key = []
        lower_key = []

        for code_number, code_letter, priority in harmonic_codes:
            camelot_code = format_camelot_number(code_number) + code_letter
            hk_code = format_camelot_number((code_number + 7) % 12) + code_letter
            lk_code = format_camelot_number((code_number - 7) % 12) + code_letter

            for md in self._get_matches(
                bpm, camelot_code, SAME_UPPER_BOUND, SAME_LOWER_BOUND
            ):
                if source_id is not None and md.get(TrackDBCols.ID) == source_id:
                    continue
                match = TransitionMatch(md, cur_track_md, priority)
                same_key.append(match)

            for md in self._get_matches(
                bpm, hk_code, DOWN_KEY_UPPER_BOUND, DOWN_KEY_LOWER_BOUND
            ):
                if source_id is not None and md.get(TrackDBCols.ID) == source_id:
                    continue
                match = TransitionMatch(md, cur_track_md, priority)
                higher_key.append(match)

            for md in self._get_matches(
                bpm, lk_code, UP_KEY_UPPER_BOUND, UP_KEY_LOWER_BOUND
            ):
                if source_id is not None and md.get(TrackDBCols.ID) == source_id:
                    continue
                match = TransitionMatch(md, cur_track_md, priority)
                lower_key.append(match)

        if sort_results:
            same_key = sorted(same_key, reverse=True)
            higher_key = sorted(higher_key, reverse=True)
            lower_key = sorted(lower_key, reverse=True)

        return same_key, higher_key, lower_key

    def _print_transition_ranks(self, result_type, results, start_index=0):
        print("\n\n\n%s results:\n\n\n" % result_type)
        print(DASHED_LINE)
        print(TransitionMatch.result_column_header)
        print(DASHED_LINE)

        num_results = len(results)
        if num_results == 0:
            return

        for i, result in enumerate(results[start_index:]):
            if i == self.max_results:
                break

            if (
                num_results >= self.result_threshold
                and result.get_score() < self.cutoff_threshold_score
            ):
                break

            print(result.format())
            if (i + 1) % 5 == 0:
                print()
