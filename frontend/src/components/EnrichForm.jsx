import { useState } from "react";

/**
 * EnrichForm — controlled form for submitting a company URL to the enrichment API.
 *
 * Props:
 *   onSubmit(payload)  — called with { website_name, url }
 *   loading            — disables the button and shows spinner text
 */
export default function EnrichForm({ onSubmit, loading }) {
  const [websiteName, setWebsiteName] = useState("");
  const [url, setUrl] = useState("");
  const [validationError, setValidationError] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    setValidationError("");

    const trimmedUrl = url.trim();
    if (!trimmedUrl) {
      setValidationError("Company URL is required.");
      return;
    }

    onSubmit({ website_name: websiteName.trim(), url: trimmedUrl });
  }

  return (
    <form className="enrich-form" onSubmit={handleSubmit} noValidate>
      <div className="form-group">
        <label htmlFor="website-name">Website Name</label>
        <input
          id="website-name"
          type="text"
          placeholder="e.g. Zoho"
          value={websiteName}
          onChange={(e) => setWebsiteName(e.target.value)}
          disabled={loading}
          autoComplete="off"
        />
        <span className="field-hint">Optional — overrides the URL-derived name</span>
      </div>

      <div className="form-group">
        <label htmlFor="company-url">
          Company URL <span className="required">*</span>
        </label>
        <input
          id="company-url"
          type="url"
          placeholder="https://www.zoho.com"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={loading}
          autoComplete="off"
          required
        />
      </div>

      {validationError && (
        <p className="validation-error">{validationError}</p>
      )}

      <button
        id="enrich-btn"
        type="submit"
        className="btn btn-primary"
        disabled={loading}
      >
        {loading ? (
          <span className="btn-loading">
            <span className="spinner" aria-hidden="true" />
            Enriching…
          </span>
        ) : (
          "⚡ Enrich"
        )}
      </button>
    </form>
  );
}
