"""
Prospect Research API — FastAPI application entry point.

Endpoints
---------
GET  /health   — liveness check
POST /enrich   — enrich a single company URL
GET  /results  — retrieve all saved enriched profiles

Run locally:
    cd backend
    uvicorn app.main:app --reload

Swagger UI: http://localhost:8000/docs
"""

import logging
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.enrichment import enrich_company
from app.schemas import CompanyProfile, EnrichRequest
from app.storage import read_results, save_result

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App & CORS
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Prospect Research API",
    description=(
        "AI-powered company enrichment backend. "
        "Accepts a company URL and returns a structured prospect profile."
    ),
    version="1.0.0",
)

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    # Permissive during hackathon development — tighten for production.
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get(
    "/health",
    summary="Health check",
    tags=["Utility"],
)
def health_check() -> JSONResponse:
    """Return API liveness status."""
    return JSONResponse(
        content={"status": "ok", "message": "Prospect Research API is running"}
    )


@app.post(
    "/enrich",
    response_model=CompanyProfile,
    summary="Enrich a company by URL",
    tags=["Enrichment"],
)
def enrich(request: EnrichRequest) -> CompanyProfile:
    """
    Scrape and enrich a company website.

    - Calls the existing `enrich_company(url)` pipeline.
    - Overrides `website_name` with the caller-supplied label if provided.
    - Validates output against the strict `CompanyProfile` schema.
    - Persists the result to `data/results.json`.

    Returns the saved `CompanyProfile` on success.
    Raises HTTP 422 on invalid input, HTTP 500 on enrichment failure.
    """
    logger.info("POST /enrich  url=%s  website_name=%r", request.url, request.website_name)

    try:
        raw_profile: dict = enrich_company(request.url)
    except Exception as exc:
        logger.error("Enrichment pipeline error for %s: %s", request.url, exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Enrichment failed. Please check the URL and try again.",
        ) from exc

    if not isinstance(raw_profile, dict):
        logger.error("enrich_company returned non-dict: %r", raw_profile)
        raise HTTPException(
            status_code=500,
            detail="Enrichment returned an unexpected result type.",
        )

    # Override website_name when caller supplies one.
    if request.website_name and request.website_name.strip():
        raw_profile["website_name"] = request.website_name.strip()

    # Serialize through CompanyProfile to enforce schema & strip extra keys.
    try:
        profile = CompanyProfile(**raw_profile)
    except Exception as exc:
        logger.error("Schema validation failed: %s — raw=%r", exc, raw_profile)
        raise HTTPException(
            status_code=500,
            detail="Enrichment result failed schema validation.",
        ) from exc

    # Persist to JSON storage.
    try:
        save_result(profile.model_dump())
    except Exception as exc:
        # Storage failure should not block the API response.
        logger.warning("Failed to persist result for %s: %s", request.url, exc)

    logger.info("Enrichment complete for %s", request.url)
    return profile


@app.get(
    "/results",
    response_model=List[CompanyProfile],
    summary="Retrieve all saved profiles",
    tags=["Results"],
)
def get_results() -> List[CompanyProfile]:
    """
    Return every enriched company profile saved in `data/results.json`.
    Returns an empty list when no profiles have been saved yet.
    """
    try:
        records = read_results()
    except Exception as exc:
        logger.error("Failed to read results: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve saved results.",
        ) from exc

    profiles: List[CompanyProfile] = []
    for record in records:
        try:
            profiles.append(CompanyProfile(**record))
        except Exception:
            # Skip individual corrupted records rather than failing the whole list.
            logger.warning("Skipping malformed record: %r", record)

    return profiles
