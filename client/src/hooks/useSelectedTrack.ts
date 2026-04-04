import { useState, useCallback, useRef, useEffect } from 'react';
import type { Track, SearchSuggestion, TransitionMatch } from '../types';
import { fetchMatches } from '../api/http';

interface SelectedTrackState {
  selectedTrack: Track | SearchSuggestion | null;
  matches: TransitionMatch[];
  matchesLoading: boolean;
  selectTrack: (track: Track | SearchSuggestion) => void;
  clearSelectedTrack: () => void;
  refetchMatches: () => void;
}

/**
 * Global selected-track state with session-scoped match caching.
 * Both autocomplete and browse selections converge on `selectTrack`.
 * Match results are cached per track ID for the session.
 */
export function useSelectedTrack(onTrackAction?: () => void): SelectedTrackState {
  const [selectedTrack, setSelectedTrack] = useState<Track | SearchSuggestion | null>(null);
  const [matches, setMatches] = useState<TransitionMatch[]>([]);
  const [matchesLoading, setMatchesLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const matchCacheRef = useRef<Map<number, TransitionMatch[]>>(new Map());
  const selectedTrackRef = useRef<Track | SearchSuggestion | null>(null);
  const onTrackActionRef = useRef(onTrackAction);
  useEffect(() => {
    onTrackActionRef.current = onTrackAction;
  }, [onTrackAction]);

  const loadMatches = useCallback((trackId: number) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setMatchesLoading(true);

    fetchMatches(trackId, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          matchCacheRef.current.set(trackId, data);
          setMatches(data);
          onTrackActionRef.current?.();
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setMatches([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setMatchesLoading(false);
      });
  }, []);

  const selectTrack = useCallback((track: Track | SearchSuggestion) => {
    abortRef.current?.abort();
    setSelectedTrack(track);
    selectedTrackRef.current = track;

    const cached = matchCacheRef.current.get(track.id);
    if (cached) {
      setMatches(cached);
      setMatchesLoading(false);
      return;
    }

    setMatches([]);
    loadMatches(track.id);
  }, [loadMatches]);

  const clearSelectedTrack = useCallback(() => {
    if (selectedTrackRef.current === null) return;
    abortRef.current?.abort();
    setSelectedTrack(null);
    selectedTrackRef.current = null;
    setMatches([]);
    setMatchesLoading(false);
  }, []);

  const refetchMatches = useCallback(() => {
    const track = selectedTrackRef.current;
    if (!track) return;
    matchCacheRef.current.delete(track.id);
    loadMatches(track.id);
  }, [loadMatches]);

  return { selectedTrack, matches, matchesLoading, selectTrack, clearSelectedTrack, refetchMatches };
}
