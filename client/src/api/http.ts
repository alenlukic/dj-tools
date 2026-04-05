import type { Track, SearchSuggestion, TransitionMatch, MatchDetail, CacheStats, WeightsResponse, TrackTraitEntry } from '../types';

export async function fetchTracks(params: {
  camelot_code?: string;
  bpm?: number;
  bpm_min?: number;
  bpm_max?: number;
}): Promise<Track[]> {
  const qs = new URLSearchParams();
  if (params.camelot_code) qs.set('camelot_code', params.camelot_code);
  if (params.bpm != null) qs.set('bpm', String(params.bpm));
  if (params.bpm_min != null) qs.set('bpm_min', String(params.bpm_min));
  if (params.bpm_max != null) qs.set('bpm_max', String(params.bpm_max));

  const url = `/api/tracks${qs.toString() ? '?' + qs.toString() : ''}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch tracks: ${res.status}`);
  return res.json();
}

export async function searchTracks(q: string): Promise<SearchSuggestion[]> {
  if (!q.trim()) return [];
  const res = await fetch(`/api/search?q=${encodeURIComponent(q.trim())}`);
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

export async function fetchMatches(trackId: number, signal?: AbortSignal): Promise<TransitionMatch[]> {
  const res = await fetch(`/api/tracks/${trackId}/matches`, { signal });
  if (!res.ok) throw new Error(`Failed to fetch matches: ${res.status}`);
  return res.json();
}

export async function fetchMatchDetail(trackId: number, candidateId: number): Promise<MatchDetail> {
  const res = await fetch(`/api/tracks/${trackId}/match-detail/${candidateId}`);
  if (!res.ok) throw new Error(`Failed to fetch match detail: ${res.status}`);
  return res.json();
}

export async function fetchTrackTraits(): Promise<TrackTraitEntry[]> {
  const res = await fetch('/api/track-traits');
  if (!res.ok) throw new Error(`Failed to fetch track traits: ${res.status}`);
  return res.json();
}

export async function fetchCacheStats(): Promise<CacheStats> {
  const res = await fetch('/api/admin/cache-stats');
  if (!res.ok) throw new Error(`Failed to fetch cache stats: ${res.status}`);
  return res.json();
}

export async function fetchWeights(): Promise<WeightsResponse> {
  const res = await fetch('/api/weights');
  if (!res.ok) throw new Error(`Failed to fetch weights: ${res.status}`);
  return res.json();
}

export async function updateWeights(weights: Record<string, number>): Promise<WeightsResponse> {
  const res = await fetch('/api/weights', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ weights }),
  });
  if (!res.ok) throw new Error(`Failed to update weights: ${res.status}`);
  return res.json();
}
