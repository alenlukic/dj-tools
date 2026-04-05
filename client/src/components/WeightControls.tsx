import { memo, useCallback, useRef, useState } from 'react';
import { gaugeWeightToFill } from '../utils';

const FUSION_SUBFACTOR_KEYS = [
  { key: 'FUSION_HARMONIC', label: 'Harmonic' },
  { key: 'FUSION_RHYTHM',   label: 'Rhythm' },
  { key: 'FUSION_TIMBRE',   label: 'Timbre' },
  { key: 'FUSION_ENERGY',   label: 'Energy' },
] as const;

const FACTOR_LABELS: Record<string, string> = {
  CAMELOT: 'Camelot',
  BPM: 'BPM',
  SIMILARITY: 'Fusion',
  FRESHNESS: 'Freshness',
  ENERGY: 'Energy',
  GENRE_SIMILARITY: 'Genre',
  MOOD_CONTINUITY: 'Mood',
  VOCAL_CLASH: 'Vocal',
  DANCEABILITY: 'Dance',
  TIMBRE: 'Timbre',
  INSTRUMENT_SIMILARITY: 'Instrument',
};

const GAUGE_ROWS: { factors: string[]; colorClass: string }[] = [
  { factors: ['BPM', 'CAMELOT', 'GENRE_SIMILARITY'], colorClass: 'weight-gauge--crimson' },
  {
    factors: ['ENERGY', 'DANCEABILITY', 'MOOD_CONTINUITY', 'TIMBRE', 'INSTRUMENT_SIMILARITY', 'VOCAL_CLASH'],
    colorClass: 'weight-gauge--teal',
  },
];

interface GaugeProps {
  factor: string;
  value: number;
  onChange: (factor: string, value: number) => void;
  colorClass?: string;
  readOnly?: boolean;
  label?: string;
  hideLabel?: boolean;
  small?: boolean;
}

const ARC_RADIUS = 24;
const ARC_STROKE = 4;
const START_ANGLE = -135;
const END_ANGLE = 135;
const SWEEP = END_ANGLE - START_ANGLE;
// Drag sensitivity (weight units per degree) follows an exponential decay with a floor:
//   sensitivity = max(FLOOR, BASE * exp(-weight * DECAY))
// Profile:  weight=0 → 0.18,  weight=10 → ~0.13,  weight=25 → ~0.085,
//           weight=50 → ~0.04, weight=100 → 0.03 (floor)
const DRAG_SENSITIVITY_BASE = 0.18;
const DRAG_DECAY = 0.03;

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

