import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { SearchPanel } from './components/SearchPanel';
import { FilterBar } from './components/FilterBar';
import { TrackTable } from './components/TrackTable';
import { MatchesPanel } from './components/MatchesPanel';
import { MatchDetail } from './components/MatchDetail';
import { WeightControls } from './components/WeightControls';
import { AdminDashboard } from './components/AdminDashboard';
import { useSelectedTrack } from './hooks/useSelectedTrack';
import { useTrackFilters } from './hooks/useTrackFilters';
import { useCollectionCache } from './hooks/useCollectionCache';
import { useCacheStats } from './hooks/useCacheStats';
import { useWeights } from './hooks/useWeights';
import type { Track, SearchSuggestion, TransitionMatch } from './types';

type TabKey = 'matches' | 'browse' | 'admin';

const BROWSE_PAGE_SIZE = 250;

export default function App() {
  const { allTracks, traitMap, loading: collectionLoading } = useCollectionCache();

  const [activeTab, setActiveTab] = useState<TabKey>('matches');
  const [detailMatch, setDetailMatch] = useState<TransitionMatch | null>(null);
  const [searchText, setSearchText] = useState('');
  const [loadedPages, setLoadedPages] = useState(1);
  const loadedPageCacheRef = useRef<Map<string, number>>(new Map());

  const {
    stats: cacheStats,
    loading: cacheLoading,
    error: cacheError,
    refresh: refreshCacheStats,
  } = useCacheStats(activeTab === 'admin');

  const {
    selectedTrack,
    matches,
    matchesLoading,
    selectTrack,
    clearSelectedTrack,
    refetchMatches,
  } = useSelectedTrack(refreshCacheStats);

  const {
    filters,
    filteredTracks,
    filterCacheKey,
    setCamelotCodes,
    setBpm,
    setBpmMin,
    setBpmMax,
  } = useTrackFilters(allTracks, searchText);

  const {
    weights,
    loading: weightsLoading,
    saving: weightsSaving,
    setWeight,
    rawSum,
    isSumValid,
    normalizeWeights,
  } = useWeights(refetchMatches);

  const browsePages = useMemo(() => {
    const pages: Track[][] = [];
    for (let i = 0; i < filteredTracks.length; i += BROWSE_PAGE_SIZE) {
      pages.push(filteredTracks.slice(i, i + BROWSE_PAGE_SIZE));
    }
    return pages;
  }, [filteredTracks]);

  const totalPages = browsePages.length;

  const visibleTracks = useMemo(() => {
    const cap = Math.min(loadedPages, totalPages);
    return browsePages.slice(0, cap).flat();
  }, [browsePages, loadedPages, totalPages]);

  const hasMorePages = loadedPages < totalPages;

  useEffect(() => {
    const cached = loadedPageCacheRef.current.get(filterCacheKey);
    setLoadedPages(cached ?? 1);
  }, [filterCacheKey]);

  const handleLoadMore = useCallback(() => {
    setLoadedPages(prev => {
      const next = Math.min(prev + 1, totalPages);
      loadedPageCacheRef.current.set(filterCacheKey, next);
      return next;
    });
  }, [totalPages, filterCacheKey]);

  const handleSelectTrack = useCallback(
    (track: Track | SearchSuggestion) => {
      setDetailMatch(null);
      selectTrack(track);
      setActiveTab('matches');
      setSearchText('');
    },
    [selectTrack],
  );

  const handleBrowseSelect = useCallback(
    (track: Track) => {
      handleSelectTrack(track);
      setActiveTab('matches');
    },
    [handleSelectTrack],
  );

  return (
    <div className="app-shell-v2">
      {!weightsLoading && Object.keys(weights).length > 0 && (
        <WeightControls
          weights={weights}
          setWeight={setWeight}
          saving={weightsSaving}
        />
      )}

      <SearchPanel
        selectedTrack={selectedTrack}
        selectTrack={handleSelectTrack}
        clearSelectedTrack={clearSelectedTrack}
        normalizeWeights={normalizeWeights}
        isSumValid={isSumValid}
        rawSum={rawSum}
        onSearchTextChange={setSearchText}
      />

      <div className="tab-bar">
        <button
          className={`tab${activeTab === 'matches' ? ' active' : ''}`}
          onClick={() => {
            setActiveTab('matches');
            setDetailMatch(null);
          }}
        >
          Matches
        </button>
        <button
          className={`tab${activeTab === 'browse' ? ' active' : ''}`}
          onClick={() => setActiveTab('browse')}
        >
          Browse
        </button>
        <button
          className={`tab${activeTab === 'admin' ? ' active' : ''}`}
          onClick={() => setActiveTab('admin')}
        >
          Admin
        </button>
      </div>

      <div className="tab-content">
        {activeTab === 'matches' && !detailMatch && (
          <MatchesPanel
            selectedTrack={selectedTrack}
            matches={matches}
            loading={matchesLoading}
            onScoreClick={setDetailMatch}
          />
        )}
        {activeTab === 'matches' && detailMatch && (
          <MatchDetail
            sourceTrack={selectedTrack}
            match={detailMatch}
            onBack={() => setDetailMatch(null)}
            traitMap={traitMap}
          />
        )}
        {activeTab === 'browse' && (
          <>
            <FilterBar
              camelotCodes={filters.camelotCodes}
              bpm={filters.bpm}
              bpmMin={filters.bpmMin}
              bpmMax={filters.bpmMax}
              setCamelotCodes={setCamelotCodes}
              setBpm={setBpm}
              setBpmMin={setBpmMin}
              setBpmMax={setBpmMax}
            />
            <TrackTable
              tracks={selectedTrack ? allTracks.filter(t => t.id === selectedTrack.id) : visibleTracks}
              loading={collectionLoading}
              selectedTrack={selectedTrack}
              selectTrack={handleBrowseSelect}
              hasMore={!selectedTrack ? hasMorePages : undefined}
              onLoadMore={!selectedTrack ? handleLoadMore : undefined}
            />
          </>
        )}
        {activeTab === 'admin' && (
          <AdminDashboard
            stats={cacheStats}
            loading={cacheLoading}
            error={cacheError}
          />
        )}
      </div>
    </div>
  );
}
