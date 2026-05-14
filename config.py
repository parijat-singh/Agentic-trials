import os

# Patch curl_cffi (used by yfinance 1.x) to skip SSL verification on Windows.
# Python's SSL layer cannot access the Windows system CA store, causing cert
# errors against Yahoo Finance. This is safe for outbound read-only API calls.
try:
    import curl_cffi.requests as _cr
    _orig_cffi_init = _cr.Session.__init__
    def _patched_cffi_init(self, *args, **kwargs):
        kwargs.setdefault("verify", False)
        _orig_cffi_init(self, *args, **kwargs)
    _cr.Session.__init__ = _patched_cffi_init
except ImportError:
    pass

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

# ETF storage: cloud/G Drive for local; /tmp for Cloud Run
if os.environ.get("ETF_STORAGE_ROOT"):
    ETF_STORAGE_ROOT = os.environ["ETF_STORAGE_ROOT"]
elif os.path.exists(r"G:\My Drive\Agentic-trials-data"):
    ETF_STORAGE_ROOT = os.path.join(r"G:\My Drive\Agentic-trials-data", "etf_data")
else:
    ETF_STORAGE_ROOT = os.path.join(DATA_DIR, "etf_data")
ETF_CACHE_DB = os.path.join(ETF_STORAGE_ROOT, "etf", "etf_cache.db")
ETF_SESSIONS_DIR = os.path.join(ETF_STORAGE_ROOT, "sessions")
ETF_ARCHIVE_DIR = os.path.join(ETF_STORAGE_ROOT, "reports_archive")
os.makedirs(os.path.dirname(ETF_CACHE_DB), exist_ok=True)
os.makedirs(ETF_SESSIONS_DIR, exist_ok=True)
os.makedirs(ETF_ARCHIVE_DIR, exist_ok=True)

# Mutual Fund storage: same root pattern as ETF
if os.environ.get("MF_STORAGE_ROOT"):
    MF_STORAGE_ROOT = os.environ["MF_STORAGE_ROOT"]
elif os.path.exists(r"G:\My Drive\Agentic-trials-data"):
    MF_STORAGE_ROOT = os.path.join(r"G:\My Drive\Agentic-trials-data", "mf_data")
elif os.environ.get("K_SERVICE") or os.environ.get("DATA_DIR"):
    MF_STORAGE_ROOT = os.path.join(os.environ.get("DATA_DIR", "/tmp/app_data"), "mf_data")
else:
    MF_STORAGE_ROOT = os.path.join(DATA_DIR, "mf_data")
# MF cache DB lives on C: (same as stock_data.db) — avoids Google Drive sync I/O errors
MF_CACHE_DB = os.path.join(_DB_ROOT, "mf_cache.db")
MF_SESSIONS_DIR = os.path.join(MF_STORAGE_ROOT, "sessions")
MF_ARCHIVE_DIR = os.path.join(MF_STORAGE_ROOT, "reports_archive")
os.makedirs(os.path.dirname(MF_CACHE_DB), exist_ok=True)
os.makedirs(MF_SESSIONS_DIR, exist_ok=True)
os.makedirs(MF_ARCHIVE_DIR, exist_ok=True)
