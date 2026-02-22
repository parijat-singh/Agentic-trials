import os

# Local C: drive path for SQLite (avoids OneDrive/cloud sync I/O errors)
_DB_ROOT = os.path.join(os.environ.get("LOCALAPPDATA", "C:\\Users\\Public"), "stock-analysis")
os.makedirs(_DB_ROOT, exist_ok=True)
DB_PATH = os.path.join(_DB_ROOT, "stock_data.db")

# Cloud detection: use K_SERVICE (Cloud Run) or DATA_DIR env
if os.environ.get("K_SERVICE") or os.environ.get("DATA_DIR"):
    # Google Cloud Run or explicit cloud config
    _base = os.environ.get("DATA_DIR", "/tmp/app_data")
    DATA_DIR = os.path.join(_base, "data")
    ARCHIVE_DIR = os.path.join(_base, "reports_archive")
    DB_PATH = os.path.join(_base, "stock_data.db")  # Cloud: DB with data
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
elif os.path.exists(r"G:\My Drive\Agentic-trials-data"):
    # Google Drive (local dev)
    DRIVE_ROOT = r"G:\My Drive\Agentic-trials-data"
    DATA_DIR = os.path.join(DRIVE_ROOT, "data")
    ARCHIVE_DIR = os.path.join(DRIVE_ROOT, "reports_archive")
    # DB stays on C: (already set above) - avoids Google Drive sync issues
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
else:
    # Local fallback
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "stock_agent", "data")
    ARCHIVE_DIR = os.path.join(BASE_DIR, "reports_archive")
    # DB stays on C: (already set above) - avoids OneDrive sync issues
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
