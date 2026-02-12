# Stock Data Agent

An automated agent that:
1.  **Scrapes** S&P 500 and NASDAQ 100 tickers from Wikipedia.
2.  **Filters** for the top 100 companies by market cap that have started trading within the last 10 years.
3.  **Downloads** 10 years of historical data for these companies.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the main script:

```bash
python main.py
```

## Output

-   `tickers.txt`: List of all candidate tickers.
-   `top_100_new_stocks.csv`: The list of selected stocks with metadata (Market Cap, IPO Date).
-   `data/`: Folder containing individual CSV files for each stock's history.
