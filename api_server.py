import re

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import subprocess
import os
from typing import Optional, List, Dict
import sys
import threading
import time

import config  # must be top-level so config.ETF_SESSIONS_DIR is available in all endpoints

app = FastAPI(title="Stock Analysis API", description="API to trigger stock analysis pipeline with custom filters.")

# ── Auth ──────────────────────────────────────────────────────────────────────
# Set the SECRET_API_KEY environment variable to require authentication on all
# pipeline endpoints.  If the variable is unset the server runs in open mode
# (convenient for local dev).  When set, callers must pass the key as either:
#   • HTTP header:  X-API-Key: <key>
#   • Query param:  ?api_key=<key>   (fallback for tools that can't set headers)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def _require_api_key(key: Optional[str] = Security(_api_key_header)) -> None:
    expected = os.environ.get("SECRET_API_KEY")
    if expected and key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

# ── Session ID validation ─────────────────────────────────────────────────────
_SESSION_ID_RE = re.compile(r"^[a-f0-9]{8}$")

def _validate_session_id(session_id: str, label: str = "session") -> None:
    """Reject session IDs that could be used for path traversal."""
    if not _SESSION_ID_RE.fullmatch(session_id):
        raise HTTPException(status_code=400, detail=f"Invalid {label} ID format")


@app.middleware("http")
async def add_no_cache_static(request, call_next):
    """Prevent caching of static assets so users always get the latest UI."""
    response = await call_next(request)
    if request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


app.mount("/static", StaticFiles(directory="static"), name="static")

# Global State
class PipelineState:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.logs: List[str] = []
        self.status: str = "idle"  # idle, running, completed, error, stopped
        self.return_code: Optional[int] = None
        self._lock = threading.Lock()

    def append_log(self, line: str) -> None:
        with self._lock:
            self.logs.append(line)

    def reset_logs(self) -> None:
        with self._lock:
            self.logs = []

    def get_logs_str(self) -> str:
        with self._lock:
            return "".join(self.logs)

state = PipelineState()


def _cleanup_old_sessions(sessions: Dict[str, Dict], max_age_hours: int = 24) -> None:
    """Evict sessions older than max_age_hours to prevent unbounded memory growth."""
    cutoff = time.time() - max_age_hours * 3600
    stale = [k for k, v in sessions.items() if v.get("_created", 0) < cutoff]
    for k in stale:
        del sessions[k]

@app.get("/")
async def read_root():
    return RedirectResponse(url="/static/index.html")

class HoldingItem(BaseModel):
    symbol: str
    amount: float

class PortfolioCompareRequest(BaseModel):
    holdings: List[HoldingItem]
    start_date: str
    end_date: str

class AnalyzeRequest(BaseModel):
    min_history: float = 5.0
    max_ipo: float = 10.0
    min_market_cap: Optional[float] = None
    max_pe_by_sector: Optional[Dict[str, float]] = None  # e.g. {"Technology": 30, "Healthcare": 25}
    min_price: Optional[float] = None
    no_exchange_filter: bool = False
    industries: Optional[List[str]] = None
    max_pages: int = 200
    skip_scraper: bool = False


class ETFAnalyzeRequest(BaseModel):
    max_expense_ratio: float = 0.005
    min_aum: float = 1e9
    min_history_years: float = 3.0
    nyse_nasdaq_only: bool = True
    skip_scraper: bool = False
    skip_fetcher: bool = False
    max_pages: int = 40  # number of scraper pages (~100 ETFs each)


class MFAnalyzeRequest(BaseModel):
    max_expense_ratio: float = 0.015   # 1.5 % as decimal
    min_aum: float = 1e9
    min_history_years: float = 5.0
    categories: Optional[List[str]] = None   # e.g. ["Equity", "Bond"]
    skip_scraper: bool = False
    skip_fetcher: bool = False
    max_pages: int = 80  # number of scraper pages (~100 MFs each)


etf_sessions: Dict[str, Dict] = {}
mf_sessions:  Dict[str, Dict] = {}


