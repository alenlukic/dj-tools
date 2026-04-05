"""Track similarity scoring: scorer registry, block extraction, and benchmark harness.

Provides multiple scoring strategies over the 75-D compact descriptor vectors,
from a simple flat cosine baseline through a structured late-fusion scorer that
compares descriptor blocks (harmonic, rhythm, timbre, energy) separately.

Descriptor layout (75 dims):
    [0:12]   chroma mean        (harmonic)
    [12:24]  chroma std         (harmonic)
    [24]     normalized BPM     (rhythm)
    [25:41]  tempogram hist     (rhythm, 16 bins)
    [41:54]  MFCC mean          (timbre, 13 dims)
    [54:67]  MFCC std           (timbre, 13 dims)
    [67:69]  RMS mean/std       (energy)
    [69:71]  centroid mean/std  (energy/brightness)
    [71:73]  rolloff mean/std   (energy/brightness)
    [73:75]  ZCR mean/std       (energy)
"""

from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Descriptor block slicing
# ---------------------------------------------------------------------------

CHROMA_MEAN = slice(0, 12)
CHROMA_STD = slice(12, 24)
BPM_IDX = 24
TEMPOGRAM = slice(25, 41)
MFCC_MEAN = slice(41, 54)
MFCC_STD = slice(54, 67)
ENERGY_BRIGHTNESS = slice(67, 75)

_EPS = 1e-10


def extract_blocks(vec: np.ndarray) -> Dict[str, np.ndarray]:
    """Extract named descriptor blocks from a 75-D vector."""
    return {
        "chroma_mean": vec[CHROMA_MEAN],
        "chroma_std": vec[CHROMA_STD],
        "bpm": vec[BPM_IDX: BPM_IDX + 1],
        "tempogram": vec[TEMPOGRAM],
        "mfcc_mean": vec[MFCC_MEAN],
        "mfcc_std": vec[MFCC_STD],
        "energy_brightness": vec[ENERGY_BRIGHTNESS],
    }


# ---------------------------------------------------------------------------
# Scorer name enum and registry
# ---------------------------------------------------------------------------

class ScorerName(str, Enum):
    CURRENT_COSINE_CLAMPED = "current_cosine_clamped"
    RAW_COSINE_UNCAPPED = "raw_cosine_uncapped"
    COSINE_AFTER_GLOBAL_ZSCORE = "cosine_after_global_zscore"
    CORRELATION_OR_CENTERED_COSINE = "correlation_or_centered_cosine"
    STANDARDIZED_EUCLIDEAN = "standardized_euclidean"
    LATE_FUSION_V1 = "late_fusion_v1"


_SCORER_REGISTRY: Dict[ScorerName, Callable] = {}


def _register(name: ScorerName):
    def decorator(fn):
        _SCORER_REGISTRY[name] = fn
        return fn
    return decorator


def get_scorer(name: ScorerName) -> Callable:
    """Return the scorer function for *name*."""
    return _SCORER_REGISTRY[name]


