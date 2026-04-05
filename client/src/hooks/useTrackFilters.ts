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
  filterCacheKey: string;
  setCamelotCodes: (codes: string[]) => void;
  setBpm: (bpm: number | undefined) => void;
  setBpmMin: (min: number | undefined) => void;
  setBpmMax: (max: number | undefined) => void;
}

/**
 * Client-side filtering over the session-cached collection.
 * No server round-trips on filter change — all computation is local.
 */
export function useTrackFilters(allTracks: Track[], searchText: string = ''): TrackFiltersResult {
  const [filters, setFilters] = useState<FilterState>({
    camelotCodes: [],
    bpm: undefined,
    bpmMin: undefined,
    bpmMax: undefined,
  });

  const normalizedSearch = searchText.trim().toLowerCase();

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
      if (normalizedSearch) {
        const title = track.title.toLowerCase();
        const artists = track.artist_names.join(' ').toLowerCase();
        if (!title.includes(normalizedSearch) && !artists.includes(normalizedSearch)) {
          return false;
        }
      }
      return true;
    });
  }, [allTracks, filters, normalizedSearch]);

  const filterCacheKey = useMemo(() => {
    return JSON.stringify({
      searchText: normalizedSearch,
      camelotCodes: [...filters.camelotCodes].sort(),
      bpm: filters.bpm ?? null,
      bpmMin: filters.bpmMin ?? null,
      bpmMax: filters.bpmMax ?? null,
    });
  }, [normalizedSearch, filters]);

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

  return { filters, filteredTracks, filterCacheKey, setCamelotCodes, setBpm, setBpmMin, setBpmMax };
}
