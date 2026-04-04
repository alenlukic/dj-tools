import { useState, useEffect, useCallback, useRef } from 'react';
import type { WeightsResponse } from '../types';
import { fetchWeights, updateWeights } from '../api/http';

interface WeightsState {
  weights: Record<string, number>;
  serverState: WeightsResponse | null;
  loading: boolean;
  error: string | null;
  saving: boolean;
  setWeight: (factor: string, value: number) => void;
  rawSum: number;
  isSumValid: boolean;
  warningMessage: string | null;
}

export function useWeights(): WeightsState {
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [serverState, setServerState] = useState<WeightsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    fetchWeights()
      .then((data) => {
        setServerState(data);
        setWeights(data.raw_weights);
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load weights');
      })
      .finally(() => setLoading(false));
  }, []);

  const persistWeights = useCallback((updated: Record<string, number>) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSaving(true);
      updateWeights(updated)
        .then((data) => {
          setServerState(data);
          setError(null);
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : 'Failed to save weights');
        })
        .finally(() => setSaving(false));
    }, 500);
  }, []);

  const setWeight = useCallback(
    (factor: string, value: number) => {
      setWeights((prev) => {
        const next = { ...prev, [factor]: value };
        persistWeights(next);
        return next;
      });
    },
    [persistWeights],
  );

  const rawSum = Object.values(weights).reduce((s, v) => s + v, 0);
  const isSumValid = Math.abs(rawSum - 100) < 0.01;
  const warningMessage =
    serverState && !serverState.is_sum_valid ? serverState.message : null;
  const displayWarning = isSumValid ? null : (warningMessage ?? `Weights sum to ${parseFloat(rawSum.toFixed(1))}; target is 100`);

  return {
    weights,
    serverState,
    loading,
    error,
    saving,
    setWeight,
    rawSum,
    isSumValid,
    warningMessage: displayWarning,
  };
}
