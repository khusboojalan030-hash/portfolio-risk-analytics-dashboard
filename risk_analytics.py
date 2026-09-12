"""
Portfolio Risk Analytics - Python side
-----------------------------------------
This handles the full analytical pipeline: returns, distribution
analysis, rolling volatility, Monte Carlo simulation, and risk metrics
(VaR, Expected Shortfall, Sharpe Ratio).

It outputs clean CSV files designed to be loaded straight into Power BI
for the dashboard/visualization layer - no SQL step in this version,
since the database design piece is a separate thing to add later.

WHAT THIS COVERS
- Portfolio return analysis (daily, cumulative, annualized)
- Return distribution analysis (skew, kurtosis, normality check)
- Rolling volatility analysis (30-day and 90-day annualized)
- Monte Carlo simulation for portfolio value paths
- Risk metrics: VaR (historical + parametric), Expected Shortfall, Sharpe Ratio

OUTPUT FILES (import these into Power BI)
- portfolio_returns.csv        -> daily returns + cumulative value over time
- rolling_volatility.csv       -> rolling vol series over time
- monte_carlo_paths.csv        -> simulated future portfolio value paths
- risk_metrics_summary.csv     -> single-row summary table of all risk metrics
- return_distribution.csv      -> histogram bin data for the return distribution chart
"""

import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats

# ---------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------

TICKERS = ["RELIANCE.NS", "HDFCBANK.NS", "INFY.NS", "ITC.NS", "TATAMOTORS.NS"]
WEIGHTS = [0.28, 0.25, 0.20, 0.15, 0.12]
YEARS_OF_HISTORY = 5
PORTFOLIO_VALUE = 5_000_000          # starting portfolio value in Rs.
RISK_FREE_RATE = 0.07                # annualized, for Sharpe Ratio (approx Indian T-bill rate)
CONFIDENCE_LEVELS = [0.95, 0.99]
MC_SIMULATIONS = 1000
MC_HORIZON_DAYS = 252                # 1 year ahead

assert abs(sum(WEIGHTS) - 1) < 1e-6, "weights must sum to 1"


# ---------------------------------------------------------------------
# 1. DOWNLOAD PRICES + PORTFOLIO RETURN ANALYSIS
# ---------------------------------------------------------------------

def get_portfolio_returns(tickers, weights, years):
    print(f"downloading {years}y of data for {tickers}...")
    prices = yf.download(tickers, period=f"{years}y", auto_adjust=True, progress=False)["Close"]
    prices = prices.dropna()
    daily_returns = prices.pct_change().dropna()
    portfolio_returns = daily_returns.dot(weights)

    portfolio_value_series = PORTFOLIO_VALUE * (1 + portfolio_returns).cumprod()
    cumulative_return = portfolio_value_series.iloc[-1] / PORTFOLIO_VALUE - 1
    annualized_return = (1 + portfolio_returns.mean()) ** 252 - 1

    print(f"got {len(portfolio_returns)} days, {prices.index[0].date()} -> {prices.index[-1].date()}")
    print(f"cumulative return: {cumulative_return:.2%}, annualized return: {annualized_return:.2%}\n")

    returns_df = pd.DataFrame({
        "date": portfolio_returns.index,
        "daily_return": portfolio_returns.values,
        "portfolio_value": portfolio_value_series.values,
    })
    return returns_df, portfolio_returns, annualized_return


# ---------------------------------------------------------------------
# 2. RETURN DISTRIBUTION ANALYSIS
# ---------------------------------------------------------------------

def analyze_return_distribution(portfolio_returns):
    skew = stats.skew(portfolio_returns)
    kurt = stats.kurtosis(portfolio_returns)
    jb_stat, jb_pvalue = stats.jarque_bera(portfolio_returns)

    print("--- return distribution ---")
    print(f"mean daily return:  {portfolio_returns.mean():.4%}")
    print(f"daily volatility:   {portfolio_returns.std():.4%}")
    print(f"skewness:           {skew:.3f}")
    print(f"excess kurtosis:    {kurt:.3f}")
    print(f"Jarque-Bera test:   stat={jb_stat:.2f}, p-value={jb_pvalue:.6f}")
    if jb_pvalue < 0.05:
        print("p < 0.05 -> reject normality. Returns are NOT normally distributed")
        print("(expected for real equity returns - fat tails, possible skew)")
    else:
        print("p >= 0.05 -> can't reject normality at 5% level")
    print()

    # histogram bin data for Power BI to chart directly
    counts, bin_edges = np.histogram(portfolio_returns, bins=50)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    dist_df = pd.DataFrame({"return_bin": bin_centers, "frequency": counts})

    return dist_df, skew, kurt


# ---------------------------------------------------------------------
# 3. ROLLING VOLATILITY ANALYSIS
# ---------------------------------------------------------------------

def rolling_volatility(returns_df, portfolio_returns):
    df = returns_df.copy()
    df["rolling_vol_30d"] = portfolio_returns.rolling(30).std().values * np.sqrt(252)
    df["rolling_vol_90d"] = portfolio_returns.rolling(90).std().values * np.sqrt(252)
    print("--- rolling volatility (annualized) ---")
    print(f"30-day vol range: {df['rolling_vol_30d'].min():.2%} to {df['rolling_vol_30d'].max():.2%}")
    print(f"90-day vol range: {df['rolling_vol_90d'].min():.2%} to {df['rolling_vol_90d'].max():.2%}\n")
    return df


