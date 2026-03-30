"""
Centralized paths and config. Override via env vars so the app works from any CWD.
"""
import os

# Base data directory (e.g. for uploads, ChromaDB, SQLite). Set CLAUSE_DATA_DIR to override.
DATA_DIR = os.environ.get("CLAUSE_DATA_DIR", "data")
# Max upload size in MB (set CLAUSE_MAX_UPLOAD_MB to override).
MAX_UPLOAD_MB = int(os.environ.get("CLAUSE_MAX_UPLOAD_MB", "50"))

UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
CHROMA_PATH = os.path.join(DATA_DIR, "chroma")
DB_PATH = os.path.join(DATA_DIR, "app.db")


def ensure_dirs():
    """Create data directories if they don't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(CHROMA_PATH, exist_ok=True)
