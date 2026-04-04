import { useEffect, useReducer } from 'react';
import type {
  Track,
  SearchSuggestion,
  TransitionMatch,
  MatchDetail as MatchDetailData,
} from '../types';
import { fetchMatchDetail } from '../api/http';
import { formatFloat, formatScore, displayGenre } from '../utils';

type DetailState = { loading: boolean; detail: MatchDetailData | null };
type DetailAction =
  | { type: 'fetch' }
  | { type: 'success'; detail: MatchDetailData }
  | { type: 'error' };

function detailReducer(_: DetailState, action: DetailAction): DetailState {
  switch (action.type) {
    case 'fetch':
      return { loading: true, detail: null };
    case 'success':
      return { loading: false, detail: action.detail };
    case 'error':
      return { loading: false, detail: null };
  }
}

interface Props {
  sourceTrack: Track | SearchSuggestion | null;
  match: TransitionMatch;
  onBack: () => void;
}

function renderValue(value: unknown): React.ReactNode {
  if (value === null || value === undefined)
    return <span className="text-muted">—</span>;
  if (typeof value === 'number')
    return <span className="mono">{formatFloat(value)}</span>;
  if (typeof value === 'string') return <span>{value}</span>;
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return <span className="text-muted">—</span>;
    return (
      <div className="json-grid">
        {entries
          .sort(([, a], [, b]) => (Number(b) || 0) - (Number(a) || 0))
          .slice(0, 10)
          .map(([k, v]) => (
            <div key={k} className="json-row">
              <span className="json-key">{k}</span>
              <span className="mono json-val">
                {typeof v === 'number' ? formatFloat(v) : String(v)}
              </span>
            </div>
          ))}
        {entries.length > 10 && (
          <div className="json-row">
            <span className="text-muted">… {entries.length - 10} more</span>
          </div>
        )}
      </div>
    );
  }
  return <span>{String(value)}</span>;
}

const TRAIT_LABELS: Record<string, string> = {
  voice_instrumental: 'Voice / Instrumental',
  danceability: 'Danceability',
  bright_dark: 'Bright / Dark',
  acoustic_electronic: 'Acoustic / Electronic',
  tonal_atonal: 'Tonal / Atonal',
  reverb: 'Reverb',
  onset_density: 'Onset Density',
  spectral_flatness: 'Spectral Flatness',
  mood_theme: 'Mood / Theme',
  genre: 'Genre',
  instruments: 'Instruments',
};

export function MatchDetail({ sourceTrack, match, onBack }: Props) {
  const [{ loading, detail }, dispatch] = useReducer(detailReducer, {
    loading: true,
    detail: null,
  });

  useEffect(() => {
    if (!sourceTrack) return;
    dispatch({ type: 'fetch' });
    fetchMatchDetail(sourceTrack.id, match.candidate_id)
      .then((result) => dispatch({ type: 'success', detail: result }))
      .catch(() => dispatch({ type: 'error' }));
  }, [sourceTrack, match]);

  if (loading) {
    return (
      <div className="match-detail">
        <button className="back-button" onClick={onBack}>
          ← Back
        </button>
        <p className="table-status">Loading detail…</p>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="match-detail">
        <button className="back-button" onClick={onBack}>
          ← Back
        </button>
        <p className="table-status">Failed to load match detail</p>
      </div>
    );
  }

  return (
    <div className="match-detail">
      <button className="back-button" onClick={onBack}>
        ← Back to matches
      </button>

      <div className="detail-header">
        <h2 className="detail-title">
          Match Detail —{' '}
          <span className="mono">{formatFloat(detail.overall_score)}</span>
        </h2>
        <div className="detail-tracks-summary">
          <span>{detail.on_deck.title}</span>
          <span className="text-muted">→</span>
          <span>{detail.candidate.title}</span>
        </div>
      </div>

      <div className="detail-section">
        <h3 className="detail-section-title">Factor Breakdown</h3>
        <table className="factor-table">
          <thead>
            <tr>
              <th>Factor</th>
              <th>Score</th>
              <th>Weight</th>
              <th>Contribution</th>
            </tr>
          </thead>
          <tbody>
            {detail.factors.map((f) => (
              <tr key={f.name}>
                <td>{f.name}</td>
                <td className="mono">{formatScore(f.score)}</td>
                <td className="mono">{formatScore(f.weight)}</td>
                <td className="mono">{formatScore(f.score * f.weight)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="detail-section">
        <h3 className="detail-section-title">Track Inputs</h3>
        <div className="detail-tracks-grid">
          {[detail.on_deck, detail.candidate].map((track) => (
            <div key={track.id} className="detail-track-card">
              <h4 className="detail-card-title">{track.title}</h4>
              <div className="detail-card-fields">
                {[
                  ['BPM', track.bpm],
                  ['Key', track.key],
                  ['Camelot', track.camelot_code],
                  ['Energy', track.energy],
                  ['Genre', displayGenre(track.genre)],
                  ['Label', track.label],
                ].map(([label, val]) => (
                  <div key={label as string} className="detail-field">
                    <span className="detail-field-label">{label as string}</span>
                    {renderValue(val)}
                  </div>
                ))}
                {track.traits &&
                  Object.entries(track.traits).map(([key, val]) => (
                    <div key={key} className="detail-field">
                      <span className="detail-field-label">
                        {TRAIT_LABELS[key] ?? key}
                      </span>
                      {renderValue(val)}
                    </div>
                  ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
