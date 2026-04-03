export interface Track {
  id: number;
  title: string;
  artist_names: string[];
  bpm: number | null;
  key: string | null;
  camelot_code: string | null;
  genre: string | null;
  label: string | null;
  energy: number | null;
}

export interface SearchSuggestion {
  id: number;
  title: string;
  artist_names: string[];
  bpm: number | null;
  key: string | null;
  camelot_code: string | null;
}

export interface TransitionMatch {
  candidate_id: number;
  title: string;
  overall_score: number;
  bucket: 'same_key' | 'higher_key' | 'lower_key';
  camelot_score: number;
  bpm_score: number;
  energy_score: number;
  similarity_score: number;
  freshness_score: number;
  genre_similarity_score: number;
  mood_continuity_score: number;
  vocal_clash_score: number;
  danceability_score: number;
  timbre_score: number;
  instrument_similarity_score: number;
}

export interface MatchDetailFactorScore {
  name: string;
  score: number;
  weight: number;
}

export interface MatchDetailTrackInfo {
  id: number;
  title: string;
  bpm: number | null;
  key: string | null;
  camelot_code: string | null;
  energy: number | null;
  genre: string | null;
  label: string | null;
  traits: Record<string, unknown> | null;
}

export interface MatchDetail {
  overall_score: number;
  factors: MatchDetailFactorScore[];
  on_deck: MatchDetailTrackInfo;
  candidate: MatchDetailTrackInfo;
}
