import pandas_datareader.data as web
from datetime import datetime
import time

def test_stooq():
    symbol = "AAPL"
    print(f"Fetching {symbol} from Stooq...", flush=True)
    start = time.time()
    try:
        df = web.DataReader(symbol, 'stooq')
        print(f"Data received in {time.time() - start:.2f}s.", flush=True)
        print(f"Rows: {len(df)}", flush=True)
        print(df.head(2))
    except Exception as e:
        print(f"Error: {e}", flush=True)

if __name__ == "__main__":
    test_stooq()
