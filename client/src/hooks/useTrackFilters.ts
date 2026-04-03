import { useState, useCallback, useMemo } from 'react';
import type { Track } from '../types';

interface FilterState {
  camelotCodes: string[];
  bpm: number | undefined;
  bpmMin: number | undefined;
  bpmMax: number | undefined;
}

interface TrackFiltersResult {
  filters: FilterState;
  filteredTracks: Track[];
  setCamelotCodes: (codes: string[]) => void;
  setBpm: (bpm: number | undefined) => void;
  setBpmMin: (min: number | undefined) => void;
  setBpmMax: (max: number | undefined) => void;
}

/**
 * Client-side filtering over the session-cached collection.
 * No server round-trips on filter change — all computation is local.
 */
export function useTrackFilters(allTracks: Track[]): TrackFiltersResult {
  const [filters, setFilters] = useState<FilterState>({
    camelotCodes: [],
    bpm: undefined,
    bpmMin: undefined,
    bpmMax: undefined,
  });

  const filteredTracks = useMemo(() => {
    return allTracks.filter((track) => {
      if (
        filters.camelotCodes.length > 0 &&
        !filters.camelotCodes.includes(track.camelot_code ?? '')
      ) {
        return false;
      }
      if (filters.bpm != null && track.bpm !== filters.bpm) return false;
      if (filters.bpmMin != null && (track.bpm == null || track.bpm < filters.bpmMin))
        return false;
      if (filters.bpmMax != null && (track.bpm == null || track.bpm > filters.bpmMax))
        return false;
      return true;
    });
  }, [allTracks, filters]);

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

  return { filters, filteredTracks, setCamelotCodes, setBpm, setBpmMin, setBpmMax };
}
