/**
 * ResultCard — displays one enriched company profile.
 *
 * Props:
 *   profile  — CompanyProfile object from the API
 *
 * Rules:
 *   - Never crashes on missing/null/undefined fields.
 *   - Shows "N/A" for empty strings and empty arrays.
 *   - Renders mail entries as individual badge chips.
 */
export default function ResultCard({ profile = {} }) {
  function val(key) {
    const v = profile[key];
    if (v === null || v === undefined || v === "") return "N/A";
    return String(v).trim() || "N/A";
  }

  const mails = Array.isArray(profile.mail) ? profile.mail.filter(Boolean) : [];

  const fields = [
    { icon: "🏢", label: "Company Name",        key: "company_name" },
    { icon: "📍", label: "Address",              key: "address" },
    { icon: "📞", label: "Mobile Number",        key: "mobile_number" },
    { icon: "⚙️",  label: "Core Service",         key: "core_service" },
    { icon: "🎯", label: "Target Customer",      key: "target_customer" },
    { icon: "💡", label: "Probable Pain Point",  key: "probable_pain_point" },
    { icon: "✉️",  label: "Outreach Opener",      key: "outreach_opener" },
  ];

  return (
    <article className="result-card">
      {/* Card header */}
      <div className="card-header">
        <span className="card-site-icon">🌐</span>
        <div>
          <h2 className="card-title">{val("website_name")}</h2>
          <p className="card-subtitle">Enriched Company Profile</p>
        </div>
      </div>

      {/* Fields */}
      <div className="card-body">
        {fields.map(({ icon, label, key }) => (
          <div className="card-field" key={key}>
            <span className="field-icon">{icon}</span>
            <div className="field-content">
              <span className="field-label">{label}</span>
              <span className={`field-value ${val(key) === "N/A" ? "field-na" : ""}`}>
                {val(key)}
              </span>
            </div>
          </div>
        ))}

        {/* Mail — special rendering */}
        <div className="card-field">
          <span className="field-icon">📧</span>
          <div className="field-content">
            <span className="field-label">Email</span>
            {mails.length > 0 ? (
              <div className="mail-chips">
                {mails.map((m) => (
                  <a
                    key={m}
                    href={`mailto:${m}`}
                    className="mail-chip"
                    title={m}
                  >
                    {m}
                  </a>
                ))}
              </div>
            ) : (
              <span className="field-value field-na">N/A</span>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}
