from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import subprocess
import os
from typing import Optional, List
import sys
import threading
import time

app = FastAPI(title="Stock Analysis API", description="API to trigger stock analysis pipeline with custom filters.")

app.mount("/static", StaticFiles(directory="static"), name="static")

# Global State
class PipelineState:
    process: Optional[subprocess.Popen] = None
    logs: List[str] = []
    status: str = "idle" # idle, running, completed, error, stopped
    return_code: Optional[int] = None

state = PipelineState()

@app.get("/")
async def read_root():
    return RedirectResponse(url="/static/index.html")

class AnalyzeRequest(BaseModel):
    min_history: float = 5.0
    min_ipo: float = 5.0
    max_ipo: float = 10.0
    min_market_cap: Optional[float] = None
    max_pe: Optional[float] = None
    max_pages: int = 200
    skip_scraper: bool = False

def run_pipeline_background(cmd, cwd):
    """
    Runs the pipeline in background, captures output, and updates state.
    """
    global state
    state.status = "running"
    state.logs = []
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
            # bufsize=1 means line buffered
            p = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True, 
                cwd=cwd,
                bufsize=1,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            state.process = p
            
            # Read logs line by line
            for line in iter(p.stdout.readline, ''):
                if line:
                    state.logs.append(line)
                    log_file.write(line)
                    log_file.flush() # Ensure it's written immediately
                    
            p.stdout.close()
            return_code = p.wait()
            state.return_code = return_code
            state.process = None
            
            if return_code == 0:
                state.status = "completed"
                msg = f"\n[API] Pipeline finished successfully.\n"
                state.logs.append(msg)
                log_file.write(msg)
            else:
                # Check if it was killed manually
                if return_code == 15 or return_code == 1: # SIGTERM or Error
                     state.status = "error" # Or stopped?
                     msg = f"\n[API] Pipeline finished with exit code {return_code}.\n"
                     state.logs.append(msg)
                     log_file.write(msg)

    except Exception as e:
        state.status = "error"
        msg = f"\n[API] Error launching process: {str(e)}\n"
        state.logs.append(msg)
        try:
            with open(log_file_path, "a") as lf:
                lf.write(msg)
        except: pass
        state.process = None

@app.post("/analyze")
def run_analysis(request: AnalyzeRequest):
    """
    Triggers the full analysis pipeline in BACKGROUND.
    Returns immediate success if started.
    """
    global state
    
    if state.status == "running":
        raise HTTPException(status_code=400, detail="Pipeline is already running.")
        
    # Construct command
    cmd = [sys.executable, "-u", "run_pipeline.py"]
    
    cmd.append(f"--min-history={request.min_history}")
    cmd.append(f"--min-ipo={request.min_ipo}")
    cmd.append(f"--max-ipo={request.max_ipo}")
    cmd.append(f"--max-pages={request.max_pages}")
    
    if request.max_pe is not None:
        cmd.append(f"--max-pe={request.max_pe}")

    if request.min_market_cap is not None:
        cmd.append(f"--min-market-cap={request.min_market_cap}")
        
    if request.skip_scraper:
        cmd.append("--skip-scraper")
        
    print(f"API Triggering Pipeline: {' '.join(cmd)}")
    
    cwd = os.path.dirname(os.path.abspath(__file__))
    
    # Start Thread
    t = threading.Thread(target=run_pipeline_background, args=(cmd, cwd))
    t.start()
    
    return {"status": "started", "message": "Pipeline started in background."}

@app.get("/status")
def get_status():
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
        "logs": "".join(state.logs),
        "report": report_content
    }

@app.post("/stop")
def stop_process():
    """
    Terminates the running process.
    """
    global state
    if state.process:
        print("API: Stopping process...")
        state.logs.append("\n[API] User requested STOP. Terminating process...\n")
        try:
            # On Windows, p.terminate() is usually enough, but sometimes we need kill
            state.process.terminate()
            # If it doesn't die quickly?
            # state.process.kill() 
        except Exception as e:
            state.logs.append(f"\n[API] Error stopping process: {e}\n")
            
        state.status = "stopped"
        return {"status": "stopped", "message": "Process termination requested."}
    else:
        return {"status": "idle", "message": "No process running."}

if __name__ == "__main__":
    import uvicorn
    # Run slightly different port to avoid conflicts
    uvicorn.run(app, host="0.0.0.0", port=8081)
