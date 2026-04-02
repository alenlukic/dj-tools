import { useState, useCallback, useRef } from 'react';
import type { Track, SearchSuggestion, TransitionMatch } from '../types';
import { fetchMatches } from '../api/http';

interface SelectedTrackState {
  selectedTrack: Track | SearchSuggestion | null;
  matches: TransitionMatch[];
  matchesLoading: boolean;
  selectTrack: (track: Track | SearchSuggestion) => void;
}

export function useSelectedTrack(): SelectedTrackState {
  const [selectedTrack, setSelectedTrack] = useState<Track | SearchSuggestion | null>(null);
  const [matches, setMatches] = useState<TransitionMatch[]>([]);
  const [matchesLoading, setMatchesLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const selectTrack = useCallback((track: Track | SearchSuggestion) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setSelectedTrack(track);
    setMatches([]);
    setMatchesLoading(true);

    fetchMatches(track.id, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setMatches(data);
      })
      .catch(() => {
        if (!controller.signal.aborted) setMatches([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setMatchesLoading(false);
      });
  }, []);

  return { selectedTrack, matches, matchesLoading, selectTrack };
}
