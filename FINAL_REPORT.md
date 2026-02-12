# Financial Analysis Report
**Date:** 2026-02-11 22:59

---

## 1. Candidate Selection (Module 1)
Goal: Identify large-cap stocks (<10 years old).

Status: Data not found.

---

## 2. Risk-Adjusted Ranking (Module 2)
Goal: Filter Top 50 by Sharpe Ratio.

- **Top Stock:** SNDK (Sharpe: 3.27)

**Top 10 Ranked Stocks:**

| Symbol    |   Sharpe Ratio |   Annualized Return |   Annualized Volatility |
|:----------|---------------:|--------------------:|------------------------:|
| SNDK      |        3.26965 |            3.36871  |                1.01754  |
| GEV       |        2.03404 |            1.13268  |                0.53635  |
| DCII.JK   |        1.94326 |            1.50924  |                0.755186 |
| GALD.SW   |        1.68081 |            0.615047 |                0.341102 |
| VIK       |        1.65266 |            0.683741 |                0.388478 |
| MDLN      |        1.56556 |            0.736406 |                0.443731 |
| CRWV      |        1.36367 |            1.71193  |                1.22479  |
| AMMN.JK   |        1.25172 |            0.758529 |                0.572661 |
| 402340.KS |        1.12911 |            0.625044 |                0.516623 |
| CEG       |        1.12116 |            0.595411 |                0.493853 |

---

## 3. Optimized Portfolio (Module 3)
Goal: Maximize forward-looking Sharpe Ratio using Mean-Variance Optimization.
Constraint: Max 20% allocation per stock.

**Recommended Allocation:**

| Symbol    | Weight   |
|:----------|:---------|
| 2082.SR   | 20.00%   |
| SNDK      | 1.63%    |
| VIK       | 1.63%    |
| GEV       | 1.63%    |
| GALD.SW   | 1.63%    |
| MDLN      | 1.63%    |
| DCII.JK   | 1.63%    |
| 402340.KS | 1.63%    |
| CARR      | 1.63%    |
| BPAC3.SA  | 1.63%    |
| SDZ.SW    | 1.63%    |
| 329180.KS | 1.63%    |
| 300502.SZ | 1.63%    |
| ARGX      | 1.63%    |
| CEG       | 1.63%    |
| CVNA      | 1.63%    |
| PLTR      | 1.63%    |
| HAL.NS    | 1.63%    |
| AMMN.JK   | 1.63%    |
| RKLB      | 1.63%    |
| VST       | 1.63%    |
| ENR.F     | 1.63%    |
| DELL      | 1.63%    |
| DSV.VI    | 1.63%    |
| CRWV      | 1.63%    |
| CRWD      | 1.63%    |
| DMART.NS  | 1.63%    |
| IR        | 1.63%    |
| UCB.VI    | 1.63%    |
| VRT       | 1.63%    |
| 2359.HK   | 1.63%    |
| BAM       | 1.63%    |
| 603986.SS | 1.63%    |
| BNTX      | 1.63%    |
| SE        | 1.63%    |
| HWM       | 1.63%    |
| 9992.HK   | 1.63%    |
| BE        | 1.63%    |
| 601127.SS | 1.63%    |
| 688012.SS | 1.63%    |
| GULF.BK   | 1.63%    |
| 207940.KS | 1.63%    |
| ARM       | 1.63%    |
| 300750.SZ | 1.63%    |
| MDB       | 1.63%    |
| SYM       | 1.63%    |
| 688256.SS | 1.63%    |
| ASTS      | 1.63%    |
| NET       | 1.63%    |
| APP       | 1.63%    |

---

## 4. Historical Backtest Criteria (Module 4)
Goal: Find the combination with the highest consecutive 3-year return.

**Winning Historical Combination (Past 3 Years):**

| Symbol    | Weight   |
|:----------|:---------|
| 688012.SS | 20.00%   |
| IBKR      | 20.00%   |
| 329180.KS | 20.00%   |
| 9992.HK   | 20.00%   |
| 402340.KS | 20.00%   |

