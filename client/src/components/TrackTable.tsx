import { useState, useRef, useLayoutEffect, useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
} from '@tanstack/react-table';
import type { Track, SearchSuggestion } from '../types';
import { cleanTitle } from '../utils';

const col = createColumnHelper<Track>();

const FIXED_PX = 90;
const FIXED_COUNT = 4;
const FLEX_MINS = [180, 140, 100, 100];
const TOTAL_FLEX = FLEX_MINS.reduce((a, b) => a + b, 0);
const TOTAL_FIXED = FIXED_COUNT * FIXED_PX;
const TOTAL_MIN = TOTAL_FIXED + TOTAL_FLEX;

function computeColWidths(container: number): number[] {
  if (container <= 0) {
    return Array(FIXED_COUNT).fill(FIXED_PX).concat(FLEX_MINS);
  }
  if (container >= TOTAL_MIN) {
    const flexBudget = container - TOTAL_FIXED;
    return [
      ...Array<number>(FIXED_COUNT).fill(FIXED_PX),
      ...FLEX_MINS.map((m) => (m / TOTAL_FLEX) * flexBudget),
    ];
  }
  const scale = container / TOTAL_MIN;
  return [
    ...Array<number>(FIXED_COUNT).fill(FIXED_PX * scale),
    ...FLEX_MINS.map((m) => m * scale),
  ];
}

const columns = [
  col.accessor('camelot_code', {
    header: 'Camelot',
    cell: (info) => <span className="mono">{info.getValue()}</span>,
  }),
  col.accessor('key', {
    header: 'Key',
    cell: (info) => <span className="mono">{info.getValue()}</span>,
  }),
  col.accessor('bpm', {
    header: 'BPM',
    cell: (info) => <span className="mono">{info.getValue()}</span>,
  }),
  col.accessor('energy', {
    header: 'Energy',
    cell: (info) => <span className="mono">{info.getValue()}</span>,
  }),
  col.accessor('title', {
    header: 'Title',
    cell: (info) => cleanTitle(info.getValue()),
  }),
  col.accessor('artist_names', {
    header: 'Artist',
    cell: (info) => info.getValue().join(', '),
  }),
  col.accessor('label', { header: 'Label' }),
  col.accessor('genre', { header: 'Genre' }),
];

interface Props {
  tracks: Track[];
  loading: boolean;
  selectedTrack: Track | SearchSuggestion | null;
  selectTrack: (track: Track) => void;
}

export function TrackTable({ tracks, loading, selectedTrack, selectTrack }: Props) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);

  useLayoutEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    setContainerWidth(el.clientWidth);
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerWidth(entry.contentRect.width);
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const colWidths = useMemo(() => computeColWidths(containerWidth), [containerWidth]);

  const table = useReactTable({
    data: tracks,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="track-table-wrapper" ref={wrapperRef}>
      <table className="track-table">
        <colgroup>
          {colWidths.map((w, i) => (
            <col key={i} style={{ width: w }} />
          ))}
        </colgroup>
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((header) => (
                <th key={header.id}>
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