function WeightGaugeBase({ factor, value, onChange, colorClass, readOnly, label, hideLabel }: GaugeProps) {
  const [editing, setEditing] = useState(false);
  const [inputVal, setInputVal] = useState('');
  // Local float drag state — keeps the visual smooth without triggering parent renders.
  const [dragValue, setDragValue] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const clamped = Math.max(0, Math.min(100, value));
  // During a drag use the local float; only fall back to parent value when idle.
  const displayValue = dragValue !== null ? dragValue : clamped;
  const fillPct = gaugeWeightToFill(displayValue);
  const valueAngle = START_ANGLE + (fillPct / 100) * SWEEP;
  const cx = 30;
  const cy = 30;

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (readOnly) return;
      const svg = svgRef.current;
      if (!svg) return;
      e.preventDefault();
      (e.target as Element).setPointerCapture(e.pointerId);

      // Work in weight-space so resistance is expressed as weight units per degree.
      let currentWeight = clamped;

      const getAngle = (clientX: number, clientY: number) => {
        const rect = svg.getBoundingClientRect();
        const mx = clientX - rect.left - cx * (rect.width / 60);
        const my = clientY - rect.top - cy * (rect.height / 42);
        return (Math.atan2(mx, -my) * 180) / Math.PI;
      };

      let prevAngle = getAngle(e.clientX, e.clientY);

      const onMove = (ev: PointerEvent) => {
        const angle = getAngle(ev.clientX, ev.clientY);
        let rawDelta = angle - prevAngle;
        // Clamp to [-180, 180] so crossing the atan2 ±180° seam never causes a wild swing.
        if (rawDelta > 180) rawDelta -= 360;
        if (rawDelta < -180) rawDelta += 360;
        prevAngle = angle;

        // Resistance climbs as weight rises up to 25, then stays constant.
        const sensitivity = DRAG_SENSITIVITY_BASE * Math.exp(-Math.min(currentWeight, 25) * DRAG_DECAY);
        currentWeight = Math.max(0, Math.min(100, currentWeight + rawDelta * sensitivity));

        // Update only local state — no parent call, no app-level re-render during drag.
        setDragValue(currentWeight);
      };

      const onUp = () => {
        // Single parent commit on release; round only here, never during the drag.
        onChange(factor, Math.round(currentWeight));
        setDragValue(null);
        document.removeEventListener('pointermove', onMove);
        document.removeEventListener('pointerup', onUp);
      };
      document.addEventListener('pointermove', onMove);
      document.addEventListener('pointerup', onUp);
    },
    [factor, onChange, readOnly, clamped],
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

  const displayLabel = label ?? FACTOR_LABELS[factor] ?? factor;
  const gaugeClass = ['weight-gauge', colorClass].filter(Boolean).join(' ');

  return (
    <div className={gaugeClass}>
      <div className="gauge-arc-pane">
        <svg
          ref={svgRef}
          viewBox="0 0 60 42"
          className="weight-gauge-svg"
          onPointerDown={handlePointerDown}
          style={readOnly ? { cursor: 'default' } : undefined}
        >
          <path
            d={arcPath(cx, cy, ARC_RADIUS, START_ANGLE, END_ANGLE)}
            fill="none"
            stroke="var(--border)"
            strokeWidth={ARC_STROKE}
            strokeLinecap="round"
          />
          {displayValue > 0 && (
            <path
              d={arcPath(cx, cy, ARC_RADIUS, START_ANGLE, valueAngle)}
              fill="none"
              stroke="var(--gauge-accent, var(--accent))"
              strokeWidth={ARC_STROKE}
              strokeLinecap="round"
            />
          )}
        </svg>
        {!hideLabel && (
          <div className="gauge-value-overlay">
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
              <span
                className="gauge-value-display"
                style={readOnly ? undefined : { cursor: 'pointer' }}
                onClick={readOnly ? undefined : (e: React.MouseEvent) => {
                  e.stopPropagation();
                  setInputVal(String(Math.round(clamped)));
                  setEditing(true);
                }}
              >
                {Math.round(displayValue)}
              </span>
            )}
          </div>
        )}
      </div>
      {!hideLabel && (
        <span className="weight-gauge-label">{displayLabel}</span>
      )}
    </div>
  );
}

const WeightGauge = memo(WeightGaugeBase);

interface Props {
  weights: Record<string, number>;
  setWeight: (factor: string, value: number) => void;
}

export const WeightControls = memo(function WeightControls({
  weights,
  setWeight,
}: Props) {
  const factors = Object.keys(weights);
  if (factors.length === 0) return null;

  return (
    <div className="weight-controls-row">
      <div className="gauge-group gauge-group--bpm">
        {GAUGE_ROWS[0].factors
          .filter((f) => f in weights)
          .map((f) => (
            <WeightGauge
              key={f}
              factor={f}
              value={weights[f]}
              onChange={setWeight}
              colorClass={GAUGE_ROWS[0].colorClass}
            />
          ))}
      </div>
      <div className="gauge-group gauge-group--energy">
        {GAUGE_ROWS[1].factors
          .filter((f) => f in weights)
          .map((f) => (
            <WeightGauge
              key={f}
              factor={f}
              value={weights[f]}
              onChange={setWeight}
              colorClass={GAUGE_ROWS[1].colorClass}
            />
          ))}
      </div>
      <div className="gauge-group gauge-group--fusion">
        {factors.includes('SIMILARITY') && (
          <div className="fusion-pane">
            <WeightGauge
              factor="SIMILARITY"
              value={weights['SIMILARITY']}
              onChange={setWeight}
              colorClass="weight-gauge--violet"
            />
            <div className="fusion-subfactors">
              {FUSION_SUBFACTOR_KEYS.map((item) => (
                <WeightGauge
                  key={item.key}
                  factor={item.key}
                  value={weights[item.key] ?? 0}
                  onChange={setWeight}
                  colorClass="weight-gauge--white"
                  label={item.label}
                  small
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
});
