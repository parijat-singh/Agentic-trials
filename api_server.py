from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import subprocess
import os
from typing import Optional
import sys

app = FastAPI(title="Stock Analysis API", description="API to trigger stock analysis pipeline with custom filters.")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    return RedirectResponse(url="/static/index.html")

class AnalyzeRequest(BaseModel):
    min_history: float = 5.0
    min_ipo: float = 5.0
    max_ipo: float = 10.0
    max_pe: Optional[float] = None
    max_pages: int = 200
    skip_scraper: bool = False

@app.post("/analyze")
def run_analysis(request: AnalyzeRequest):
    """
    Triggers the full analysis pipeline.
    This may take several minutes to complete.
    """
    # Construct command
    # Use sys.executable to ensure we use the same python environment
    cmd = [sys.executable, "run_pipeline.py"]
    
    cmd.append(f"--min-history={request.min_history}")
    cmd.append(f"--min-ipo={request.min_ipo}")
    cmd.append(f"--max-ipo={request.max_ipo}")
    cmd.append(f"--max-pages={request.max_pages}")
    
    if request.max_pe is not None:
        cmd.append(f"--max-pe={request.max_pe}")
        
    if request.skip_scraper:
        cmd.append("--skip-scraper")
        
    print(f"API Triggering Pipeline: {' '.join(cmd)}")
    
    try:
        # Run synchronous for now to return output
        # cwd should be the directory of this script (project root)
        cwd = os.path.dirname(os.path.abspath(__file__))
        
        # Cleanup old report to ensure we don't return stale data if pipeline fails silently (or was catching error)
        report_path = os.path.join(cwd, "FINAL_REPORT.md")
        if os.path.exists(report_path):
            try: os.remove(report_path)
            except: pass
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=cwd)
        
        # Read Report
        report_path = os.path.join(cwd, "FINAL_REPORT.md")
        if os.path.exists(report_path):
            with open(report_path, "r") as f:
                report_content = f.read()
            return {
                "status": "success", 
                "parameters": request.dict(),
                "report": report_content, 
                "stdout": result.stdout
            }
        else:
            return {
                "status": "warning", 
                "message": "Pipeline finished but Report not found.", 
                "stdout": result.stdout
            }
            
    except subprocess.CalledProcessError as e:
        # Return stdout/stderr even on failure for debugging
        return {
            "status": "error",
            "message": f"Pipeline failed. Exit Code: {e.returncode}",
            "stdout": e.stdout,
            "stderr": e.stderr
        }
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # Run slightly different port to avoid conflicts
    uvicorn.run(app, host="0.0.0.0", port=8000)
