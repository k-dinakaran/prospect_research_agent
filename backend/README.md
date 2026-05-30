# Prospect Research Agent — Backend API

AI-powered B2B prospect research backend built with **FastAPI**.  
Accepts a company URL, scrapes the website, calls the Gemini AI pipeline, and returns a structured company profile.

---

## Project Overview

This backend wraps the enrichment pipeline (`app/enrichment.py`) in a production-ready REST API.  
It does **not** contain any AI logic itself — the intelligence lives entirely in the existing enrichment engine.

---

## Folder Structure

```
backend/
├── app/
│   ├── __init__.py        # Package marker
│   ├── main.py            # FastAPI app — routes & middleware
│   ├── schemas.py         # Pydantic request / response models
│   ├── storage.py         # JSON file persistence layer
│   └── enrichment.py      # Core AI enrichment pipeline (do not edit)
├── data/
│   └── results.json       # All saved enriched profiles
├── requirements.txt
├── .env                   # Your secrets (never commit)
├── .env.example           # Template for environment variables
├── README.md
└── test_enrichment.py     # Quick smoke test for the enrichment engine
```

---

## Environment Variables

| Variable         | Required | Description                       |
|------------------|----------|-----------------------------------|
| `GEMINI_API_KEY` | ✅ Yes   | Your Google Gemini API key        |

Copy `.env.example` to `.env` and fill in your key:

```bash
cp .env.example .env
# then edit .env and add your GEMINI_API_KEY
```

---

## Setup Instructions

> Prerequisites: Python 3.10+, pip

```powershell
# 1. Navigate into the backend folder
cd backend

# 2. Create and activate a virtual environment (Windows)
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your API key
#    Edit .env and set GEMINI_API_KEY=<your_key>
```

---

## Run Locally

```powershell
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload
```

The API will be available at:

- **Base URL**: `http://localhost:8000`
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

## API Endpoints

### `GET /health`

Liveness check.

**Response**
```json
{
  "status": "ok",
  "message": "Prospect Research API is running"
}
```

---

### `POST /enrich`

Enrich a company by URL.

**Request body**
```json
{
  "website_name": "Zoho",
  "url": "https://www.zoho.com"
}
```

| Field          | Type   | Required | Description                                          |
|----------------|--------|----------|------------------------------------------------------|
| `url`          | string | ✅ Yes   | Full company website URL                             |
| `website_name` | string | No       | Human-readable label (overrides the URL-derived name)|

**Example response** `200 OK`
```json
{
  "website_name": "Zoho",
  "company_name": "Zoho Corporation",
  "address": "4141 Hacienda Drive, Pleasanton, CA 94588",
  "mobile_number": "+1-888-900-9646",
  "mail": ["support@zoho.com"],
  "core_service": "Cloud-based business software suite including CRM, email, and project management",
  "target_customer": "Small and mid-sized businesses seeking affordable, integrated SaaS tools",
  "probable_pain_point": "Managing fragmented software stacks across sales, support, and finance teams",
  "outreach_opener": "Hi team, we noticed Zoho's broad CRM and workflow suite serves thousands of SMBs looking to consolidate their tooling."
}
```

**Error responses**

| Status | Reason                                   |
|--------|------------------------------------------|
| `422`  | Invalid or missing `url` field           |
| `500`  | Enrichment pipeline failure              |

---

### `GET /results`

Retrieve all previously enriched company profiles.

**Response** `200 OK` — array of `CompanyProfile` objects (empty array `[]` if none saved yet).

---

## Output Schema

Every enriched company strictly follows this schema:

```json
{
  "website_name": "string",
  "company_name": "string",
  "address": "string",
  "mobile_number": "string",
  "mail": ["string"],
  "core_service": "string",
  "target_customer": "string",
  "probable_pain_point": "string",
  "outreach_opener": "string"
}
```

Rules:
- No missing keys.
- No extra keys.
- Missing values are empty strings `""` (or `[]` for `mail`).
- `null` is never returned.

---

## Render Deployment

1. Push the `backend/` directory to a GitHub repository.
2. Go to [https://render.com](https://render.com) → **New Web Service**.
3. Connect your GitHub repo.
4. Set the following in the Render dashboard:

| Setting          | Value                                        |
|------------------|----------------------------------------------|
| **Root Directory** | `backend`                                  |
| **Build Command**  | `pip install -r requirements.txt`          |
| **Start Command**  | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **Environment**    | Add `GEMINI_API_KEY` as a secret env var   |

5. Deploy. Render will provide a public HTTPS URL automatically.

> **Note:** The `data/results.json` file lives on the ephemeral filesystem on Render.  
> Results will reset on each redeploy. Consider upgrading to a persistent store (SQLite with a mounted disk, or Supabase) for production use.
