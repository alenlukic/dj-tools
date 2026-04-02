from typing import List, Optional

from pydantic import BaseModel


class TrackResponse(BaseModel):
    id: int
    title: str
    artist_names: List[str]
    bpm: Optional[float]
    key: Optional[str]
    camelot_code: Optional[str]
    genre: Optional[str]
    label: Optional[str]
    energy: Optional[int]


class SearchSuggestion(BaseModel):
    id: int
    title: str
    artist_names: List[str]
    bpm: Optional[float]
    key: Optional[str]
    camelot_code: Optional[str]


class TransitionMatchResponse(BaseModel):
    title: str
    overall_score: float
    bucket: str
    camelot_score: float
    bpm_score: float
    energy_score: float
