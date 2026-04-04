from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TrackResponse(BaseModel):
    id: int
    title: str
    artist_names: List[str] = Field(default_factory=list)
    bpm: Optional[float] = None
    key: Optional[str] = None
    camelot_code: Optional[str] = None
    genre: Optional[str] = None
    label: Optional[str] = None
    energy: Optional[int] = None


class SearchSuggestion(BaseModel):
    id: int
    title: str
    artist_names: List[str]
    bpm: Optional[float]
    key: Optional[str]
    camelot_code: Optional[str]


class TransitionMatchResponse(BaseModel):
    candidate_id: int
    title: str
    overall_score: float
    bucket: str
    camelot_score: float
    bpm_score: float
    energy_score: float
    similarity_score: float
    freshness_score: float
    genre_similarity_score: float
    mood_continuity_score: float
    vocal_clash_score: float
    danceability_score: float
    timbre_score: float
    instrument_similarity_score: float


class MatchDetailFactorScore(BaseModel):
    name: str
    score: float
    weight: float


class MatchDetailTrackInfo(BaseModel):
    id: int
    title: str
    bpm: Optional[float]
    key: Optional[str]
    camelot_code: Optional[str]
    energy: Optional[int]
    genre: Optional[str]
    label: Optional[str]
    traits: Optional[Dict[str, Any]]


class MatchDetailResponse(BaseModel):
    overall_score: float
    factors: List[MatchDetailFactorScore]
    on_deck: MatchDetailTrackInfo
    candidate: MatchDetailTrackInfo


# ---------------------------------------------------------------------------
# Admin / cache stats
# ---------------------------------------------------------------------------


class CacheEventEntry(BaseModel):
    pair: List[int]
    timestamp: float


class CacheExitEntry(BaseModel):
    pair: List[int]
    timestamp: float
    reason: Optional[str] = None


class KeyDistributionEntry(BaseModel):
    key: str
    count: int


class BpmBinEntry(BaseModel):
    bin_start: float
    bin_end: float
    count: int


class CacheStatsResponse(BaseModel):
    used: int
    capacity: int
    usage_ratio: float
    hits: int
    misses: int
    hit_rate: float
    hit_rate_numerator: int
    hit_rate_denominator: int
    hit_rate_basis: str
    key_distribution: List[KeyDistributionEntry]
    bpm_distribution: List[BpmBinEntry]
    recent_entries: List[CacheEventEntry]
    recent_exits: List[CacheExitEntry]


# ---------------------------------------------------------------------------
# Weight controls
# ---------------------------------------------------------------------------


class WeightResponse(BaseModel):
    raw_weights: Dict[str, float]
    effective_weights: Dict[str, float]
    raw_sum: float
    target_sum: float = Field(default=100)
    is_sum_valid: bool
    message: Optional[str] = None


class WeightUpdateRequest(BaseModel):
    weights: Dict[str, float] = Field(
        ...,
        description="Factor name → value on 0-100 scale",
    )
