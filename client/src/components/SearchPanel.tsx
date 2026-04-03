import { useState, useRef, useEffect, useCallback } from 'react';
import type { SearchSuggestion, Track } from '../types';
import { searchTracks } from '../api/http';

/**
 * Session-scoped cache for `/api/search` (autocomplete) responses keyed by
 * trimmed query string. Eliminates redundant Elasticsearch round-trips when a
 * user revisits a previously-typed query within the same page session.
 * Resets naturally on page reload since it is module-level state.
 */
const searchCache = new Map<string, SearchSuggestion[]>();

interface Props {
  query: string;
  setQuery: (q: string) => void;
  selectTrack: (track: Track | SearchSuggestion) => void;
}

export function SearchPanel({ query, setQuery, selectTrack }: Props) {
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const userTypedRef = useRef(false);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      userTypedRef.current = true;
      setQuery(e.target.value);
    },
    [setQuery],
  );

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!userTypedRef.current) return;
    userTypedRef.current = false;

    const trimmed = query.trim();
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
      searchTracks(query).then((results) => {
        searchCache.set(trimmed, results);
        setSuggestions(results);
        setOpen(results.length > 0);
        setActiveIdx(-1);
      });
    }, 200);
    return () => clearTimeout(debounceRef.current ?? undefined);
  }, [query]);

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
  );
}
