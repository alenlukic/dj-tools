"""Batch script: precompute cosine similarities for harmonic match candidates.

For each track, finds harmonic-match candidates via TransitionMatchFinder,
computes cosine similarity between compact descriptor vectors, and stores
one row per unordered pair (min_id, max_id). Already-computed pairs are
skipped, so the script is safe to re-run.

Usage:
    # Process all tracks that have current-version descriptors
    python -m src.scripts.feature_extraction.compute_cosine_similarities

    # Process specific track IDs
    python -m src.scripts.feature_extraction.compute_cosine_similarities 42 101 200

Environment:
    COSINE_WORKERS  Number of parallel worker processes (default: 2). Each
                    worker loads TransitionMatchFinder (tracks + camelot map)
                    but not ONNX models; memory is moderate.
"""

import os
import sys
import warnings

warnings.simplefilter("ignore")

from multiprocessing import Pipe, Process  # noqa: E402

from sqlalchemy import or_  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

from src.db import database  # noqa: E402
from src.models.track import Track  # noqa: E402
from src.models.track_descriptor import TrackDescriptor  # noqa: E402
from src.models.track_cosine_similarity import TrackCosineSimilarity  # noqa: E402
from src.feature_extraction.config import COSINE_WORKERS, DESCRIPTOR_VERSION  # noqa: E402
from src.feature_extraction.compact_descriptor import cosine_similarity, unpack_vector  # noqa: E402
from src.feature_extraction.track_similarity import ScorerName, compute_similarity  # noqa: E402
from src.harmonic_mixing.transition_match_finder import TransitionMatchFinder  # noqa: E402
from src.data_management.config import TrackDBCols  # noqa: E402
from src.errors import handle  # noqa: E402


_PROGRESS_INTERVAL = 10


def _chunkify(lst, n):
    """Split lst into n roughly equal non-empty chunks."""
    if not lst:
        return []
    n = min(n, len(lst))
    size, rem = divmod(len(lst), n)
    chunks, i = [], 0
    for k in range(n):
        extra = 1 if k < rem else 0
        chunks.append(lst[i : i + size + extra])
        i += size + extra
    return [c for c in chunks if c]


def _extract_candidate_ids(matches_result, source_track_id):
    """Extract unique candidate track IDs from TransitionMatchFinder results."""
    (same_key, higher_key, lower_key), _ = matches_result
    candidates = set()
    for match in same_key + higher_key + lower_key:
        cand_id = match.metadata.get(TrackDBCols.ID)
        if cand_id is not None and cand_id != source_track_id:
            candidates.add(cand_id)
    return candidates


def _ordered_pair(id_a, id_b):
    """Return (min, max) pair for canonical storage ordering."""
    return (min(id_a, id_b), max(id_a, id_b))


def _classify_existing_pairs(rows, descriptor_version):
    """Separate cosine rows into current-version (skip) and stale (update) sets.

    Returns (existing, stale) where each is a set of (id1, id2) tuples.
    """
    existing = set()
    stale = set()
    for row in rows:
        pair = (row.id1, row.id2)
        if row.descriptor_version == descriptor_version:
            existing.add(pair)
        else:
            stale.add(pair)
    return existing, stale


