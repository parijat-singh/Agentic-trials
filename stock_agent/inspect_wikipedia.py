import pandas as pd
import requests
from io import StringIO

def inspect_sp500():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers)
        dfs = pd.read_html(StringIO(r.text))
        df = dfs[0]
        print("Columns found:", df.columns.tolist())
        print(df.head())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_sp500()
