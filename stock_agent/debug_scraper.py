import requests
from bs4 import BeautifulSoup
import time

def test_scraper():
    url = "https://companiesmarketcap.com/page/1/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    print("Sending request...", flush=True)
    start = time.time()
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Response received in {time.time() - start:.2f}s. Status: {response.status_code}", flush=True)
        
        if response.status_code == 200:
            print("Parsing soup...", flush=True)
            soup = BeautifulSoup(response.text, 'html.parser')
            rows = soup.find_all('tr')
            print(f"Found {len(rows)} rows.", flush=True)
            
            # Check first company
            first_name = soup.find('div', class_='company-name')
            if first_name:
                print(f"First company: {first_name.text.strip()}", flush=True)
            else:
                print("Could not find company name div.", flush=True)
        else:
            print("Failed to get 200 OK.")
            
    except Exception as e:
        print(f"Error: {e}", flush=True)

if __name__ == "__main__":
    test_scraper()
