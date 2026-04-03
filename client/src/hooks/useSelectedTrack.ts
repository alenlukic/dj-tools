import { useState, useCallback, useRef } from 'react';
import type { Track, SearchSuggestion, TransitionMatch } from '../types';
import { fetchMatches } from '../api/http';

interface SelectedTrackState {
  selectedTrack: Track | SearchSuggestion | null;
  matches: TransitionMatch[];
  matchesLoading: boolean;
  selectTrack: (track: Track | SearchSuggestion) => void;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
}

/**
 * Global selected-track state with session-scoped match caching.
 * Both autocomplete and browse selections converge on `selectTrack`.
 * Match results are cached per track ID for the session.
 */
export function useSelectedTrack(): SelectedTrackState {
  const [selectedTrack, setSelectedTrack] = useState<Track | SearchSuggestion | null>(null);
  const [matches, setMatches] = useState<TransitionMatch[]>([]);
  const [matchesLoading, setMatchesLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const abortRef = useRef<AbortController | null>(null);
  const matchCacheRef = useRef<Map<number, TransitionMatch[]>>(new Map());

  const selectTrack = useCallback((track: Track | SearchSuggestion) => {
    abortRef.current?.abort();
    setSelectedTrack(track);
    setSearchQuery(track.title);

    const cached = matchCacheRef.current.get(track.id);
    if (cached) {
      setMatches(cached);
      setMatchesLoading(false);
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    setMatches([]);
    setMatchesLoading(true);

    fetchMatches(track.id, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          matchCacheRef.current.set(track.id, data);
          setMatches(data);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setMatches([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setMatchesLoading(false);
      });
  }, []);

  return { selectedTrack, matches, matchesLoading, selectTrack, searchQuery, setSearchQuery };
}
