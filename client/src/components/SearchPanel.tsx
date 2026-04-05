import { useState, useRef, useEffect, useCallback } from 'react';
import type { SearchSuggestion, Track } from '../types';
import { searchTracks } from '../api/http';

const searchCache = new Map<string, SearchSuggestion[]>();

interface Props {
  selectedTrack: Track | SearchSuggestion | null;
  selectTrack: (track: Track | SearchSuggestion) => void;
  clearSelectedTrack: () => void;
  normalizeWeights: () => void;
  isSumValid: boolean;
  rawSum: number;
  onSearchTextChange?: (text: string) => void;
}

export function SearchPanel({ selectedTrack, selectTrack, clearSelectedTrack, normalizeWeights, isSumValid, rawSum, onSearchTextChange }: Props) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [prevTrackId, setPrevTrackId] = useState<number | null>(null);
  const trackId = selectedTrack?.id ?? null;
  if (trackId !== prevTrackId) {
    setPrevTrackId(trackId);
    if (selectedTrack) {
      setQuery(selectedTrack.title);
    }
  }

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const newQuery = e.target.value;
      setQuery(newQuery);
      clearSelectedTrack();
      onSearchTextChange?.(newQuery);

      if (debounceRef.current) clearTimeout(debounceRef.current);

      const trimmed = newQuery.trim();
      if (!trimmed) {
        setSuggestions([]);
        setOpen(false);
        return;
      }

      const cached = searchCache.get(trimmed);
      if (cached) {
        setSuggestions(cached);
        setOpen(cached.length > 0);
        setActiveIdx(-1);
        return;
      }

      debounceRef.current = setTimeout(() => {
        searchTracks(newQuery).then((results) => {
          searchCache.set(trimmed, results);
          setSuggestions(results);
          setOpen(results.length > 0);
          setActiveIdx(-1);
        });
      }, 200);
    },
    [clearSelectedTrack, onSearchTextChange],
  );

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  function handleSelect(suggestion: SearchSuggestion) {
    selectTrack(suggestion);
    setOpen(false);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!open) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx((prev) => Math.min(prev + 1, suggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((prev) => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter' && activeIdx >= 0) {
      e.preventDefault();
      handleSelect(suggestions[activeIdx]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  }

  return (
    <div className="search-bar-wrapper" ref={containerRef}>
      <div className="search-input-container">
        <input
          type="text"
          className="search-input"
          placeholder="Search tracks…"
          value={query}
          onChange={handleInputChange}
          onFocus={() => suggestions.length > 0 && setOpen(true)}
          onKeyDown={handleKeyDown}
        />
        {open && (
          <ul className="search-dropdown">
            {suggestions.map((s, i) => (
              <li
                key={s.id}
                className={`search-item${i === activeIdx ? ' active' : ''}`}
                onMouseDown={() => handleSelect(s)}
                onMouseEnter={() => setActiveIdx(i)}
              >
                <span className="search-item-title">{s.title}</span>
                <span className="search-item-meta">
                  {s.artist_names.join(', ')}
                  {s.camelot_code && <span className="mono"> · {s.camelot_code}</span>}
                  {s.bpm != null && <span className="mono"> · {s.bpm}</span>}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <button
        className={`weight-normalize-btn${isSumValid ? ' inactive' : ''}`}
        disabled={isSumValid}
        onClick={normalizeWeights}
      >
        Normalize Weights{!isSumValid && ` (${parseFloat(rawSum.toFixed(1))})`}
      </button>
    </div>
  );
}
