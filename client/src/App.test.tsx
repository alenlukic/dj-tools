import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
import type { Track } from './types';
import { useCollectionCache } from './hooks/useCollectionCache';

vi.mock('./hooks/useCollectionCache', () => ({
  useCollectionCache: vi.fn().mockReturnValue({
    allTracks: [],
    traitMap: new Map(),
    loading: false,
  }),
}));

vi.mock('./api/http', () => ({
  fetchTracks: vi.fn().mockResolvedValue([]),
  fetchTrackTraits: vi.fn().mockResolvedValue([]),
  searchTracks: vi.fn().mockResolvedValue([]),
  fetchCacheStats: vi.fn().mockResolvedValue({
    used: 0, capacity: 100, usage_ratio: 0, hits: 0, misses: 0,
    hit_rate: 0, hit_rate_numerator: 0, hit_rate_denominator: 0,
    hit_rate_basis: 'n/a', key_distribution: [], bpm_distribution: [],
    recent_entries: [], recent_exits: [],
  }),
  fetchWeights: vi.fn().mockResolvedValue({
    raw_weights: {}, effective_weights: {}, raw_sum: 1, target_sum: 1,
    is_sum_valid: true, message: null,
  }),
  fetchMatches: vi.fn().mockResolvedValue([]),
  fetchMatchDetail: vi.fn().mockResolvedValue({}),
  updateWeights: vi.fn().mockResolvedValue({}),
}));

function makeTracks(count: number): Track[] {
  return Array.from({ length: count }, (_, i) => {
    const id = i + 1;
    return {
      id,
      title: `Track ${id}`,
      artist_names: [`Artist ${id}`],
      bpm: id <= count / 2 ? 120 : 130,
      key: 'C',
      camelot_code: id <= count / 2 ? '01A' : '02A',
      genre: 'Electronic',
      label: 'Label',
      energy: 0.5,
    };
  });
}

class ResizeObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}

let latestIntersectionCb: IntersectionObserverCallback | null = null;

class IntersectionObserverMock {
  constructor(cb: IntersectionObserverCallback) {
    latestIntersectionCb = cb;
  }
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}

function triggerLoadMore() {
  if (latestIntersectionCb) {
    latestIntersectionCb(
      [{ isIntersecting: true } as IntersectionObserverEntry],
      {} as IntersectionObserver,
    );
  }
}

beforeEach(() => {
  latestIntersectionCb = null;
  vi.stubGlobal('ResizeObserver', ResizeObserverMock);
  vi.stubGlobal('IntersectionObserver', IntersectionObserverMock);
  vi.mocked(useCollectionCache).mockReturnValue({
    allTracks: makeTracks(600),
    traitMap: new Map(),
    loading: false,
  });
});

function getRowCount(): number {
  return document.querySelectorAll('.track-table tbody tr').length;
}

async function openBrowseTab() {
  render(<App />);
  await act(async () => {
    screen.getByRole('button', { name: 'Browse' }).click();
  });
}

describe('Browse infinite scroll', () => {
  it('initially renders the first 250 tracks', async () => {
    await openBrowseTab();
    expect(getRowCount()).toBe(250);
  });

  it('loads next chunk when sentinel intersection fires', async () => {
    await openBrowseTab();
    expect(getRowCount()).toBe(250);

    await act(async () => {
      triggerLoadMore();
    });
    expect(getRowCount()).toBe(500);
  });

  it('resets to first chunk when key filter changes', async () => {
    await openBrowseTab();

    await act(async () => {
      triggerLoadMore();
    });
    expect(getRowCount()).toBe(500);

    await act(async () => {
      screen.getByRole('button', { name: /All keys/ }).click();
    });
    await act(async () => {
      screen.getByRole('button', { name: '01A' }).click();
    });

    await waitFor(() => {
      expect(getRowCount()).toBe(250);
    });
  });

  it('resets to first chunk when BPM filter changes', async () => {
    await openBrowseTab();

    await act(async () => {
      triggerLoadMore();
    });
    expect(getRowCount()).toBe(500);

    const bpmInput = screen.getByPlaceholderText('Exact');
    await userEvent.type(bpmInput, '120');

    await waitFor(() => {
      expect(getRowCount()).toBe(250);
    });
  });

  it('resets to first chunk when search text changes', async () => {
    await openBrowseTab();

    await act(async () => {
      triggerLoadMore();
    });
    expect(getRowCount()).toBe(500);

    const searchInput = screen.getByPlaceholderText('Search tracks…');
    await userEvent.type(searchInput, 'track');

    await waitFor(() => {
      expect(getRowCount()).toBe(250);
    });
  });

  it('preserves loaded progress on tab switch with unchanged filters', async () => {
    await openBrowseTab();

    await act(async () => {
      triggerLoadMore();
    });
    expect(getRowCount()).toBe(500);

    await act(async () => {
      screen.getByRole('button', { name: 'Matches' }).click();
    });
    await act(async () => {
      screen.getByRole('button', { name: 'Browse' }).click();
    });

    expect(getRowCount()).toBe(500);
  });

  it('restores loaded progress when returning to a previous filter key', async () => {
    await openBrowseTab();

    await act(async () => {
      triggerLoadMore();
    });
    expect(getRowCount()).toBe(500);

    // Switch to filter B (key=01A) — resets to page 1
    await act(async () => {
      screen.getByRole('button', { name: /All keys/ }).click();
    });
    await act(async () => {
      screen.getByRole('button', { name: '01A' }).click();
    });

    await waitFor(() => {
      expect(getRowCount()).toBe(250);
    });

    // Switch back to filter A (all keys) — should restore 2-page progress
    await act(async () => {
      screen.getByRole('button', { name: /01A/ }).click();
    });
    await act(async () => {
      screen.getByRole('button', { name: 'Clear' }).click();
    });

    await waitFor(() => {
      expect(getRowCount()).toBe(500);
    });
  });

  it('shows sentinel when more pages are available', async () => {
    await openBrowseTab();
    expect(screen.getByText('Loading more tracks…')).toBeInTheDocument();
  });

  it('hides sentinel when all pages are loaded', async () => {
    await openBrowseTab();
    await act(async () => { triggerLoadMore(); });
    await act(async () => { triggerLoadMore(); });
    expect(getRowCount()).toBe(600);
    expect(screen.queryByText('Loading more tracks…')).not.toBeInTheDocument();
  });
});
