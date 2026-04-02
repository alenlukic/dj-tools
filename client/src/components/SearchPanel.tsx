import { useState, useRef, useEffect } from 'react';
import type { SearchSuggestion, Track } from '../types';
import { searchTracks } from '../api/http';

interface Props {
  selectTrack: (track: Track | SearchSuggestion) => void;
}

export function SearchPanel({ selectTrack }: Props) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!query.trim()) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    debounceRef.current = setTimeout(() => {
      searchTracks(query).then((results) => {
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
    setQuery(suggestion.title);
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
    <div className="search-panel" ref={containerRef}>
      <h2 className="panel-title">Search</h2>
      <input
        type="text"
        className="search-input"
        placeholder="Search tracks…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
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
