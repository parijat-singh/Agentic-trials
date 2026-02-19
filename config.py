import os

# Google Drive Paths
# User confirmed G: is mapped to Google Drive
DRIVE_ROOT = r"G:\My Drive\Agentic-trials-data"

# Subdirectories
DATA_DIR = os.path.join(DRIVE_ROOT, "data")
ARCHIVE_DIR = os.path.join(DRIVE_ROOT, "reports_archive")
DB_PATH = os.path.join(DRIVE_ROOT, "stock_data.db")

# Validations
if not os.path.exists(DRIVE_ROOT):
    print(f"WARNING: Drive path {DRIVE_ROOT} does not exist. Using local fallback.")
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "stock_agent", "data")
    ARCHIVE_DIR = os.path.join(BASE_DIR, "reports_archive")
    DB_PATH = os.path.join(BASE_DIR, "stock_agent", "stock_data.db")

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)
