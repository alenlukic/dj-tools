import { useState, useCallback } from 'react';
import { SearchPanel } from './components/SearchPanel';
import { FilterBar } from './components/FilterBar';
import { TrackTable } from './components/TrackTable';
import { MatchesPanel } from './components/MatchesPanel';
import { MatchDetail } from './components/MatchDetail';
import { useSelectedTrack } from './hooks/useSelectedTrack';
import { useTrackFilters } from './hooks/useTrackFilters';
import { useCollectionCache } from './hooks/useCollectionCache';
import type { Track, SearchSuggestion, TransitionMatch } from './types';

export default function App() {
  const { allTracks, loading: collectionLoading } = useCollectionCache();
  const {
    selectedTrack,
    matches,
    matchesLoading,
    selectTrack,
    searchQuery,
    setSearchQuery,
  } = useSelectedTrack();
  const {
    filters,
    filteredTracks,
    setCamelotCodes,
    setBpm,
    setBpmMin,
    setBpmMax,
  } = useTrackFilters(allTracks);

  const [activeTab, setActiveTab] = useState<'matches' | 'browse'>('matches');
  const [detailMatch, setDetailMatch] = useState<TransitionMatch | null>(null);

  const handleSelectTrack = useCallback(
    (track: Track | SearchSuggestion) => {
      setDetailMatch(null);
      selectTrack(track);
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
      <SearchPanel
        query={searchQuery}
        setQuery={setSearchQuery}
        selectTrack={handleSelectTrack}
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
              tracks={filteredTracks}
              loading={collectionLoading}
              selectedTrack={selectedTrack}
              selectTrack={handleBrowseSelect}
            />
          </>
        )}
      </div>
    </div>
  );
}
