# Local Development Setup

Run and test the Stock Analysis Pipeline on your machine before pushing to GitHub.

---

## Prerequisites

- Python 3.10 or 3.11
- (Optional) Google Drive path `G:\My Drive\Agentic-trials-data` for persistent data; otherwise uses `stock_agent/data` locally

## Database Location (Local)

The SQLite database is stored on the **local C: drive** to avoid cloud-sync I/O errors (OneDrive, Google Drive):

- **Path:** `%LOCALAPPDATA%\stock-analysis\stock_data.db`
- **Typical:** `C:\Users\<you>\AppData\Local\stock-analysis\stock_data.db`

Data dir and reports may be in the project or on Google Drive; only the DB uses C:.

---

## 1. Create Virtual Environment

```powershell
cd c:\Users\user\OneDrive\Documents\Coding\Agentic-trials
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 2. Run the API Server Locally

**Option A: VS Code**  
- Press F5 or use Run and Debug, choose **"API Server (Stock Analysis)"**

**Option B: Terminal**
```powershell
.\venv\Scripts\Activate.ps1
python api_server.py
```

App URL: **http://localhost:8081**

---

## 3. Run Tests

```powershell
pytest tests/ -v --tb=short
```

With coverage:
```powershell
pytest tests/ -v --tb=short --cov=. --cov-report=term-missing
```

Vulnerability check:
```powershell
pip install pip-audit
pip-audit
```

---

## 4. Run Pipeline (CLI)

```powershell
python run_pipeline.py --skip-scraper
```

---

## 5. Before Committing

1. `pytest tests/ -v`
2. `pip-audit`
3. Commit and push

CI will run tests, vuln scan, and deploy to Cloud Run on push to main.
