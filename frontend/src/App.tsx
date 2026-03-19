import { useEffect, useState } from "react";

import { CropSelector } from "./components/CropSelector";
import { FieldRankingCard } from "./components/FieldRankingCard";
import { RankingSummary } from "./components/RankingSummary";
import { fetchCrops, rankFieldsForCrop } from "./lib/api";
import type { CropProfileRead, RankFieldsResponse } from "./types/ranking";

export function App() {
  const [crops, setCrops] = useState<CropProfileRead[]>([]);
  const [selectedCropId, setSelectedCropId] = useState<number | null>(null);
  const [ranking, setRanking] = useState<RankFieldsResponse | null>(null);
  const [loadingCrops, setLoadingCrops] = useState(true);
  const [loadingResults, setLoadingResults] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadCrops() {
      try {
        const response = await fetchCrops();
        if (!active) {
          return;
        }
        setCrops(response);
        if (response.length > 0) {
          setSelectedCropId(response[0].id);
        }
      } catch (error) {
        if (!active) {
          return;
        }
        setErrorMessage(
          error instanceof Error ? error.message : "Unable to load crop profiles.",
        );
      } finally {
        if (active) {
          setLoadingCrops(false);
        }
      }
    }

    loadCrops();
    return () => {
      active = false;
    };
  }, []);

  async function handleRankFields() {
    if (selectedCropId === null) {
      return;
    }

    setLoadingResults(true);
    setErrorMessage(null);

    try {
      const response = await rankFieldsForCrop(selectedCropId);
      setRanking(response);
    } catch (error) {
      setRanking(null);
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to rank fields right now.",
      );
    } finally {
      setLoadingResults(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="hero-panel">
        <div className="hero-panel__content">
          <p className="hero-panel__eyebrow">AgriMind MVP</p>
          <h1 className="hero-panel__title">Field ranking for crop placement</h1>
          <p className="hero-panel__body">
            Select a crop profile and rank the top five field candidates using the
            current rule-based suitability engine.
          </p>
        </div>

        <div className="control-panel">
          <CropSelector
            crops={crops}
            selectedCropId={selectedCropId}
            disabled={loadingCrops || loadingResults}
            onChange={setSelectedCropId}
          />

          <button
            className="primary-button"
            disabled={loadingCrops || loadingResults || selectedCropId === null}
            onClick={handleRankFields}
            type="button"
          >
            {loadingResults ? "Ranking fields..." : "Rank top 5 fields"}
          </button>
        </div>
      </section>

      {errorMessage ? (
        <section className="feedback-panel feedback-panel--error">
          <h2 className="feedback-panel__title">Unable to load ranking data</h2>
          <p>{errorMessage}</p>
        </section>
      ) : null}

      {loadingCrops ? (
        <section className="feedback-panel">
          <h2 className="feedback-panel__title">Loading crop profiles</h2>
          <p>Fetching available crop profiles from the AgriMind API.</p>
        </section>
      ) : null}

      {!loadingCrops && ranking === null && errorMessage === null ? (
        <section className="feedback-panel">
          <h2 className="feedback-panel__title">No ranking loaded yet</h2>
          <p>Choose a crop and run the ranking to see the strongest field candidates.</p>
        </section>
      ) : null}

      {ranking ? (
        <section className="results-panel">
          <RankingSummary response={ranking} />

          <div className="results-grid">
            {ranking.ranked_results.slice(0, 5).map((result) => (
              <FieldRankingCard key={result.field_id} result={result} />
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );
}