def run_etf_pipeline_background(session_id: str, req: ETFAnalyzeRequest):
    _cleanup_old_sessions(etf_sessions)
    etf_sessions[session_id] = {"status": "running", "logs": [], "report_path": None, "_created": time.time()}
    cwd = os.path.dirname(os.path.abspath(__file__))
    session_dir = os.path.join(config.ETF_SESSIONS_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    log_file_path = os.path.join(session_dir, "pipeline.log")
    cmd = [sys.executable, "-u", "run_etf_pipeline.py", f"--session-id={session_id}",
           f"--max-expense-ratio={req.max_expense_ratio*100}", f"--min-aum={req.min_aum}",
           f"--min-history-years={req.min_history_years}", f"--max-pages={req.max_pages}"]
    if not req.nyse_nasdaq_only:
        cmd.append("--no-nyse-nasdaq")
    if req.skip_scraper:
        cmd.append("--skip-scraper")
    if req.skip_fetcher:
        cmd.append("--skip-fetcher")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    def run():
        try:
            with open(log_file_path, "w", encoding="utf-8") as log_file:
                log_file.write(f"--- ETF Pipeline started {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                log_file.write(f"Command: {' '.join(cmd)}\n\n")
                log_file.flush()
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, cwd=cwd, bufsize=1, env=env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
                for line in iter(p.stdout.readline, ""):
                    if line:
                        etf_sessions[session_id]["logs"].append(line)
                        log_file.write(line)
                        log_file.flush()
                p.stdout.close()
                rc = p.wait()
                etf_sessions[session_id]["status"] = "completed" if rc == 0 else "error"
                etf_sessions[session_id]["report_path"] = os.path.join(config.ETF_SESSIONS_DIR, session_id, "ETF_REPORT.md")
                log_file.write(f"\n--- Exit code: {rc} ---\n")
        except Exception as e:
            etf_sessions[session_id]["status"] = "error"
            err_msg = f"\n[API] Error: {str(e)}\n"
            etf_sessions[session_id]["logs"].append(err_msg)
            try:
                with open(log_file_path, "a", encoding="utf-8") as log_file:
                    log_file.write(err_msg)
            except Exception:
                pass

    threading.Thread(target=run).start()


def run_pipeline_background(cmd, cwd):
    """
    Runs the pipeline in background, captures output, and updates state.
    """
    global state
    state.status = "running"
    state.reset_logs()
    state.return_code = None
    
    log_file_path = os.path.join(cwd, "pipeline.log")
    
    try:
        # Cleanup old report
        report_path = os.path.join(cwd, "FINAL_REPORT.md")
        if os.path.exists(report_path):
            try: os.remove(report_path)
            except: pass

        # Open log file
        with open(log_file_path, "w") as log_file:
            log_file.write(f"--- Pipeline Started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            log_file.flush()
            
            # Start Process with pipes for stdout/stderr
            # bufsize=1 = line buffered; PYTHONUNBUFFERED for child processes
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            p = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=cwd,
                bufsize=1,
                env=env,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            state.process = p
            
            # Read logs line by line
            for line in iter(p.stdout.readline, ''):
                if line:
                    state.append_log(line)
                    log_file.write(line)
                    log_file.flush()

            p.stdout.close()
            return_code = p.wait()
            state.return_code = return_code
            state.process = None

            if return_code == 0:
                state.status = "completed"
                msg = "\n[API] Pipeline finished successfully.\n"
                state.append_log(msg)
                log_file.write(msg)
            else:
                if return_code == 15 or return_code == 1:  # SIGTERM or Error
                    state.status = "error"
                    msg = f"\n[API] Pipeline finished with exit code {return_code}.\n"
                    state.append_log(msg)
                    log_file.write(msg)

    except Exception as e:
        state.status = "error"
        msg = f"\n[API] Error launching process: {str(e)}\n"
        state.append_log(msg)
        try:
            with open(log_file_path, "a") as lf:
                lf.write(msg)
        except: pass
        state.process = None

@app.post("/analyze")
async def run_analysis(req: AnalyzeRequest, _: None = Depends(_require_api_key)):
    """
    Triggers the full analysis pipeline in BACKGROUND.
    Returns immediate success if started.
    """
    global state

    if state.status == "running":
        raise HTTPException(status_code=400, detail="Pipeline is already running.")

    # Construct command
    cmd = [sys.executable, "-u", "run_pipeline.py"]
    
    cmd.append(f"--min-history={req.min_history}")
    cmd.append(f"--min-ipo={req.min_history}")
    cmd.append(f"--max-ipo={req.max_ipo}")
    cmd.append(f"--max-pages={req.max_pages}")
    
    if req.max_pe_by_sector:
        import json
        cmd.append(f"--max-pe-by-sector={json.dumps(req.max_pe_by_sector)}")

    if req.min_market_cap is not None:
        cmd.append(f"--min-market-cap={req.min_market_cap}")
    if req.min_price is not None:
        cmd.append(f"--min-price={req.min_price}")
    if req.no_exchange_filter:
        cmd.append("--no-exchange-filter")
    industries = req.industries if req.industries is not None else []
    industries_str = ",".join(str(s).strip() for s in industries if s) if isinstance(industries, list) else ""
    if isinstance(industries, list) and len(industries) > 0 and industries_str:
        cmd.append(f"--industries={industries_str}")

    if req.skip_scraper:
        cmd.append("--skip-scraper")

    cwd = os.path.dirname(os.path.abspath(__file__))
    
    # Start Thread
    t = threading.Thread(target=run_pipeline_background, args=(cmd, cwd))
    t.start()
    
    return {"status": "started", "message": "Pipeline started in background."}

@app.post("/portfolio-compare")
async def portfolio_compare(req: PortfolioCompareRequest, _: None = Depends(_require_api_key)):
    """
    Compare a custom portfolio against S&P 500 (SPY) for a given date range.
    Returns metrics (return, volatility, sharpe, alpha, beta) and time series for charting.
    """
    try:
        import portfolio_compare as pc
        holdings = [{"symbol": h.symbol, "amount": h.amount} for h in req.holdings]
        result = pc.run_portfolio_compare(holdings, req.start_date, req.end_date)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/status")
def get_status(_: None = Depends(_require_api_key)):
    """
    Returns current status and full logs.
    """
    global state
    
    # Check if report exists if completed
    report_content = None
    if state.status == "completed":
        cwd = os.path.dirname(os.path.abspath(__file__))
        report_path = os.path.join(cwd, "FINAL_REPORT.md")
        if os.path.exists(report_path):
            with open(report_path, "r") as f:
                report_content = f.read()
    
    return {
        "status": state.status,
        "logs": state.get_logs_str(),
        "report": report_content
    }

def run_mf_pipeline_background(session_id: str, req: MFAnalyzeRequest):
    _cleanup_old_sessions(mf_sessions)
    mf_sessions[session_id] = {"status": "running", "logs": [], "report_path": None, "_created": time.time()}
    cwd = os.path.dirname(os.path.abspath(__file__))
    session_dir = os.path.join(config.MF_SESSIONS_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    log_file_path = os.path.join(session_dir, "pipeline.log")
    cmd = [
        sys.executable, "-u", "run_mf_pipeline.py",
        f"--session-id={session_id}",
        f"--max-expense-ratio={req.max_expense_ratio * 100}",
        f"--min-aum={req.min_aum}",
        f"--min-history-years={req.min_history_years}",
        f"--max-pages={req.max_pages}",
    ]
    if req.categories:
        cmd.append(f"--categories={','.join(req.categories)}")
    if req.skip_scraper:
        cmd.append("--skip-scraper")
    if req.skip_fetcher:
        cmd.append("--skip-fetcher")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    def run():
        try:
            with open(log_file_path, "w", encoding="utf-8") as log_file:
                log_file.write(f"--- MF Pipeline started {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                log_file.write(f"Command: {' '.join(cmd)}\n\n")
                log_file.flush()
                p = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, cwd=cwd, bufsize=1, env=env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                )
                for line in iter(p.stdout.readline, ""):
                    if line:
                        mf_sessions[session_id]["logs"].append(line)
                        log_file.write(line)
                        log_file.flush()
                p.stdout.close()
                rc = p.wait()
                mf_sessions[session_id]["status"] = "completed" if rc == 0 else "error"
                mf_sessions[session_id]["report_path"] = os.path.join(
                    config.MF_SESSIONS_DIR, session_id, "MF_REPORT.md"
                )
                log_file.write(f"\n--- Exit code: {rc} ---\n")
        except Exception as e:
            mf_sessions[session_id]["status"] = "error"
            err_msg = f"\n[API] Error: {str(e)}\n"
            mf_sessions[session_id]["logs"].append(err_msg)
            try:
                with open(log_file_path, "a", encoding="utf-8") as lf:
                    lf.write(err_msg)
            except Exception:
                pass

    threading.Thread(target=run).start()


@app.post("/etf-analyze")
async def run_etf_analysis(req: ETFAnalyzeRequest, _: None = Depends(_require_api_key)):
    import uuid
    session_id = str(uuid.uuid4())[:8]
    run_etf_pipeline_background(session_id, req)
    return {"status": "started", "session_id": session_id}


@app.get("/etf-status/{session_id}")
def get_etf_status(session_id: str, _: None = Depends(_require_api_key)):
    _validate_session_id(session_id, "ETF session")
    if session_id not in etf_sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    s = etf_sessions[session_id]
    report_content = None
    if s["status"] == "completed" and s.get("report_path") and os.path.exists(s["report_path"]):
        with open(s["report_path"], "r") as f:
            report_content = f.read()
    log_path = os.path.join(config.ETF_SESSIONS_DIR, session_id, "pipeline.log")
    return {"status": s["status"], "logs": "".join(s["logs"]), "report": report_content, "log_file": log_path}


@app.get("/etf-log/{session_id}")
def get_etf_log(session_id: str, _: None = Depends(_require_api_key)):
    """Return pipeline.log content for a session (for investigation)."""
    _validate_session_id(session_id, "ETF session")
    log_path = os.path.join(config.ETF_SESSIONS_DIR, session_id, "pipeline.log")
    if not os.path.exists(log_path):
        raise HTTPException(status_code=404, detail=f"Log not found for session {session_id}")
    with open(log_path, "r", encoding="utf-8") as f:
        return {"session_id": session_id, "log": f.read()}


# ── Mutual Fund endpoints ─────────────────────────────────────────────────────

@app.post("/mf-analyze")
async def run_mf_analysis(req: MFAnalyzeRequest, _: None = Depends(_require_api_key)):
    import uuid
    session_id = str(uuid.uuid4())[:8]
    run_mf_pipeline_background(session_id, req)
    return {"status": "started", "session_id": session_id}


@app.get("/mf-status/{session_id}")
def get_mf_status(session_id: str, _: None = Depends(_require_api_key)):
    _validate_session_id(session_id, "MF session")
    if session_id not in mf_sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    s = mf_sessions[session_id]
    report_content = None
    if s["status"] == "completed" and s.get("report_path") and os.path.exists(s["report_path"]):
        with open(s["report_path"], "r", encoding="utf-8") as f:
            report_content = f.read()
    log_path = os.path.join(config.MF_SESSIONS_DIR, session_id, "pipeline.log")
    return {
        "status": s["status"],
        "logs": "".join(s["logs"]),
        "report": report_content,
        "log_file": log_path,
    }


@app.get("/mf-log/{session_id}")
def get_mf_log(session_id: str, _: None = Depends(_require_api_key)):
    """Return pipeline.log content for a MF session."""
    _validate_session_id(session_id, "MF session")
    log_path = os.path.join(config.MF_SESSIONS_DIR, session_id, "pipeline.log")
    if not os.path.exists(log_path):
        raise HTTPException(status_code=404, detail=f"Log not found for session {session_id}")
    with open(log_path, "r", encoding="utf-8") as f:
        return {"session_id": session_id, "log": f.read()}


@app.post("/stop")
def stop_process(_: None = Depends(_require_api_key)):
    """Terminate the running stock pipeline process."""
    global state
    proc = state.process
    if proc:
        state.append_log("\n[API] User requested STOP. Terminating process...\n")
        try:
            proc.terminate()
            # Wait up to 5 s for a clean exit; escalate to SIGKILL if needed
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
        except Exception as e:
            state.append_log(f"\n[API] Error stopping process: {e}\n")
        # Set status only after the process has actually exited
        state.status = "stopped"
        state.process = None
        return {"status": "stopped", "message": "Process terminated."}
    else:
        return {"status": "idle", "message": "No process running."}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8081))
    uvicorn.run(app, host="0.0.0.0", port=port)
