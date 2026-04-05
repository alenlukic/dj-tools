import { useState, useRef, useEffect } from 'react';

const CAMELOT_CODES = [
  '01A','01B','02A','02B','03A','03B','04A','04B',
  '05A','05B','06A','06B','07A','07B','08A','08B',
  '09A','09B','10A','10B','11A','11B','12A','12B',
];

const RANGE_DEBOUNCE_MS = 300;

interface Props {
  camelotCodes: string[];
  bpm: number | undefined;
  bpmMin: number | undefined;
  bpmMax: number | undefined;
  setCamelotCodes: (codes: string[]) => void;
  setBpm: (bpm: number | undefined) => void;
  setBpmMin: (min: number | undefined) => void;
  setBpmMax: (max: number | undefined) => void;
}

export function FilterBar({
  camelotCodes,
  bpm,
  bpmMin,
  bpmMax,
  setCamelotCodes,
  setBpm,
  setBpmMin,
  setBpmMax,
}: Props) {
  const [camelotOpen, setCamelotOpen] = useState(false);
  const camelotRef = useRef<HTMLDivElement>(null);

  const [minText, setMinText] = useState(bpmMin != null ? String(bpmMin) : '');
  const [maxText, setMaxText] = useState(bpmMax != null ? String(bpmMax) : '');
  const minTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const maxTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    return () => {
      clearTimeout(minTimer.current);
      clearTimeout(maxTimer.current);
    };
  }, []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (camelotRef.current && !camelotRef.current.contains(e.target as Node)) {
        setCamelotOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  function toggleCode(code: string) {
    if (camelotCodes.includes(code)) {
      setCamelotCodes(camelotCodes.filter((c) => c !== code));
    } else {
      setCamelotCodes([...camelotCodes, code]);
    }
    setCamelotOpen(false);
  }

  function parseNum(val: string): number | undefined {
    const n = parseFloat(val);
    return Number.isNaN(n) ? undefined : n;
  }

  function handleMinChange(e: React.ChangeEvent<HTMLInputElement>) {
    const text = e.target.value;
    setMinText(text);
    clearTimeout(minTimer.current);
    minTimer.current = setTimeout(() => setBpmMin(parseNum(text)), RANGE_DEBOUNCE_MS);
  }

  function handleMaxChange(e: React.ChangeEvent<HTMLInputElement>) {
    const text = e.target.value;
    setMaxText(text);
    clearTimeout(maxTimer.current);
    maxTimer.current = setTimeout(() => setBpmMax(parseNum(text)), RANGE_DEBOUNCE_MS);
  }

  function handleMinBlur() {
    clearTimeout(minTimer.current);
    setBpmMin(parseNum(minText));
  }

  function handleMaxBlur() {
    clearTimeout(maxTimer.current);
    setBpmMax(parseNum(maxText));
  }

  return (
    <div className="filter-bar">
      <div className="filter-group" ref={camelotRef}>
        <label className="filter-label">Camelot</label>
        <div className="filter-input-row">
          <button
            className="filter-camelot-toggle"
            onClick={() => setCamelotOpen(!camelotOpen)}
          >
            {camelotCodes.length > 0 ? camelotCodes.join(', ') : 'All keys'}
            <span className="caret">{camelotOpen ? '▲' : '▼'}</span>
          </button>
          {camelotCodes.length > 0 && (
            <button className="clear-btn" onClick={() => setCamelotCodes([])} tabIndex={-1}>×</button>
          )}
        </div>
        {camelotOpen && (
          <div className="camelot-grid">
            {CAMELOT_CODES.map((code) => (
              <button
                key={code}
                className={`camelot-chip${camelotCodes.includes(code) ? ' selected' : ''}`}
                onClick={() => toggleCode(code)}
              >
                {code}
              </button>
            ))}
            {camelotCodes.length > 0 && (
              <button className="camelot-chip clear" onClick={() => setCamelotCodes([])}>
                Clear
              </button>
            )}
          </div>
        )}
      </div>

      <div className="filter-group">
        <label className="filter-label">BPM</label>
        <div className="filter-input-row">
          <input
            type="number"
            className="filter-input mono"
            placeholder="Exact"
            value={bpm ?? ''}
            onChange={(e) => setBpm(parseNum(e.target.value))}
          />
          {bpm != null && (
            <button className="clear-btn" onClick={() => setBpm(undefined)} tabIndex={-1}>×</button>
          )}
        </div>
      </div>

      <div className="filter-group">
        <label className="filter-label">BPM Range</label>
        <div className="filter-range">
          <input
            type="number"
            className="filter-input mono"
            placeholder="Min"
            value={minText}
            onChange={handleMinChange}
            onBlur={handleMinBlur}
          />
          <span className="range-sep">–</span>
          <input
            type="number"
            className="filter-input mono"
            placeholder="Max"
            value={maxText}
            onChange={handleMaxChange}
            onBlur={handleMaxBlur}
          />
          {(minText || maxText) && (
            <button
              className="clear-btn"
              onClick={() => {
                clearTimeout(minTimer.current);
                clearTimeout(maxTimer.current);
                setMinText('');
                setMaxText('');
                setBpmMin(undefined);
                setBpmMax(undefined);
              }}
              tabIndex={-1}
            >
              ×
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