# ---------------------------------------------------------------------
# 4. MONTE CARLO SIMULATION FOR PORTFOLIO VALUE PATHS
# ---------------------------------------------------------------------

def monte_carlo_simulation(portfolio_returns, start_value, n_sims, horizon_days):
    """
    Simulates future portfolio value paths using Geometric Brownian
    Motion, calibrated to the historical mean and volatility of the
    portfolio's daily returns. Each simulation is one possible future
    path; looking at the SPREAD across simulations tells you the range
    of plausible outcomes, not just a single point forecast.
    """
    mu = portfolio_returns.mean()
    sigma = portfolio_returns.std()

    print(f"--- Monte Carlo simulation ---")
    print(f"{n_sims} simulations, {horizon_days} trading days ahead")
    print(f"calibrated to daily mu={mu:.5f}, sigma={sigma:.5f}\n")

    simulated_paths = np.zeros((horizon_days + 1, n_sims))
    simulated_paths[0] = start_value

    np.random.seed(42)
    for t in range(1, horizon_days + 1):
        random_shocks = np.random.normal(mu, sigma, n_sims)
        simulated_paths[t] = simulated_paths[t - 1] * (1 + random_shocks)

    # build a long-format dataframe: day, simulation_id, value - easiest for Power BI to plot
    days = np.repeat(np.arange(horizon_days + 1), n_sims)
    sim_ids = np.tile(np.arange(n_sims), horizon_days + 1)
    values = simulated_paths.flatten()
    mc_df = pd.DataFrame({"day": days, "simulation_id": sim_ids, "portfolio_value": values})

    final_values = simulated_paths[-1]
    print(f"after {horizon_days} days:")
    print(f"  median outcome:     Rs. {np.median(final_values):,.0f}")
    print(f"  5th percentile:     Rs. {np.percentile(final_values, 5):,.0f}")
    print(f"  95th percentile:    Rs. {np.percentile(final_values, 95):,.0f}")
    print(f"  probability of loss (below Rs. {start_value:,.0f}): "
          f"{(final_values < start_value).mean():.1%}\n")

    return mc_df, final_values


# ---------------------------------------------------------------------
# 5. RISK METRICS: VaR, EXPECTED SHORTFALL, SHARPE RATIO
# ---------------------------------------------------------------------

def calculate_risk_metrics(portfolio_returns, annualized_return, start_value, confidence_levels):
    metrics_rows = []

    for c in confidence_levels:
        alpha = 1 - c
        hist_var = np.percentile(portfolio_returns, alpha * 100)
        tail = portfolio_returns[portfolio_returns <= hist_var]
        hist_es = tail.mean()  # Expected Shortfall = average of the tail beyond VaR

        z = stats.norm.ppf(alpha)
        param_var = portfolio_returns.mean() + z * portfolio_returns.std()

        metrics_rows.append({
            "confidence_level": c,
            "historical_var_pct": hist_var,
            "historical_var_rs": hist_var * start_value,
            "expected_shortfall_pct": hist_es,
            "expected_shortfall_rs": hist_es * start_value,
            "parametric_var_pct": param_var,
        })

    annualized_vol = portfolio_returns.std() * np.sqrt(252)
    sharpe_ratio = (annualized_return - RISK_FREE_RATE) / annualized_vol

    print("--- risk metrics ---")
    print(f"{'Confidence':<12}{'Hist. VaR':<14}{'Expected Shortfall':<20}{'Param. VaR':<12}")
    for row in metrics_rows:
        print(f"{row['confidence_level']:.0%}         "
              f"{row['historical_var_pct']:<14.4%}"
              f"{row['expected_shortfall_pct']:<20.4%}"
              f"{row['parametric_var_pct']:<12.4%}")
    print(f"\nAnnualized return:   {annualized_return:.2%}")
    print(f"Annualized vol:      {annualized_vol:.2%}")
    print(f"Sharpe Ratio:        {sharpe_ratio:.3f}")
    print(f"(risk-free rate assumed: {RISK_FREE_RATE:.1%})\n")

    metrics_df = pd.DataFrame(metrics_rows)
    metrics_df["annualized_return"] = annualized_return
    metrics_df["annualized_volatility"] = annualized_vol
    metrics_df["sharpe_ratio"] = sharpe_ratio
    metrics_df["risk_free_rate"] = RISK_FREE_RATE

    return metrics_df


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():
    returns_df, portfolio_returns, annualized_return = get_portfolio_returns(
        TICKERS, WEIGHTS, YEARS_OF_HISTORY
    )
    dist_df, skew, kurt = analyze_return_distribution(portfolio_returns)
    vol_df = rolling_volatility(returns_df, portfolio_returns)
    mc_df, final_values = monte_carlo_simulation(
        portfolio_returns, PORTFOLIO_VALUE, MC_SIMULATIONS, MC_HORIZON_DAYS
    )
    metrics_df = calculate_risk_metrics(
        portfolio_returns, annualized_return, PORTFOLIO_VALUE, CONFIDENCE_LEVELS
    )

    # save everything Power BI needs
    vol_df.to_csv("portfolio_returns.csv", index=False)
    dist_df.to_csv("return_distribution.csv", index=False)
    mc_df.to_csv("monte_carlo_paths.csv", index=False)
    metrics_df.to_csv("risk_metrics_summary.csv", index=False)

    print("saved: portfolio_returns.csv, return_distribution.csv,")
    print("       monte_carlo_paths.csv, risk_metrics_summary.csv")
    print("\nload these 4 files into Power BI to build the dashboard.")


if __name__ == "__main__":
    main()
