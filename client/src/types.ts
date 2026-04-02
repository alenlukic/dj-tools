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
  title: string;
  overall_score: number;
  bucket: 'same_key' | 'higher_key' | 'lower_key';
  camelot_score: number;
  bpm_score: number;
  energy_score: number;
}
