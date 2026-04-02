import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
} from '@tanstack/react-table';
import type { Track, SearchSuggestion, TransitionMatch } from '../types';

const col = createColumnHelper<TransitionMatch>();

const columns = [
  col.accessor('title', { header: 'Track', size: 240 }),
  col.accessor('overall_score', {
    header: 'Score',
    size: 70,
    cell: (info) => <span className="mono">{info.getValue().toFixed(1)}</span>,
  }),
  col.accessor('bucket', {
    header: 'Bucket',
    size: 100,
    cell: (info) => {
      const v = info.getValue();
      const labels: Record<string, string> = {
        same_key: 'Same key',
        higher_key: 'Higher',
        lower_key: 'Lower',
      };
      return labels[v] ?? v;
    },
  }),
  col.accessor('camelot_score', {
    header: 'Camelot',
    size: 80,
    cell: (info) => <span className="mono">{(info.getValue() * 100).toFixed(0)}%</span>,
  }),
  col.accessor('bpm_score', {
    header: 'BPM',
    size: 60,
    cell: (info) => <span className="mono">{(info.getValue() * 100).toFixed(0)}%</span>,
  }),
  col.accessor('energy_score', {
    header: 'Energy',
    size: 70,
    cell: (info) => <span className="mono">{(info.getValue() * 100).toFixed(0)}%</span>,
  }),
];

interface Props {
  selectedTrack: Track | SearchSuggestion | null;
  matches: TransitionMatch[];
  loading: boolean;
}

export function MatchesPanel({ selectedTrack, matches, loading }: Props) {
  const table = useReactTable({
    data: matches,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  if (!selectedTrack) {
    return (
      <div className="matches-panel">
        <h2 className="panel-title">Transition Matches</h2>
        <p className="matches-empty">Select a track to see matches</p>
      </div>
    );
  }

  return (
    <div className="matches-panel">
      <h2 className="panel-title">
        Matches for <span className="matches-track-name">{selectedTrack.title}</span>
      </h2>
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
            ) : matches.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="table-status">
                  No matches found
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
