import { useState, useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
} from '@tanstack/react-table';
import type { Track, SearchSuggestion, TransitionMatch } from '../types';
import { formatFloat, formatScore } from '../utils';

type BucketKey = 'same_key' | 'higher_key' | 'lower_key';

const BUCKET_TABS: { key: BucketKey; label: string }[] = [
  { key: 'same_key', label: 'Same' },
  { key: 'higher_key', label: 'Higher' },
  { key: 'lower_key', label: 'Lower' },
];

const col = createColumnHelper<TransitionMatch>();

function makeColumns(onScoreClick: (match: TransitionMatch) => void) {
  return [
    col.accessor('title', { header: 'Track', size: 240 }),
    col.accessor('overall_score', {
      header: 'Score',
      size: 70,
      cell: (info) => (
        <span
          className="mono score-link"
          onClick={(e) => {
            e.stopPropagation();
            onScoreClick(info.row.original);
          }}
        >
          {formatFloat(info.getValue())}
        </span>
      ),
    }),
    col.accessor('camelot_score', {
      header: 'Camelot',
      size: 80,
      cell: (info) => <span className="mono">{formatScore(info.getValue())}</span>,
    }),
    col.accessor('bpm_score', {
      header: 'BPM',
      size: 60,
      cell: (info) => <span className="mono">{formatScore(info.getValue())}</span>,
    }),
    col.accessor('energy_score', {
      header: 'Energy',
      size: 70,
      cell: (info) => <span className="mono">{formatScore(info.getValue())}</span>,
    }),
  ];
}

interface Props {
  selectedTrack: Track | SearchSuggestion | null;
  matches: TransitionMatch[];
  loading: boolean;
  onScoreClick: (match: TransitionMatch) => void;
}

export function MatchesPanel({ selectedTrack, matches, loading, onScoreClick }: Props) {
  const [bucketTab, setBucketTab] = useState<BucketKey>('same_key');

  const bucketMatches = useMemo(
    () => matches.filter((m) => m.bucket === bucketTab),
    [matches, bucketTab],
  );

  const columns = useMemo(() => makeColumns(onScoreClick), [onScoreClick]);

  const table = useReactTable({
    data: bucketMatches,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  if (!selectedTrack) {
    return (
      <div className="matches-panel">
        <p className="matches-empty">Select a track to see matches</p>
      </div>
    );
  }

  return (
    <div className="matches-panel">
      <h2 className="panel-title">
        Matches for <span className="matches-track-name">{selectedTrack.title}</span>
      </h2>
      <div className="bucket-tabs">
        {BUCKET_TABS.map((bt) => (
          <button
            key={bt.key}
            className={`bucket-tab${bucketTab === bt.key ? ' active' : ''}`}
            onClick={() => setBucketTab(bt.key)}
          >
            {bt.label}
            <span className="bucket-count">
              {matches.filter((m) => m.bucket === bt.key).length}
            </span>
          </button>
        ))}
      </div>
      <div className="matches-table-wrapper">
        <table className="matches-table">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => (
                  <th key={header.id} style={{ width: header.getSize() }}>
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={columns.length} className="table-status">
                  Loading matches…
                </td>
              </tr>
            ) : bucketMatches.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="table-status">
                  No matches in this bucket
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
