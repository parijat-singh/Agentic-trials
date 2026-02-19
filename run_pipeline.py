import os
import subprocess
import sys
import argparse
import shutil
import config

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
            
        # Run in the script's directory to ensure relative paths (like 'data/') work as expected by the scripts
        result = subprocess.run(cmd, check=True, cwd=os.path.dirname(path)) 
        print(f"SUCCESS: {description}", flush=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"FAILURE: {description} (Exit Code: {e.returncode})", flush=True)
        return False
    except Exception as e:
        print(f"ERROR: {description} (Exception: {str(e)})", flush=True)
        return False

def get_user_input(prompt, default_val, type_func=str):
    val = input(f"{prompt} [{default_val}]: ").strip()
    if not val:
        return default_val
    return type_func(val)

def main():
    parser = argparse.ArgumentParser(description="Run Full Analysis Pipeline")
    parser.add_argument("--interactive", action="store_true", help="Ask for parameters interactively")
    parser.add_argument("--min-history", type=float, help="Minimum years of history")
    parser.add_argument("--min-ipo", type=float, help="Minimum years since IPO")
    parser.add_argument("--max-ipo", type=float, help="Maximum years since IPO")
    parser.add_argument("--max-pe", type=float, help="Maximum P/E Ratio")
    parser.add_argument("--min-market-cap", type=float, help="Minimum Market Cap in Billions")
    parser.add_argument("--max-pages", type=int, default=200, help="Max pages to scan")
    parser.add_argument("--skip-scraper", action="store_true", help="Skip the scraping step")
    
    args = parser.parse_args()
    
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Defaults
    p_min_hist = 5.0
    p_min_ipo = 5.0
    p_max_ipo = 10.0
    p_max_pe = None
    p_max_pages = 200
    
    if args.interactive:
        print("\n--- Pipeline Configuration ---")
        p_min_hist = get_user_input("Minimum History (Years)", 5.0, float)
        p_min_ipo = get_user_input("Minimum IPO Age (Years)", 5.0, float)
        p_max_ipo = get_user_input("Maximum IPO Age (Years)", 10.0, float)
        
        pe_input = input("Maximum P/E Ratio (Enter for None/Disable): ").strip()
        if pe_input:
            p_max_pe = float(pe_input)
        else:
            p_max_pe = None
            
        p_max_pages = get_user_input("Max Pages to Scan", 200, int)
    else:
        # Use args if provided, else defaults
        if args.min_history is not None: p_min_hist = args.min_history
        if args.min_ipo is not None: p_min_ipo = args.min_ipo
        if args.max_ipo is not None: p_max_ipo = args.max_ipo
        if args.max_pe is not None: p_max_pe = args.max_pe
        if args.max_pages is not None: p_max_pages = args.max_pages

    # Construct Description
    pe_desc = f", P/E < {p_max_pe}" if p_max_pe else ""
    run_description = f"Scan (IPO {p_min_ipo}-{p_max_ipo}y, Hist {p_min_hist}y{pe_desc})"
    
    print(f"\nStarting Pipeline: {run_description}")
    
    # Scripts to run
    
    import time
    import json
    
    start_time = time.time()
    
    # Save parameters to stats file so downstream modules (like Financial Engine) can see them
    # This is crucial when --skip-scraper is used but we still want to enforce current filter criteria
    stats_path = os.path.join(config.DATA_DIR, "scraping_stats.json")
    stats = {}
    if os.path.exists(stats_path):
        try:
            with open(stats_path, 'r') as f:
                stats = json.load(f)
        except: pass
    
    # Update only the parameters section
    stats["Parameters"] = {
        "Min_History": p_min_hist,
        "Min_IPO": p_min_ipo,
        "Max_IPO": p_max_ipo,
        "Max_PE": p_max_pe,
        "Min_Market_Cap": args.min_market_cap,
        "Max_Pages": p_max_pages
    }
    
    if not os.path.exists(config.DATA_DIR):
        os.makedirs(config.DATA_DIR)
        
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    
    print(f"Parameters saved to {stats_path}")
    
    # ... (Rest of script execution) ...
    
    # 1. Scraper (Optional skip)
    if not args.skip_scraper:
        # Clean previous data
        print(f"Cleaning data directory: {config.DATA_DIR}")
        if os.path.exists(config.DATA_DIR):
            try:
                shutil.rmtree(config.DATA_DIR)
                os.makedirs(config.DATA_DIR)
            except Exception as e:
                print(f"Warning: Failed to clean data directory: {e}")
                
        scraper_script = os.path.join(root_dir, "stock_agent", "market_cap_scraper.py")
        scraper_args = [
            f"--min-history={p_min_hist}",
            f"--min-ipo={p_min_ipo}",
            f"--max-ipo={p_max_ipo}",
            f"--max-pages={p_max_pages}"
        ]
        if p_max_pe is not None:
            scraper_args.append(f"--max-pe={p_max_pe}")

        if args.min_market_cap is not None:
             scraper_args.append(f"--min-market-cap={args.min_market_cap}")
            
        if not run_script(scraper_script, "Module 1: Stock Scraper", args=scraper_args):
             print("Pipeline interrupted at Scraper.")
             sys.exit(1)

    # 2. Other Modules
    scripts = [
        (os.path.join(root_dir, "financial_engine", "main.py"), "Module 2: Financial Engine (Sharpe Ranking)"),
        (os.path.join(root_dir, "portfolio_optimizer", "main.py"), "Module 3: Portfolio Optimization"),
        (os.path.join(root_dir, "portfolio_optimizer", "main.py"), "Module 3: Portfolio Optimization"),
        (os.path.join(root_dir, "backtester", "main.py"), "Module 4: Backtester"),
        (os.path.join(root_dir, "financial_engine", "top_10_analyzer.py"), "Top 10 Exclusion Analysis"),
        (os.path.join(root_dir, "report_generator", "create_report.py"), "Final Reporting")
    ]
    
    for script_path, desc in scripts:
        # Before running report, save the elapsed time to stats so report can pick it up
        if "create_report.py" in script_path:
            end_time = time.time()
            elapsed_time = end_time - start_time
            hours, rem = divmod(elapsed_time, 3600)
            minutes, seconds = divmod(rem, 60)
            time_str = "{:0>2}:{:0>2}:{:05.2f}".format(int(hours), int(minutes), seconds)
            
            # Save to stats
            stats_path = os.path.join(config.DATA_DIR, "scraping_stats.json")
            if os.path.exists(stats_path):
                try:
                    with open(stats_path, 'r') as f:
                         stats = json.load(f)
                    stats["Total_Time"] = time_str
                    with open(stats_path, 'w') as f:
                        json.dump(stats, f, indent=2)
                except Exception as e:
                    print(f"Error saving time stats: {e}")
        
        if "create_report.py" in script_path:
             if not run_script(script_path, desc, args=[run_description]):
                print("Pipeline interrupted.")
                sys.exit(1)
        else:
            if not run_script(script_path, desc):
                print("Pipeline interrupted.")
                sys.exit(1)
            
    print("\nPipeline Execution Complete.")

if __name__ == "__main__":
    main()
