import os

# Google Drive Paths
# User confirmed G: is mapped to Google Drive
DRIVE_ROOT = r"G:\My Drive\Agentic-trials-data"

# Subdirectories
DATA_DIR = os.path.join(DRIVE_ROOT, "data")
ARCHIVE_DIR = os.path.join(DRIVE_ROOT, "reports_archive")

# Validations
if not os.path.exists(DRIVE_ROOT):
    print(f"WARNING: Drive path {DRIVE_ROOT} does not exist. Using local fallback.")
    DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_agent", "data")
    ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports_archive")

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)
