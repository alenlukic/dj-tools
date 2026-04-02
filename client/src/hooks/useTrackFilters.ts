import { useState, useCallback, useEffect } from 'react';
import type { Track } from '../types';
import { fetchTracks } from '../api/http';

interface FilterState {
  camelotCodes: string[];
  bpm: number | undefined;
  bpmMin: number | undefined;
  bpmMax: number | undefined;
}

interface TrackFiltersResult {
  filters: FilterState;
  tracks: Track[];
  tracksLoading: boolean;
  setCamelotCodes: (codes: string[]) => void;
  setBpm: (bpm: number | undefined) => void;
  setBpmMin: (min: number | undefined) => void;
  setBpmMax: (max: number | undefined) => void;
}

export function useTrackFilters(): TrackFiltersResult {
  const [filters, setFilters] = useState<FilterState>({
    camelotCodes: [],
    bpm: undefined,
    bpmMin: undefined,
    bpmMax: undefined,
  });
  const [tracks, setTracks] = useState<Track[]>([]);
  const [tracksLoading, setTracksLoading] = useState(true);

  useEffect(() => {
    setTracksLoading(true);
    fetchTracks({
      camelot_code: filters.camelotCodes.length > 0 ? filters.camelotCodes.join(',') : undefined,
      bpm: filters.bpm,
      bpm_min: filters.bpmMin,
      bpm_max: filters.bpmMax,
    })
      .then(setTracks)
      .catch(() => setTracks([]))
      .finally(() => setTracksLoading(false));
  }, [filters]);

  const setCamelotCodes = useCallback((codes: string[]) => {
    setFilters((prev) => ({ ...prev, camelotCodes: codes }));
  }, []);

  const setBpm = useCallback((bpm: number | undefined) => {
    setFilters((prev) => ({ ...prev, bpm }));
  }, []);

  const setBpmMin = useCallback((min: number | undefined) => {
    setFilters((prev) => ({ ...prev, bpmMin: min }));
  }, []);

  const setBpmMax = useCallback((max: number | undefined) => {
    setFilters((prev) => ({ ...prev, bpmMax: max }));
  }, []);

  return { filters, tracks, tracksLoading, setCamelotCodes, setBpm, setBpmMin, setBpmMax };
}