def _compute_cosine_batch(chunk, all_track_ids, result_transmitter, scorer_name=None):
    """Worker: compute cosine similarities for a chunk of track IDs.

    all_track_ids is the full set of IDs being processed across all workers.
    When a candidate is also in all_track_ids, only the source with the
    smaller ID inserts the pair — this eliminates cross-worker races on
    symmetric harmonic matches.
    """
    pid = os.getpid()
    n_saved = 0
    n_skipped = 0
    n_failed = 0
    print("  [%d] Initializing TransitionMatchFinder..." % pid, flush=True)
    worker_session = database.create_session()

    try:
        finder = TransitionMatchFinder(session=worker_session)
    except Exception as exc:
        handle(exc)
        result_transmitter.send((0, 0, len(chunk)))
        result_transmitter.close()
        return

    print("  [%d] Ready, processing %d tracks." % (pid, len(chunk)), flush=True)

    try:
        for idx, track_id in enumerate(chunk):
            try:
                track = worker_session.query(Track).filter_by(id=track_id).first()
                if track is None:
                    print(
                        "  [%d] track %d: not found in DB" % (pid, track_id),
                        flush=True,
                    )
                    n_failed += 1
                    continue

                source_desc = (
                    worker_session.query(TrackDescriptor)
                    .filter_by(track_id=track_id, descriptor_version=DESCRIPTOR_VERSION)
                    .first()
                )
                if source_desc is None:
                    print(
                        "  [%d] track %d: no descriptor (v%s)"
                        % (pid, track_id, DESCRIPTOR_VERSION),
                        flush=True,
                    )
                    n_skipped += 1
                    continue

                source_vec = unpack_vector(source_desc.global_vector)

                result = finder.get_transition_matches(track, sort_results=False)
                if result is None:
                    n_failed += 1
                    continue

                candidates = _extract_candidate_ids(result, track_id)
                if not candidates:
                    continue

                cosine_rows = (
                    worker_session.query(TrackCosineSimilarity)
                    .filter(
                        or_(
                            TrackCosineSimilarity.id1 == track_id,
                            TrackCosineSimilarity.id2 == track_id,
                        )
                    )
                    .all()
                )
                existing_pairs, stale_pair_keys = _classify_existing_pairs(
                    cosine_rows, DESCRIPTOR_VERSION
                )

                cand_descs = {
                    d.track_id: d
                    for d in worker_session.query(TrackDescriptor)
                    .filter(
                        TrackDescriptor.track_id.in_(list(candidates)),
                        TrackDescriptor.descriptor_version == DESCRIPTOR_VERSION,
                    )
                    .all()
                }

                track_saved = 0
                for cand_id in candidates:
                    try:
                        if cand_id in all_track_ids and cand_id < track_id:
                            n_skipped += 1
                            continue

                        id1, id2 = _ordered_pair(track_id, cand_id)

                        if (id1, id2) in existing_pairs:
                            n_skipped += 1
                            continue

                        cand_desc = cand_descs.get(cand_id)
                        if cand_desc is None:
                            continue

                        cand_vec = unpack_vector(cand_desc.global_vector)
                        if scorer_name is not None:
                            sim = compute_similarity(source_vec, cand_vec, scorer=scorer_name)
                        else:
                            sim = compute_similarity(source_vec, cand_vec)

                        if (id1, id2) in stale_pair_keys:
                            try:
                                worker_session.query(TrackCosineSimilarity).filter_by(
                                    id1=id1, id2=id2
                                ).update(
                                    {
                                        "cosine_similarity": sim,
                                        "descriptor_version": DESCRIPTOR_VERSION,
                                    }
                                )
                                worker_session.commit()
                                n_saved += 1
                                track_saved += 1
                                stale_pair_keys.discard((id1, id2))
                                existing_pairs.add((id1, id2))
                            except Exception as exc:
                                handle(exc)
                                worker_session.rollback()
                                n_failed += 1
                        else:
                            stmt = pg_insert(TrackCosineSimilarity).values(
                                id1=id1,
                                id2=id2,
                                cosine_similarity=sim,
                                descriptor_version=DESCRIPTOR_VERSION,
                            ).on_conflict_do_nothing(
                                index_elements=["id1", "id2"]
                            )
                            try:
                                result = worker_session.session.execute(stmt)
                                worker_session.commit()
                                if result.rowcount > 0:
                                    n_saved += 1
                                    track_saved += 1
                                else:
                                    n_skipped += 1
                                existing_pairs.add((id1, id2))
                            except Exception as exc:
                                handle(exc)
                                worker_session.rollback()
                                n_failed += 1

                    except Exception as exc:
                        handle(exc)
                        n_failed += 1

                print(
                    "  [%d] track %d: %d candidates, %d new"
                    % (pid, track_id, len(candidates), track_saved),
                    flush=True,
                )

            except Exception as exc:
                handle(exc)
                n_failed += 1

    finally:
        worker_session.close()

    print(
        "<<< Worker %d done: %d saved, %d skipped, %d failed >>>"
        % (pid, n_saved, n_skipped, n_failed),
        flush=True,
    )
    result_transmitter.send((n_saved, n_skipped, n_failed))
    result_transmitter.close()


def _get_tracks_for_processing(track_ids, session):
    """Determine which track IDs to process.

    When explicit IDs are provided, uses those directly. In batch mode,
    selects all tracks with current-version descriptors; per-pair
    deduplication in the worker handles already-computed pairs.
    """
    if track_ids:
        return sorted(track_ids)
    return sorted(
        r.track_id
        for r in session.query(TrackDescriptor)
        .filter_by(descriptor_version=DESCRIPTOR_VERSION)
        .all()
    )


def run(track_ids, session, scorer_name=None):
    try:
        tracks_to_process = _get_tracks_for_processing(track_ids, session)

        num_tracks = len(tracks_to_process)
        print("Computing cosine similarities for %d track(s)" % num_tracks)
        if num_tracks == 0:
            return

        n_workers = min(COSINE_WORKERS, num_tracks)
        print("Using %d worker(s) (COSINE_WORKERS=%d)\n" % (n_workers, COSINE_WORKERS))

        chunks = _chunkify(tracks_to_process, n_workers)
        all_track_ids = frozenset(tracks_to_process)

        workers = []
        aggregators = []

        for chunk in chunks:
            receiver, transmitter = Pipe(duplex=False)
            aggregators.append(receiver)
            worker = Process(
                target=_compute_cosine_batch,
                args=(chunk, all_track_ids, transmitter, scorer_name),
            )
            worker.daemon = True
            workers.append(worker)
            worker.start()
            transmitter.close()

        worker_results = [agg.recv() for agg in aggregators]

        for worker in workers:
            worker.join()

        for agg in aggregators:
            agg.close()

        total_saved = sum(n for n, _, _ in worker_results)
        total_skipped = sum(n for _, n, _ in worker_results)
        total_failed = sum(n for _, _, n in worker_results)

        print(
            "\nDone. %d saved, %d skipped, %d failed."
            % (total_saved, total_skipped, total_failed)
        )

    except Exception as exc:
        handle(exc)
        session.rollback()
    finally:
        session.close()


def _parse_args(argv):
    """Parse CLI arguments, separating track IDs from --scorer flag.

    Defaults to ``late_fusion_v1`` when no ``--scorer`` is given, matching
    the live transition-ranking path.
    """
    scorer = ScorerName.LATE_FUSION_V1
    track_ids = set()
    i = 1
    while i < len(argv):
        if argv[i] == "--scorer" and i + 1 < len(argv):
            scorer = ScorerName(argv[i + 1])
            i += 2
        else:
            track_ids.add(int(argv[i]))
            i += 1
    return track_ids, scorer


if __name__ == "__main__":
    _session = database.create_session()
    _track_ids, _scorer = _parse_args(sys.argv)
    run(_track_ids, _session, scorer_name=_scorer)
