"""
JSON file storage for enriched company profiles.

All functions are safe to call at any time:
- Missing directories/files are created automatically.
- Corrupted or empty JSON is silently reset to an empty list.
- UTF-8 encoding is used throughout.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

# Resolve relative to this file so the backend works from any cwd.
_APP_DIR = Path(__file__).parent          # backend/app/
_BACKEND_DIR = _APP_DIR.parent            # backend/
_DATA_DIR = _BACKEND_DIR / "data"
_RESULTS_FILE = _DATA_DIR / "results.json"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def ensure_storage() -> None:
    """
    Guarantee that data/results.json exists and contains a valid JSON array.
    Called automatically by read/write helpers — callers do not need to invoke
    this manually, but it is safe to do so.
    """
    _DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not _RESULTS_FILE.exists():
        _RESULTS_FILE.write_text("[]", encoding="utf-8")
        return

    # Validate existing content; reset on any parse error.
    try:
        raw = _RESULTS_FILE.read_text(encoding="utf-8").strip()
        if not raw:
            raise ValueError("empty file")
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            raise ValueError("not a list")
    except Exception:
        _RESULTS_FILE.write_text("[]", encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_results() -> List[Dict[str, Any]]:
    """
    Return all saved profiles.
    Returns an empty list if the storage file is missing or corrupted.
    """
    ensure_storage()
    try:
        raw = _RESULTS_FILE.read_text(encoding="utf-8").strip()
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Append a single enriched profile to results.json and return it.
    Thread-safety note: for a single-worker hackathon deployment this is fine;
    add a filelock if multi-worker Gunicorn is used later.
    """
    ensure_storage()
    records = read_results()
    records.append(result)

    _RESULTS_FILE.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return result
