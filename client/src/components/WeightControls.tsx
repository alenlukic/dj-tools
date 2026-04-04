import { useCallback, useRef, useState } from 'react';

const FACTOR_LABELS: Record<string, string> = {
  CAMELOT: 'Camelot',
  BPM: 'BPM',
  SIMILARITY: 'Similarity',
  FRESHNESS: 'Freshness',
  ENERGY: 'Energy',
  GENRE_SIMILARITY: 'Genre',
  MOOD_CONTINUITY: 'Mood',
  VOCAL_CLASH: 'Vocal',
  DANCEABILITY: 'Dance',
  TIMBRE: 'Timbre',
  INSTRUMENT_SIMILARITY: 'Instrument',
};

interface GaugeProps {
  factor: string;
  value: number;
  onChange: (factor: string, value: number) => void;
}

const ARC_RADIUS = 24;
const ARC_STROKE = 4;
const START_ANGLE = -135;
const END_ANGLE = 135;
const SWEEP = END_ANGLE - START_ANGLE;

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function arcPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const s = polarToCartesian(cx, cy, r, startDeg);
  const e = polarToCartesian(cx, cy, r, endDeg);
  const large = endDeg - startDeg > 180 ? 1 : 0;
  return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`;
}

function WeightGauge({ factor, value, onChange }: GaugeProps) {
  const [editing, setEditing] = useState(false);
  const [inputVal, setInputVal] = useState('');
  const svgRef = useRef<SVGSVGElement>(null);

  const clamped = Math.max(0, Math.min(100, value));
  const valueAngle = START_ANGLE + (clamped / 100) * SWEEP;
  const cx = 30;
  const cy = 30;

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      const svg = svgRef.current;
      if (!svg) return;
      e.preventDefault();
      (e.target as Element).setPointerCapture(e.pointerId);

      const update = (clientX: number, clientY: number) => {
        const rect = svg.getBoundingClientRect();
        const mx = clientX - rect.left - cx * (rect.width / 60);
        const my = clientY - rect.top - cy * (rect.height / 60);
        let angle = (Math.atan2(mx, -my) * 180) / Math.PI;
        angle = Math.max(START_ANGLE, Math.min(END_ANGLE, angle));
        const pct = ((angle - START_ANGLE) / SWEEP) * 100;
        onChange(factor, Math.round(pct));
      };

      update(e.clientX, e.clientY);

      const onMove = (ev: PointerEvent) => update(ev.clientX, ev.clientY);
      const onUp = () => {
        document.removeEventListener('pointermove', onMove);
        document.removeEventListener('pointerup', onUp);
      };
      document.addEventListener('pointermove', onMove);
      document.addEventListener('pointerup', onUp);
    },
    [factor, onChange],
  );

  const handleInputBlur = useCallback(() => {
    setEditing(false);
    const num = parseFloat(inputVal);
    if (!isNaN(num)) {
      onChange(factor, Math.max(0, Math.min(100, Math.round(num))));
    }
  }, [inputVal, factor, onChange]);

  const handleInputKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') handleInputBlur();
      if (e.key === 'Escape') setEditing(false);
    },
    [handleInputBlur],
  );

  return (
    <div className="weight-gauge">
      <svg
        ref={svgRef}
        viewBox="0 0 60 42"
        className="weight-gauge-svg"
        onPointerDown={handlePointerDown}
      >
        <path
          d={arcPath(cx, cy, ARC_RADIUS, START_ANGLE, END_ANGLE)}
          fill="none"
          stroke="var(--border)"
          strokeWidth={ARC_STROKE}
          strokeLinecap="round"
        />
        {clamped > 0 && (
          <path
            d={arcPath(cx, cy, ARC_RADIUS, START_ANGLE, valueAngle)}
            fill="none"
            stroke="var(--accent)"
            strokeWidth={ARC_STROKE}
            strokeLinecap="round"
          />
        )}
      </svg>
      {editing ? (
        <input
          type="number"
          className="weight-gauge-input"
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          onBlur={handleInputBlur}
          onKeyDown={handleInputKeyDown}
          min={0}
          max={100}
          autoFocus
        />
      ) : (
        <button
          className="weight-gauge-num"
          onClick={() => {
            setInputVal(String(Math.round(clamped)));
            setEditing(true);
          }}
        >
          {Math.round(clamped)}
        </button>
      )}
      <span className="weight-gauge-label">{FACTOR_LABELS[factor] ?? factor}</span>
    </div>
  );
}

interface Props {
  weights: Record<string, number>;
  setWeight: (factor: string, value: number) => void;
  isSumValid: boolean;
  rawSum: number;
  saving: boolean;
  normalizeWeights: () => void;
}

export function WeightControls({
  weights,
  setWeight,
  isSumValid,
  rawSum,
  saving,
  normalizeWeights,
}: Props) {
  const factors = Object.keys(weights);
  if (factors.length === 0) return null;

  return (
    <div className="weight-controls-row">
      <div className="weight-gauges">
        {factors.map((f) => (
          <WeightGauge key={f} factor={f} value={weights[f]} onChange={setWeight} />
        ))}
      </div>
      <div className="weight-actions">
        <button
          className={`weight-normalize-btn${isSumValid ? ' inactive' : ''}`}
          disabled={isSumValid}
          onClick={normalizeWeights}
        >
          Normalize{!isSumValid && ` (${parseFloat(rawSum.toFixed(1))})`}
        </button>
        {saving && <span className="weight-saving">Saving…</span>}
      </div>
    </div>
  );
}
