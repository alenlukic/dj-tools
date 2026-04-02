import { SearchPanel } from './components/SearchPanel';
import { FilterBar } from './components/FilterBar';
import { TrackTable } from './components/TrackTable';
import { MatchesPanel } from './components/MatchesPanel';
import { useSelectedTrack } from './hooks/useSelectedTrack';
import { useTrackFilters } from './hooks/useTrackFilters';

export default function App() {
  const { selectedTrack, matches, matchesLoading, selectTrack } = useSelectedTrack();
  const {
    filters,
    tracks,
    tracksLoading,
    setCamelotCodes,
    setBpm,
    setBpmMin,
    setBpmMax,
  } = useTrackFilters();

  return (
    <div className="app-shell">
      <div className="left-col">
        <SearchPanel selectTrack={selectTrack} />
        <MatchesPanel
          selectedTrack={selectedTrack}
          matches={matches}
          loading={matchesLoading}
        />
      </div>
      <div className="right-col">
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
          tracks={tracks}
          loading={tracksLoading}
          selectedTrack={selectedTrack}
          selectTrack={selectTrack}
        />
      </div>
    </div>
  );
}
