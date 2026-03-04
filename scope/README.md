# Earnings Volatility Backtest

A backtesting framework for short-premium earnings strategies. Tests the hypothesis that options markets systematically overprice volatility before earnings announcements, and that selling that premium via iron butterflies (or short straddles) generates positive expected value over time.

## How It Works

1. **Fetch** historical earnings dates from the Nasdaq calendar API
2. **Screen** each event through three filters: variance risk premium (IV30/RV30 ≥ 1.25), term structure inversion, and minimum volume
3. **Construct** an iron butterfly (or short straddle) using real or synthetic option chains
4. **Simulate** hold-to-expiration P&L with position sizing, slippage, and multi-position management
5. **Analyze** results with Monte Carlo bootstrap resampling (10k paths) for risk metrics

See [EXPLAINER.md](EXPLAINER.md) for a detailed plain-English walkthrough of the entire system.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# 1. Fetch earnings dates (curated 86-ticker universe, 2020–2024)
python fetch_earnings.py --start 2020-01-01 --end 2024-12-31

# 2. Pre-download price history (Stooq.com, free, no API key)
python prefetch_prices.py --earnings-csv data_store/earnings.csv

# 3. Run backtest with synthetic option chains
python run_backtest.py --provider synthetic --earnings-csv data_store/earnings.csv --clear-option-cache

# 4. Run Monte Carlo simulation on a completed backtest
python run_montecarlo.py --run-id <RUN_ID>

# 5. Generate HTML report
python run_report.py --run-id <RUN_ID>
```

For the full production universe (~3,300 tickers), use `--universe` in step 1.

## Data Sources

| Source | Data | Cost |
|--------|------|------|
| **Nasdaq API** | Earnings announcement dates | Free, no key |
| **Stooq.com** | Daily OHLCV price bars | Free, no key |
| **yfinance** | Price bars (fallback) | Free, rate-limited |
| **Synthetic (Black-Scholes)** | Option chains, per-ticker IV calibration | Generated locally |
| **DoltHub /options** | 102M real option chain snapshots | Free local clone |
| **Polygon.io** | Live option chains | API key required |

## Project Structure

```
├── run_backtest.py             # Main backtest entry point
├── run_montecarlo.py           # Monte Carlo simulation
├── run_report.py               # HTML report generation
├── fetch_earnings.py           # Fetch earnings dates from Nasdaq
├── prefetch_prices.py          # Pre-download OHLC price history
├── config.yaml                 # All strategy and system configuration
│
├── backtest/
│   ├── engine.py               # Chronological backtest loop
│   ├── screener.py             # Three-filter screening + classification
│   ├── account.py              # Position tracking, margin, equity
│   ├── slippage.py             # Entry/exit cost simulation
│   ├── validation.py           # Result sanity checks
│   └── strategies/
│       ├── iron_butterfly.py   # 4-leg defined-risk strategy
│       └── short_straddle.py   # 2-leg undefined-risk strategy
│
├── data/
│   ├── cache.py                # SQLite caching layer
│   ├── schema.py               # Data classes (EarningsEvent, OHLCBar, etc.)
│   ├── dolt_provider.py        # Real option data from DoltHub
│   ├── synthetic_provider.py   # Black-Scholes modelled chains
│   ├── polygon_provider.py     # Polygon.io API provider
│   ├── earnings_calendar.py    # Load/filter earnings events
│   └── earnings_move_history.py# Historical post-earnings moves for calibration
│
├── metrics/
│   ├── performance.py          # Sharpe, Sortino, win rate, expectancy
│   ├── returns.py              # Return calculations
│   └── drawdown.py             # Max drawdown, duration
│
├── montecarlo/
│   ├── simulator.py            # Bootstrap resampling engine
│   ├── position_sizing.py      # Fixed, percentage, Kelly sizing
│   └── risk_metrics.py         # VaR, CVaR, ruin probability
│
├── reporting/
│   ├── html_report.py          # Single-run HTML report
│   ├── comparison.py           # Side-by-side run comparison
│   └── charts.py               # Equity curves, P&L distributions
│
├── shared/
│   ├── config_loader.py        # Config parsing and validation
│   ├── classification.py       # Screener classification logic
│   └── math_utils.py           # Volatility, Greeks, financial math
│
├── tests/                      # 117 unit + integration tests
├── data_store/                 # SQLite cache, earnings CSV, logs
└── reports/                    # Generated HTML reports
```

## Screening Filters

All three must pass for a "Recommended" classification (2 of 3 → "Consider"):

| Filter | Threshold | Purpose |
|--------|-----------|---------|
| Average Volume | ≥ 1,500,000 shares/day | Liquidity — tight bid-ask spreads |
| IV30 / RV30 | ≥ 1.25 | Variance risk premium — market overprices by ≥25% |
| Term Structure Slope | ≤ −0.00406 | Earnings premium — near-term IV elevated vs. far-term |

## Configuration

All parameters live in [config.yaml](config.yaml): strategy type, filter thresholds, position sizing, slippage, data provider, Monte Carlo settings, and reporting options. See [CALIBRATION_GUIDE.md](CALIBRATION_GUIDE.md) for systematic parameter tuning.

Key settings:

```yaml
strategy:
  type: iron_butterfly          # or short_straddle
  max_stock_price: 100          # skip expensive underlyings

account:
  starting_capital: 1000
  max_positions: 2
  max_allocation_pct: 10.0
  sizing_mode: percentage       # or fixed

data:
  provider: synthetic           # or dolt, polygon
```

## CLI Reference

### run_backtest.py

```
--provider {synthetic,dolt,polygon}   Data provider for option chains
--earnings-csv PATH                   Path to earnings CSV
--strategy {iron_butterfly,short_straddle}
--capital FLOAT                       Starting capital
--start / --end DATE                  Date range (YYYY-MM-DD)
--tickers TICKER [TICKER ...]         Limit to specific tickers
--clear-option-cache                  Regenerate synthetic chains
--sizing {fixed,percentage}           Position sizing mode
-v, --verbose                         Debug logging
```

### run_montecarlo.py

```
--run-id INT        Backtest run ID (required)
--simulations INT   Number of simulation paths (default: 10000)
--capital FLOAT     Starting capital
--sizing {fixed,percentage,kelly}
--seed INT          Random seed for reproducibility
```

### run_report.py

```
--run-id INT        Generate report for a single run
--compare ID1 ID2   Side-by-side comparison of two runs
--output-dir DIR    Report output directory
```

### fetch_earnings.py

```
--start / --end DATE    Date range
--output PATH           Output CSV (default: data_store/earnings.csv)
--universe              S&P 500 + NASDAQ listed (~3,300 tickers)
--all-tickers           Every ticker on Nasdaq calendar
(default)               Curated 86 high-vol tickers
```

### prefetch_prices.py

```
--earnings-csv PATH     Earnings CSV to determine tickers/dates
--delay FLOAT           Seconds between requests (default: 0.5)
--stooq-only            Skip yfinance fallback
```

## Tests

```bash
pytest                  # run all 117 tests
pytest tests/ -v        # verbose output
pytest tests/test_strategies.py  # run a specific test file
```

## Documentation

- [EXPLAINER.md](EXPLAINER.md) — Plain-English explanation of the entire system
- [CALIBRATION_GUIDE.md](CALIBRATION_GUIDE.md) — Systematic parameter tuning workflow
