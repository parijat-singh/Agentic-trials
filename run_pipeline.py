import os
import subprocess
import sys

def run_script(path, description, args=None):
    print(f"\n{'='*60}")
    print(f"RUNNING: {description}")
    print(f"{'='*60}")
    
    if not os.path.exists(path):
        print(f"Error: Script not found: {path}")
        return False
        
    try:
        # Run the script and stream output
        cmd = [sys.executable, path]
        if args:
            cmd.extend(args)
            
        result = subprocess.run(cmd, check=True, cwd=os.path.dirname(path))
        print(f"SUCCESS: {description}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"FAILURE: {description} (Exit Code: {e.returncode})")
        return False

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    scripts = [
        (os.path.join(root_dir, "financial_engine", "main.py"), "Module 2: Financial Engine (Sharpe Ranking)"),
        (os.path.join(root_dir, "portfolio_optimizer", "main.py"), "Module 3: Portfolio Optimization"),
        (os.path.join(root_dir, "backtester", "main.py"), "Module 4: Backtester"),
        (os.path.join(root_dir, "report_generator", "create_report.py"), "Final Reporting")
    ]
    
    # Check for custom description
    description = "Standard Pipeline Run"
    if len(sys.argv) > 1:
        description = sys.argv[1]
        
    print(f"Starting Full Analysis Pipeline... (Description: {description})")
    
    for script_path, desc in scripts:
        # Special handling for report generator to pass description
        if "create_report.py" in script_path:
             if not run_script(script_path, desc, args=[description]):
                print("Pipeline interrupted due to failure.")
                break
        else:
            if not run_script(script_path, desc):
                print("Pipeline interrupted due to failure.")
                break
            
    print("\nPipeline Execution Complete.")

if __name__ == "__main__":
    main()
