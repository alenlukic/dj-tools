"""Benchmark track-similarity scorers on fixture or DB-loaded descriptors.

Runs all registered scorers through the BenchmarkHarness and writes a
JSON summary of distribution + hubness diagnostics.

Usage:
    # With synthetic fixture data (no DB required):
    python -m src.scripts.feature_extraction.benchmark_track_similarity --fixture

    # From database (requires DB connection):
    python -m src.scripts.feature_extraction.benchmark_track_similarity --limit 500

    # Write output to a specific directory:
    python -m src.scripts.feature_extraction.benchmark_track_similarity --fixture --output-dir .harness/runs/xxx
"""

import argparse
import json
import os
import sys

import numpy as np


def _generate_fixture_vectors(n: int = 50, dims: int = 75, seed: int = 42):
    """Generate synthetic descriptor vectors that mimic real distributions.

    Chroma values are non-negative (like real chroma), BPM is [0,1],
    tempogram sums to 1, and MFCC/energy blocks have mixed signs.
    """
    rng = np.random.default_rng(seed)
    vectors = []
    for _ in range(n):
        chroma_mean = rng.uniform(0.0, 1.0, 12).astype(np.float32)
        chroma_std = rng.uniform(0.0, 0.3, 12).astype(np.float32)
        bpm = np.array([rng.uniform(0.0, 1.0)], dtype=np.float32)
        tempogram = rng.dirichlet(np.ones(16)).astype(np.float32)
        mfcc_mean = rng.standard_normal(13).astype(np.float32) * 20
        mfcc_std = np.abs(rng.standard_normal(13).astype(np.float32)) * 10
        energy = np.abs(rng.standard_normal(8).astype(np.float32)) * 0.3
        vec = np.concatenate([
            chroma_mean, chroma_std, bpm, tempogram,
            mfcc_mean, mfcc_std, energy,
        ])
        vectors.append(vec)
    return vectors


def _load_db_vectors(limit: int):
    """Load descriptor vectors from the database."""
    from src.db import database
    from src.models.track_descriptor import TrackDescriptor
    from src.feature_extraction.config import DESCRIPTOR_VERSION
    from src.feature_extraction.compact_descriptor import unpack_vector

    session = database.create_session()
    try:
        query = (
            session.query(TrackDescriptor)
            .filter_by(descriptor_version=DESCRIPTOR_VERSION)
        )
        if limit > 0:
            query = query.limit(limit)
        rows = query.all()
        return [unpack_vector(r.global_vector) for r in rows if r.global_vector]
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Benchmark track-similarity scorers")
    parser.add_argument("--fixture", action="store_true", help="Use synthetic fixture data")
    parser.add_argument("--limit", type=int, default=200, help="Max DB vectors to load")
    parser.add_argument("--max-pairs", type=int, default=None, help="Cap on pairwise comparisons")
    parser.add_argument("--fixture-size", type=int, default=50, help="Number of fixture vectors")
    parser.add_argument(
        "--output-dir", type=str, default=".",
        help="Directory to write benchmark results",
    )
    args = parser.parse_args()

    from src.feature_extraction.track_similarity import BenchmarkHarness, list_scorers

    if args.fixture:
        print("Generating %d synthetic fixture vectors..." % args.fixture_size)
        vectors = _generate_fixture_vectors(n=args.fixture_size)
    else:
        print("Loading up to %d vectors from database..." % args.limit)
        vectors = _load_db_vectors(args.limit)

    if len(vectors) < 2:
        print("Need at least 2 vectors. Got %d." % len(vectors))
        sys.exit(1)

    print("Running benchmark with %d vectors..." % len(vectors))
    harness = BenchmarkHarness(vectors, max_pairs=args.max_pairs)
    results = harness.run_all()

    os.makedirs(args.output_dir, exist_ok=True)
    out_path = os.path.join(args.output_dir, "benchmark_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("Results written to %s" % out_path)

    for r in results:
        print("\n--- %s ---" % r["scorer"])
        print("  pairs: %d" % r["num_pairs"])
        print("  min=%.4f  max=%.4f  mean=%.4f  std=%.4f" % (
            r["min"], r["max"], r["mean"], r["std"],
        ))
        pcts = r["percentiles"]
        print("  p1=%.4f  p25=%.4f  p50=%.4f  p75=%.4f  p99=%.4f" % (
            pcts["1"], pcts["25"], pcts["50"], pcts["75"], pcts["99"],
        ))
        hub = r.get("hubness", {})
        if hub:
            print("  hubness: max_hub=%d  never_in_topk=%.2f%%  occ_std=%.2f" % (
                hub.get("max_hub_occurrence", 0),
                hub.get("fraction_never_in_topk", 0) * 100,
                hub.get("occurrence_std", 0),
            ))


if __name__ == "__main__":
    main()
