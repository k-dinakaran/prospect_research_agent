# Prospect Research Agent — Frontend

React + Vite frontend for the AI-powered B2B prospect research tool.  
Connects to the existing FastAPI backend to enrich company profiles in real time.

---

## Project Overview

This frontend provides a clean dark-themed SaaS UI where users can:

- Enter a company URL and optional website name
- Trigger AI enrichment via `POST /enrich`
- View the returned structured company profile
- Browse all previously saved profiles via `GET /results`

---

## Folder Structure

```
frontend/
├── src/
│   ├── App.jsx                  # Root component — state, layout, handlers
│   ├── api.js                   # fetch-based API client
│   ├── main.jsx                 # Vite/React entry point
│   ├── index.css                # Global dark SaaS stylesheet
│   └── components/
│       ├── EnrichForm.jsx       # Controlled form for URL input
│       ├── ResultCard.jsx       # Single enriched profile card
│       └── ResultsList.jsx      # Grid of ResultCards + empty state
├── .env                         # Local environment variables (git-ignored)
├── .env.example                 # Template — safe to commit
└── README.md
```

---

## Environment Variables

| Variable             | Description                     | Default                    |
|----------------------|---------------------------------|----------------------------|
| `VITE_API_BASE_URL`  | FastAPI backend base URL        | `http://127.0.0.1:8000`    |

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

---

## Setup & Run

> Prerequisite: Node.js 18+

```bash
cd frontend
npm install
npm run dev
```

The app runs at **http://localhost:5173**.

---

## Backend Dependency

The frontend requires the FastAPI backend to be running at the URL set in `VITE_API_BASE_URL`.

Start the backend first:

```powershell
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload
```

---

## API Endpoints Used

| Method | Endpoint   | Description                        |
|--------|------------|------------------------------------|
| POST   | `/enrich`  | Enrich a company by URL            |
| GET    | `/results` | Retrieve all saved profiles        |
| GET    | `/health`  | Backend liveness check             |

---

## Deploying to Vercel

1. Push the repo to GitHub.
2. Go to [https://vercel.com](https://vercel.com) → **Add New Project**.
3. Select the repo and set the **Root Directory** to `frontend`.
4. Add the environment variable:
   - `VITE_API_BASE_URL` → your Render backend URL (e.g. `https://your-api.onrender.com`)
5. Deploy. Vercel auto-builds with `npm run build` and serves the static output.

## Deploying to Netlify

1. Go to [https://netlify.com](https://netlify.com) → **Add New Site → Import from Git**.
2. Set **Base directory** to `frontend`.
3. Set **Build command** to `npm run build`.
4. Set **Publish directory** to `frontend/dist`.
5. Add env var `VITE_API_BASE_URL` in Site Settings → Environment.
6. Deploy.

> **CORS note:** Make sure the deployed backend's CORS allows your Vercel/Netlify domain.
