"""Shared paths and credentials.

Data never live in the repository. By default the scripts read and write in
``data/`` at the repository root (ignored by git); set ROME_SHOPS_DATA to use
another folder.
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("ROME_SHOPS_DATA", REPO / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
S = str(DATA_DIR) + "/"   # prefix used by the scripts when building file paths


def google_key():
    """Google Places API key from GOOGLE_PLACES_API_KEY or ~/.google_places_key."""
    key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if key:
        return key.strip()
    path = Path.home() / ".google_places_key"
    if path.exists():
        return path.read_text().strip()
    raise SystemExit("Set GOOGLE_PLACES_API_KEY or create ~/.google_places_key")