def list_scorers() -> List[ScorerName]:
    return list(_SCORER_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

def _safe_cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity, returning 0.0 for zero-norm vectors."""
    n1 = np.linalg.norm(a)
    n2 = np.linalg.norm(b)
    if n1 < _EPS or n2 < _EPS:
        return 0.0
    return float(np.dot(a, b) / (n1 * n2))


def _centered_cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity after centering both vectors (= Pearson correlation)."""
    ac = a - a.mean()
    bc = b - b.mean()
    return _safe_cosine(ac, bc)


def _zscore_vectors(
    a: np.ndarray,
    b: np.ndarray,
    corpus_mean: Optional[np.ndarray] = None,
    corpus_std: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Z-score both vectors. Falls back to per-pair stats if no corpus stats."""
    if corpus_mean is not None and corpus_std is not None:
        mu = corpus_mean
        sigma = corpus_std
    else:
        stacked = np.vstack([a, b])
        mu = stacked.mean(axis=0)
        sigma = stacked.std(axis=0)
    safe_sigma = np.where(sigma < _EPS, 1.0, sigma)
    return (a - mu) / safe_sigma, (b - mu) / safe_sigma


def _standardized_euclidean_distance(
    a: np.ndarray,
    b: np.ndarray,
    variance: Optional[np.ndarray] = None,
) -> float:
    """Variance-weighted Euclidean distance, safe for zero-variance dims."""
    diff = a - b
    if variance is not None:
        safe_var = np.where(variance < _EPS, 1.0, variance)
        return float(np.sqrt(np.sum(diff ** 2 / safe_var)))
    return float(np.linalg.norm(diff))


def _dist_to_sim(distance: float, tau: float = 1.0) -> float:
    """Convert a non-negative distance to [0, 1] similarity via exp kernel."""
    if not np.isfinite(distance):
        return 0.0
    return float(np.exp(-distance / max(tau, _EPS)))


# ---------------------------------------------------------------------------
# Baseline scorers
# ---------------------------------------------------------------------------

@_register(ScorerName.CURRENT_COSINE_CLAMPED)
def current_cosine_clamped(vec_a: np.ndarray, vec_b: np.ndarray, **kw) -> float:
    """Exact reproduction of the original cosine_similarity(): clamp to [0, 1]."""
    raw = _safe_cosine(vec_a, vec_b)
    return max(0.0, raw)


@_register(ScorerName.RAW_COSINE_UNCAPPED)
def raw_cosine_uncapped(vec_a: np.ndarray, vec_b: np.ndarray, **kw) -> float:
    """Same as current but without clamping; returns [-1, 1]."""
    return _safe_cosine(vec_a, vec_b)


@_register(ScorerName.COSINE_AFTER_GLOBAL_ZSCORE)
def cosine_after_global_zscore(vec_a: np.ndarray, vec_b: np.ndarray, **kw) -> float:
    """Z-score each dim (using corpus stats if available), then cosine."""
    corpus_mean = kw.get("corpus_mean")
    corpus_std = kw.get("corpus_std")
    za, zb = _zscore_vectors(vec_a, vec_b, corpus_mean, corpus_std)
    return _safe_cosine(za, zb)


@_register(ScorerName.CORRELATION_OR_CENTERED_COSINE)
def correlation_or_centered_cosine(vec_a: np.ndarray, vec_b: np.ndarray, **kw) -> float:
    """Subtract per-sample mean then cosine (= Pearson correlation)."""
    return _centered_cosine(vec_a, vec_b)


@_register(ScorerName.STANDARDIZED_EUCLIDEAN)
def standardized_euclidean(vec_a: np.ndarray, vec_b: np.ndarray, **kw) -> float:
    """Per-dim variance-aware Euclidean distance, converted to similarity."""
    variance = kw.get("corpus_variance")
    tau = kw.get("euclidean_tau", 3.0)
    d = _standardized_euclidean_distance(vec_a, vec_b, variance)
    return _dist_to_sim(d, tau)


# ---------------------------------------------------------------------------
# Late fusion v1: block-wise scoring with configurable weights
# ---------------------------------------------------------------------------

# Fusion weights — configurable constants
FUSION_WEIGHT_HARMONIC = 0.30
FUSION_WEIGHT_RHYTHM = 0.25
FUSION_WEIGHT_TIMBRE = 0.30
FUSION_WEIGHT_ENERGY = 0.15

# Harmonic: mean/std blend ratio
HARMONIC_MEAN_WEIGHT = 0.8
HARMONIC_STD_WEIGHT = 0.2

# Rhythm: BPM/tempogram blend ratio
RHYTHM_BPM_WEIGHT = 0.4
RHYTHM_TEMPOGRAM_WEIGHT = 0.6

# Tau defaults for exponential distance→similarity kernels
TIMBRE_TAU = 3.0
ENERGY_TAU = 2.0


def _best_circular_shift_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Centered cosine under all 12 circular shifts, return best."""
    if len(a) != 12 or len(b) != 12:
        return _centered_cosine(a, b)
    best = -2.0
    for shift in range(12):
        shifted = np.roll(b, shift)
        sim = _centered_cosine(a, shifted)
        if sim > best:
            best = sim
    return best


def _harmonic_similarity(blocks_a: dict, blocks_b: dict) -> float:
    """Transposition-aware harmonic similarity using chroma mean + std."""
    mean_sim = _best_circular_shift_sim(
        blocks_a["chroma_mean"], blocks_b["chroma_mean"]
    )
    std_sim = _best_circular_shift_sim(
        blocks_a["chroma_std"], blocks_b["chroma_std"]
    )
    return HARMONIC_MEAN_WEIGHT * mean_sim + HARMONIC_STD_WEIGHT * std_sim


def _bpm_similarity(bpm_a: float, bpm_b: float) -> float:
    """BPM compatibility via log-ratio kernel."""
    if bpm_a < _EPS and bpm_b < _EPS:
        return 1.0
    penalty = abs(np.log2((bpm_a + _EPS) / (bpm_b + _EPS)))
    return float(np.exp(-penalty / 0.15))


def _tempogram_similarity(hist_a: np.ndarray, hist_b: np.ndarray) -> float:
    """Jensen-Shannon divergence on normalized histograms, mapped to similarity."""
    sa = hist_a.sum()
    sb = hist_b.sum()
    if sa < _EPS and sb < _EPS:
        return 1.0
    pa = hist_a / max(sa, _EPS)
    pb = hist_b / max(sb, _EPS)
    m = 0.5 * (pa + pb)
    safe_m = np.where(m < _EPS, 1.0, m)
    with np.errstate(divide="ignore", invalid="ignore"):
        log_a_m = np.log(pa / safe_m)
        log_b_m = np.log(pb / safe_m)
    kl_a = np.where(pa > _EPS, pa * np.where(np.isfinite(log_a_m), log_a_m, 0.0), 0.0)
    kl_b = np.where(pb > _EPS, pb * np.where(np.isfinite(log_b_m), log_b_m, 0.0), 0.0)
    jsd = 0.5 * (kl_a.sum() + kl_b.sum())
    jsd = float(np.clip(jsd, 0.0, np.log(2)))
    return 1.0 - jsd / np.log(2)


def _rhythm_similarity(blocks_a: dict, blocks_b: dict) -> float:
    """BPM + tempogram fusion."""
    bpm_sim = _bpm_similarity(float(blocks_a["bpm"][0]), float(blocks_b["bpm"][0]))
    tempo_sim = _tempogram_similarity(blocks_a["tempogram"], blocks_b["tempogram"])
    return RHYTHM_BPM_WEIGHT * bpm_sim + RHYTHM_TEMPOGRAM_WEIGHT * tempo_sim


def _timbre_similarity(blocks_a: dict, blocks_b: dict, **kw) -> float:
    """Standardized Euclidean over MFCC mean + std, converted to similarity."""
    a = np.concatenate([blocks_a["mfcc_mean"], blocks_a["mfcc_std"]])
    b = np.concatenate([blocks_b["mfcc_mean"], blocks_b["mfcc_std"]])
    variance = kw.get("timbre_variance")
    tau = kw.get("timbre_tau", TIMBRE_TAU)
    d = _standardized_euclidean_distance(a, b, variance)
    return _dist_to_sim(d, tau)


def _energy_similarity(blocks_a: dict, blocks_b: dict, **kw) -> float:
    """Standardized Euclidean over energy/brightness block, converted to similarity."""
    a = blocks_a["energy_brightness"]
    b = blocks_b["energy_brightness"]
    variance = kw.get("energy_variance")
    tau = kw.get("energy_tau", ENERGY_TAU)
    d = _standardized_euclidean_distance(a, b, variance)
    return _dist_to_sim(d, tau)


def _get_live_fusion_weights():
    """Read fusion weights from WeightService if available; fall back to constants."""
    try:
        from src.harmonic_mixing.weight_service import WeightService
        fw = WeightService.instance().get_fusion_weights()
        return (
            fw.get('FUSION_HARMONIC', FUSION_WEIGHT_HARMONIC),
            fw.get('FUSION_RHYTHM', FUSION_WEIGHT_RHYTHM),
            fw.get('FUSION_TIMBRE', FUSION_WEIGHT_TIMBRE),
            fw.get('FUSION_ENERGY', FUSION_WEIGHT_ENERGY),
        )
    except Exception:
        return (FUSION_WEIGHT_HARMONIC, FUSION_WEIGHT_RHYTHM, FUSION_WEIGHT_TIMBRE, FUSION_WEIGHT_ENERGY)


@_register(ScorerName.LATE_FUSION_V1)
def late_fusion_v1(vec_a: np.ndarray, vec_b: np.ndarray, **kw) -> float:
    """Block-wise late-fusion scorer with configurable weights.

    Computes per-block similarities for harmonic, rhythm, timbre, and
    energy_brightness, then fuses with a weighted sum.
    """
    blocks_a = extract_blocks(vec_a)
    blocks_b = extract_blocks(vec_b)

    h = _harmonic_similarity(blocks_a, blocks_b)
    r = _rhythm_similarity(blocks_a, blocks_b)
    t = _timbre_similarity(blocks_a, blocks_b, **kw)
    e = _energy_similarity(blocks_a, blocks_b, **kw)

    wh, wr, wt, we = _get_live_fusion_weights()
    score = (
        wh * h
        + wr * r
        + wt * t
        + we * e
    )

    if not np.isfinite(score):
        return 0.0
    return float(np.clip(score, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------

def compute_similarity(
    vec_a: np.ndarray,
    vec_b: np.ndarray,
    scorer: ScorerName = ScorerName.LATE_FUSION_V1,
    **kw,
) -> float:
    """Compute similarity between two 75-D descriptor vectors using *scorer*."""
    fn = get_scorer(scorer)
    return fn(vec_a, vec_b, **kw)


# ---------------------------------------------------------------------------
# Benchmark harness
# ---------------------------------------------------------------------------

class BenchmarkHarness:
    """Run pairwise scoring diagnostics across multiple scorers.

    Parameters
    ----------
    vectors : list of np.ndarray
        Descriptor vectors to compare pairwise (or a sample thereof).
    max_pairs : int or None
        Cap on total pairs to evaluate. If None, computes all n*(n-1)/2.
    """

    def __init__(
        self,
        vectors: List[np.ndarray],
        max_pairs: Optional[int] = None,
        seed: int = 42,
    ):
        self.vectors = vectors
        self.n = len(vectors)
        self.pairs = self._build_pairs(max_pairs, seed)
        self._corpus_stats: Optional[dict] = None

    def _build_pairs(self, max_pairs, seed):
        total = self.n * (self.n - 1) // 2
        all_pairs = [
            (i, j)
            for i in range(self.n)
            for j in range(i + 1, self.n)
        ]
        if max_pairs is not None and max_pairs < total:
            rng = np.random.default_rng(seed)
            indices = rng.choice(total, size=max_pairs, replace=False)
            return [all_pairs[idx] for idx in sorted(indices)]
        return all_pairs

    def corpus_stats(self) -> dict:
        """Compute corpus-level mean, std, variance across all vectors."""
        if self._corpus_stats is not None:
            return self._corpus_stats
        mat = np.array(self.vectors)
        self._corpus_stats = {
            "corpus_mean": mat.mean(axis=0),
            "corpus_std": mat.std(axis=0),
            "corpus_variance": mat.var(axis=0),
        }
        timbre_block = mat[:, 41:67]
        self._corpus_stats["timbre_variance"] = timbre_block.var(axis=0)
        energy_block = mat[:, 67:75]
        self._corpus_stats["energy_variance"] = energy_block.var(axis=0)
        return self._corpus_stats

    def run_scorer(self, scorer_name: ScorerName) -> dict:
        """Evaluate a single scorer and return distribution + hubness stats."""
        fn = get_scorer(scorer_name)
        stats = self.corpus_stats()

        scores = np.empty(len(self.pairs), dtype=np.float64)
        for idx, (i, j) in enumerate(self.pairs):
            scores[idx] = fn(self.vectors[i], self.vectors[j], **stats)

        result = self._distribution_stats(scores)
        result["hubness"] = self._hubness_stats(scores, top_k=min(25, self.n - 1))
        result["scorer"] = scorer_name.value
        result["num_pairs"] = len(self.pairs)
        return result

    def run_all(self, scorers: Optional[List[ScorerName]] = None) -> List[dict]:
        """Evaluate all (or listed) scorers and return a list of result dicts."""
        if scorers is None:
            scorers = list_scorers()
        return [self.run_scorer(s) for s in scorers]

    @staticmethod
    def _distribution_stats(scores: np.ndarray) -> dict:
        percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        pcts = np.percentile(scores, percentiles) if len(scores) > 0 else []
        return {
            "min": float(np.min(scores)) if len(scores) else None,
            "max": float(np.max(scores)) if len(scores) else None,
            "mean": float(np.mean(scores)) if len(scores) else None,
            "std": float(np.std(scores)) if len(scores) else None,
            "percentiles": {
                str(p): float(v) for p, v in zip(percentiles, pcts)
            },
        }

    def _hubness_stats(self, scores: np.ndarray, top_k: int = 25) -> dict:
        """Compute hubness metrics from pairwise scores."""
        if self.n < 2 or top_k < 1:
            return {}

        neighbor_scores: Dict[int, List[Tuple[float, int]]] = {
            i: [] for i in range(self.n)
        }
        for idx, (i, j) in enumerate(self.pairs):
            s = scores[idx]
            neighbor_scores[i].append((s, j))
            neighbor_scores[j].append((s, i))

        top_k_actual = min(top_k, self.n - 1)
        occurrence = np.zeros(self.n, dtype=np.int64)
        for node, neighbors in neighbor_scores.items():
            neighbors.sort(key=lambda x: -x[0])
            for _, neighbor in neighbors[:top_k_actual]:
                occurrence[neighbor] += 1

        max_hub = int(np.max(occurrence))
        never_in_topk = int(np.sum(occurrence == 0))
        return {
            "top_k": top_k_actual,
            "max_hub_occurrence": max_hub,
            "fraction_never_in_topk": float(never_in_topk / self.n),
            "occurrence_mean": float(np.mean(occurrence)),
            "occurrence_std": float(np.std(occurrence)),
            "occurrence_max": max_hub,
        }
