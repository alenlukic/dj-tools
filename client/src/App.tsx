import { useState, useCallback } from 'react';
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

export default function App() {
  const { allTracks, loading: collectionLoading } = useCollectionCache();

  const [activeTab, setActiveTab] = useState<TabKey>('matches');
  const [detailMatch, setDetailMatch] = useState<TransitionMatch | null>(null);

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
    setCamelotCodes,
    setBpm,
    setBpmMin,
    setBpmMax,
  } = useTrackFilters(allTracks);

  const {
    weights,
    loading: weightsLoading,
    saving: weightsSaving,
    setWeight,
    rawSum,
    isSumValid,
    normalizeWeights,
  } = useWeights(refetchMatches);

  const handleSelectTrack = useCallback(
    (track: Track | SearchSuggestion) => {
      setDetailMatch(null);
      selectTrack(track);
      setActiveTab('matches');
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
          isSumValid={isSumValid}
          rawSum={rawSum}
          saving={weightsSaving}
          normalizeWeights={normalizeWeights}
        />
      )}

      <SearchPanel
        selectedTrack={selectedTrack}
        selectTrack={handleSelectTrack}
        clearSelectedTrack={clearSelectedTrack}
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
              tracks={selectedTrack ? allTracks.filter(t => t.id === selectedTrack.id) : filteredTracks}
              loading={collectionLoading}
              selectedTrack={selectedTrack}
              selectTrack={handleBrowseSelect}
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
