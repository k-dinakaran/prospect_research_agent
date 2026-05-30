import { useState } from "react";
import { enrichCompany, getResults } from "./api";
import EnrichForm from "./components/EnrichForm";
import ResultCard from "./components/ResultCard";
import ResultsList from "./components/ResultsList";

export default function App() {
  // ── State ──────────────────────────────────────────────────────────────
  const [latestResult, setLatestResult]     = useState(null);
  const [allResults, setAllResults]         = useState([]);
  const [enrichLoading, setEnrichLoading]   = useState(false);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [error, setError]                   = useState("");
  const [showResults, setShowResults]       = useState(false);

  // ── Handlers ───────────────────────────────────────────────────────────

  async function handleEnrich(payload) {
    setError("");
    setEnrichLoading(true);
    setLatestResult(null);

    try {
      const profile = await enrichCompany(payload);
      setLatestResult(profile);
    } catch (err) {
      setError(err.message || "Enrichment failed. Please try again.");
    } finally {
      setEnrichLoading(false);
    }
  }

  async function handleShowResults() {
    setError("");
    setResultsLoading(true);
    setShowResults(true);

    try {
      const data = await getResults();
      setAllResults(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || "Could not load results. Please try again.");
      setAllResults([]);
    } finally {
      setResultsLoading(false);
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <div className="app">
      {/* ── Hero Header ── */}
      <header className="app-header">
        <div className="header-inner">
          <div className="logo-lockup">
            <span className="logo-icon">🔍</span>
            <div>
              <h1 className="app-title">Prospect Research Agent</h1>
              <p className="app-subtitle">
                AI-powered B2B company enrichment in seconds
              </p>
            </div>
          </div>
          <span className="badge-live">● Live</span>
        </div>
      </header>

      <main className="app-main">
        {/* ── Enrich Section ── */}
        <section className="section" aria-labelledby="enrich-heading">
          <div className="section-header">
            <h2 id="enrich-heading" className="section-title">
              Enrich a Company
            </h2>
            <p className="section-desc">
              Enter a company URL to scrape and enrich its profile using AI.
            </p>
          </div>

          <EnrichForm onSubmit={handleEnrich} loading={enrichLoading} />

          {/* ── Global error banner ── */}
          {error && (
            <div className="error-banner" role="alert">
              <span className="error-icon">⚠️</span>
              <span>{error}</span>
              <button
                className="error-dismiss"
                onClick={() => setError("")}
                aria-label="Dismiss error"
              >
                ✕
              </button>
            </div>
          )}

          {/* ── Latest enriched result ── */}
          {enrichLoading && (
            <div className="status-box">
              <span className="spinner large" aria-hidden="true" />
              <p>Enriching company profile… this may take 15–30 seconds.</p>
            </div>
          )}

          {latestResult && !enrichLoading && (
            <div className="latest-result">
              <p className="latest-label">✅ Enrichment complete</p>
              <ResultCard profile={latestResult} />
            </div>
          )}
        </section>

        {/* ── Divider ── */}
        <div className="section-divider" />

        {/* ── All Results Section ── */}
        <section className="section" aria-labelledby="results-heading">
          <div className="section-header">
            <h2 id="results-heading" className="section-title">
              Saved Results
            </h2>
            <p className="section-desc">
              All enriched company profiles saved in this session.
            </p>
          </div>

          <button
            id="show-results-btn"
            className="btn btn-secondary"
            onClick={handleShowResults}
            disabled={resultsLoading}
          >
            {resultsLoading ? (
              <span className="btn-loading">
                <span className="spinner" aria-hidden="true" />
                Loading…
              </span>
            ) : (
              "📋 Show All Results"
            )}
          </button>

          {showResults && !resultsLoading && (
            <ResultsList results={allResults} />
          )}
        </section>
      </main>

      <footer className="app-footer">
        <p>Prospect Research Agent · Hackathon Build · Backend: FastAPI + Gemini AI</p>
      </footer>
    </div>
  );
}
