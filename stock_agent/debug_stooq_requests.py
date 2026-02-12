import requests
import time

def test_stooq_request():
    # Stooq CSV download URL for AAPL
    url = "https://stooq.com/q/d/l/?s=AAPL.US&i=d"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    
    print(f"Requesting {url}...", flush=True)
    start = time.time()
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}", flush=True)
        print(f"Time: {time.time() - start:.2f}s", flush=True)
        print("Content snippet:", response.text[:100], flush=True)
    except Exception as e:
        print(f"Error: {e}", flush=True)

if __name__ == "__main__":
    test_stooq_request()
