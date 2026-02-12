import pandas_datareader.data as web
import datetime

start = datetime.datetime(2023, 1, 1)
end = datetime.datetime(2023, 12, 31)

try:
    df = web.DataReader("AAPL", "stooq", start, end)
    print(f"Success! Retrieved {len(df)} rows.")
    print(df.head())
except Exception as e:
    print(f"Failed: {e}")
