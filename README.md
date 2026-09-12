# Portfolio Risk Analytics Dashboard

An end-to-end risk analysis workflow for an equity portfolio, combining
Python for the analytics and Power BI for the dashboard/visualization
layer - built to understand how risk teams at financial institutions
actually measure and monitor portfolio risk day to day.

## What this covers

- **Portfolio return analysis** - daily, cumulative, and annualized
  returns on a weighted 5-stock portfolio
- **Return distribution analysis** - skewness, kurtosis, and a
  Jarque-Bera normality test, to check whether returns actually behave
  like a normal distribution (they usually don't)
- **Rolling volatility analysis** - 30-day and 90-day annualized
  rolling volatility, showing how risk changes over time instead of
  assuming it's constant
- **Monte Carlo simulation** - 1,000 simulated future portfolio value
  paths over a 1-year horizon, calibrated to the portfolio's historical
  mean return and volatility
- **Risk metrics** - Value at Risk (historical + parametric), Expected
  Shortfall, and Sharpe Ratio

## Architecture

```
Python (analytics)  ->  4 CSV files  ->  Power BI (dashboard)
```

The Python script does all the number-crunching and exports clean,
Power-BI-ready CSVs. Power BI then handles the interactive
visualization layer on top.

**Note on scope**: the original version of this project included a SQL
database layer for the portfolio data. This version skips that step -
the Python script exports directly to CSV instead of reading from/
writing to a database. Adding a proper SQL layer (e.g. loading the
portfolio and returns into a database, querying from there) is a
natural next step once that piece is ready.

## Output files (import these into Power BI)

| File | Contents | Suggested Power BI visual |
|---|---|---|
| `portfolio_returns.csv` | date, daily return, rolling 30d/90d volatility, portfolio value | Line chart of portfolio value over time; line chart of rolling volatility |
| `return_distribution.csv` | histogram bin centers + frequency | Column/bar chart for the return distribution |
| `monte_carlo_paths.csv` | day, simulation_id, portfolio value (long format) | Line chart with simulation_id as a legend/series field, showing the fan of possible future paths |
| `risk_metrics_summary.csv` | VaR, Expected Shortfall, Sharpe Ratio at each confidence level | Card visuals or a table for the key risk metrics |

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
python risk_analytics.py
```

This downloads 5 years of price data, runs the full analysis, and
saves the 4 CSV files listed above in the same folder.

To use a different portfolio, edit the top of the script:
```python
TICKERS = ["RELIANCE.NS", "HDFCBANK.NS", "INFY.NS", "ITC.NS", "TATAMOTORS.NS"]
WEIGHTS = [0.28, 0.25, 0.20, 0.15, 0.12]
PORTFOLIO_VALUE = 5_000_000
RISK_FREE_RATE = 0.07
```

## Building the Power BI dashboard

1. Open Power BI Desktop -> Get Data -> Text/CSV -> load each of the 4
   output files
2. For the Monte Carlo fan chart: put `day` on the X-axis, `portfolio_value`
   on the Y-axis, and `simulation_id` in the Legend field - this draws
   all simulated paths as separate lines automatically
3. For the return distribution: `return_bin` on the X-axis, `frequency`
   on the Y-axis as a column chart
4. For risk metrics: use Card visuals bound to specific rows of
   `risk_metrics_summary.csv`, or a matrix/table visual to show both
   confidence levels side by side
5. Add a rolling volatility line chart from `portfolio_returns.csv`
   (`date` on X-axis, `rolling_vol_30d` and `rolling_vol_90d` as two
   line series) to show how risk has changed over time

## Understanding the metrics

| Metric | What it tells you |
|---|---|
| **VaR** | The loss you wouldn't expect to exceed, X% of the time, over one day |
| **Expected Shortfall (ES)** | If that bad day does happen, the average loss you'd expect - always worse than VaR, since it looks past the cutoff instead of stopping at it |
| **Sharpe Ratio** | Return earned per unit of risk taken - `(portfolio return - risk-free rate) / volatility`. Higher is better; below ~0.5 suggests the portfolio isn't being well compensated for its risk |

## Project structure

```
portfolio-risk-dashboard/
├── risk_analytics.py
├── requirements.txt
├── README.md
├── .gitignore
└── (Power BI .pbix file - add once built)
```

## Possible extensions

- Add the SQL layer back in: design a portfolio database schema, load
  the return/price data into it, and query from Python via SQL instead
  of a flat CSV pipeline
- Implement FRTB Expected Shortfall models (regulatory capital
  calculation using stressed calibration windows)
- Add a stress testing module alongside the VaR/ES metrics
- Add sector/position-level risk attribution instead of only portfolio-level metrics
