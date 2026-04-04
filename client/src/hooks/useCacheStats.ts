import { useState, useEffect, useRef, useCallback } from 'react';
import type { CacheStats } from '../types';
import { fetchCacheStats } from '../api/http';

const POLL_INTERVAL = 10_000;

interface CacheStatsState {
  stats: CacheStats | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export function useCacheStats(enabled: boolean): CacheStatsState {
  const [stats, setStats] = useState<CacheStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const enabledRef = useRef(enabled);
  useEffect(() => { enabledRef.current = enabled; }, [enabled]);

  const load = useCallback(() => {
    fetchCacheStats()
      .then((data) => {
        setStats(data);
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load cache stats');
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!enabled) return;
    load();

    intervalRef.current = setInterval(load, POLL_INTERVAL);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [enabled, load]);

  const refresh = useCallback(() => {
    if (!enabledRef.current) return;
    load();
  }, [load]);

  return { stats, loading, error, refresh };
}
