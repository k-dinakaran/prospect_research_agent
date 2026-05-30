import ResultCard from "./ResultCard";

/**
 * ResultsList — renders an array of CompanyProfile cards.
 *
 * Props:
 *   results  — array of CompanyProfile objects
 */
export default function ResultsList({ results = [] }) {
  if (results.length === 0) {
    return (
      <div className="empty-state">
        <span className="empty-icon">📭</span>
        <p className="empty-text">No results saved yet.</p>
        <p className="empty-hint">Enrich a company first, then come back here.</p>
      </div>
    );
  }

  return (
    <section className="results-list" aria-label="All enriched companies">
      <p className="results-count">
        {results.length} {results.length === 1 ? "profile" : "profiles"} saved
      </p>
      <div className="cards-grid">
        {results.map((profile, i) => (
          <ResultCard key={`${profile.website_name}-${i}`} profile={profile} />
        ))}
      </div>
    </section>
  );
}
