/**
 * API client for the Prospect Research backend.
 * Base URL is controlled via the VITE_API_BASE_URL env variable.
 */

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

/**
 * Internal helper — fetch with JSON parsing and readable error throwing.
 */
async function request(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;

  let response;
  try {
    response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (networkErr) {
    throw new Error(
      `Cannot reach the backend at ${API_BASE_URL}. Make sure it is running.`
    );
  }

  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(`Server returned a non-JSON response (status ${response.status}).`);
  }

  if (!response.ok) {
    const detail =
      data?.detail ||
      data?.message ||
      `Request failed with status ${response.status}.`;
    throw new Error(detail);
  }

  return data;
}

/**
 * POST /enrich
 * @param {{ website_name: string, url: string }} payload
 * @returns {Promise<CompanyProfile>}
 */
export async function enrichCompany(payload) {
  return request("/enrich", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * GET /results
 * @returns {Promise<CompanyProfile[]>}
 */
export async function getResults() {
  return request("/results");
}

/**
 * GET /health
 * @returns {Promise<{ status: string, message: string }>}
 */
export async function healthCheck() {
  return request("/health");
}
