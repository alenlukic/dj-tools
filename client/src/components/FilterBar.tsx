import { useState, useRef, useEffect } from 'react';

const CAMELOT_CODES = [
  '01A','01B','02A','02B','03A','03B','04A','04B',
  '05A','05B','06A','06B','07A','07B','08A','08B',
  '09A','09B','10A','10B','11A','11B','12A','12B',
];

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

  return (
    <div className="filter-bar">
      <div className="filter-group" ref={camelotRef}>
        <label className="filter-label">Camelot</label>
        <button
          className="filter-camelot-toggle"
          onClick={() => setCamelotOpen(!camelotOpen)}
        >
          {camelotCodes.length > 0 ? camelotCodes.join(', ') : 'All keys'}
          <span className="caret">{camelotOpen ? '▲' : '▼'}</span>
        </button>
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
        <input
          type="number"
          className="filter-input mono"
          placeholder="Exact"
          value={bpm ?? ''}
          onChange={(e) => setBpm(parseNum(e.target.value))}
        />
      </div>

      <div className="filter-group">
        <label className="filter-label">BPM Range</label>
        <div className="filter-range">
          <input
            type="number"
            className="filter-input mono"
            placeholder="Min"
            value={bpmMin ?? ''}
            onChange={(e) => setBpmMin(parseNum(e.target.value))}
          />
          <span className="range-sep">–</span>
          <input
            type="number"
            className="filter-input mono"
            placeholder="Max"
            value={bpmMax ?? ''}
            onChange={(e) => setBpmMax(parseNum(e.target.value))}
          />
        </div>
      </div>
    </div>
  );
}
