import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
} from '@tanstack/react-table';
import type { Track, SearchSuggestion } from '../types';

const col = createColumnHelper<Track>();

const columns = [
  col.accessor('title', { header: 'Title', size: 280 }),
  col.accessor('artist_names', {
    header: 'Artists',
    size: 200,
    cell: (info) => info.getValue().join(', '),
  }),
  col.accessor('bpm', {
    header: 'BPM',
    size: 70,
    cell: (info) => <span className="mono">{info.getValue()}</span>,
  }),
  col.accessor('key', {
    header: 'Key',
    size: 60,
    cell: (info) => <span className="mono">{info.getValue()}</span>,
  }),
  col.accessor('camelot_code', {
    header: 'Camelot',
    size: 80,
    cell: (info) => <span className="mono">{info.getValue()}</span>,
  }),
  col.accessor('genre', { header: 'Genre', size: 120 }),
  col.accessor('label', { header: 'Label', size: 140 }),
  col.accessor('energy', {
    header: 'Energy',
    size: 70,
    cell: (info) => <span className="mono">{info.getValue()}</span>,
  }),
];

interface Props {
  tracks: Track[];
  loading: boolean;
  selectedTrack: Track | SearchSuggestion | null;
  selectTrack: (track: Track) => void;
}

export function TrackTable({ tracks, loading, selectedTrack, selectTrack }: Props) {
  const table = useReactTable({
    data: tracks,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="track-table-wrapper">
      <table className="track-table">
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
                Loading tracks…
              </td>
            </tr>
          ) : tracks.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="table-status">
                No tracks found
              </td>
            </tr>
          ) : (
            table.getRowModel().rows.map((row) => {
              const isSelected = selectedTrack?.id === row.original.id;
              return (
                <tr
                  key={row.id}
                  className={isSelected ? 'row-selected' : ''}
                  onClick={() => selectTrack(row.original)}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
