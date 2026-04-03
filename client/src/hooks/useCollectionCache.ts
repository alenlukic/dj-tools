import { useState, useEffect } from 'react';
import type { Track } from '../types';
import { fetchTracks } from '../api/http';

/**
 * Session-scoped cache for the full track collection.
 * Loads once on mount and retains data for the session lifetime.
 * Browse filtering is done client-side against this cached dataset.
 */
export function useCollectionCache() {
  const [allTracks, setAllTracks] = useState<Track[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTracks({})
      .then(setAllTracks)
      .catch(() => setAllTracks([]))
      .finally(() => setLoading(false));
  }, []);

  return { allTracks, loading };
}
