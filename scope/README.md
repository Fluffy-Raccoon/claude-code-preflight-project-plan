# Automated Earnings Volatility Trading System

Screens US equities for elevated implied volatility around earnings announcements, identifies candidates where IV systematically overstates the actual move, and optionally executes short premium trades via the tastytrade API.

Two operating modes:
- **One-shot** (`pipeline.py`) — screen a specific ticker list on demand or via cron
- **Continuous drip-feed** (`drip_scheduler.py`) — scan 3,500+ tickers throughout the day via a 4-tier funnel

See [SYSTEM_OVERVIEW.md](docs/SYSTEM_OVERVIEW.md) for the full strategy explanation and [TRADING_STRATEGY.md](docs/TRADING_STRATEGY.md) for position sizing and risk management.

---

## Project Structure

```
earnings_day_trading/
├── pipeline.py                      # One-shot orchestrator (entry point 1)
├── drip_scheduler.py                # Continuous daemon (entry point 2)
├── config.yaml                      # All settings
├── start_drip.sh                    # Daemon launcher script
│
├── screener/                        # Core library package
│   ├── universe/                    # Universe building & earnings calendar
│   │   ├── yfinance_builder.py      # Identifies stocks with upcoming earnings
│   │   ├── polygon_builder.py       # Polygon.io universe builder
│   │   ├── ticker_universe.py       # S&P 500 + NASDAQ ticker lists (~3,500)
│   │   └── earnings_calendar.py     # NASDAQ/Finnhub bulk earnings calendar API
│   ├── data/                        # Market data fetching
│   │   ├── yfinance_fetcher.py      # Batch price + option chain fetching
│   │   └── polygon_fetcher.py       # Polygon.io data fetcher
│   ├── metrics/                     # Screening metrics
│   │   └── engine.py                # RV30, IV30, IV/RV ratio, term structure slope
│   ├── storage/                     # Persistence
│   │   └── layer.py                 # SQLite + CSV persistence
│   ├── execution/                   # Trade execution
│   │   └── trade_executor.py        # Automated orders via tastytrade API
│   ├── alerting/                    # Notifications
│   │   └── alerting.py              # Console summaries + HTML email alerts
│   └── scheduling/                  # Drip-feed daemon infrastructure
│       ├── work_queue.py            # SQLite-backed work queue
│       └── rate_limiter.py          # Adaptive rate limiter (backoff/recovery)
│
├── tools/                           # Standalone scripts
│   ├── calculator.py                # GUI calculator (FreeSimpleGUI)
│   ├── test_pipeline.py             # Quick pipeline test with sample tickers
│   ├── query_results.py             # Query stored screening results
│   └── generate_sample_universe.py  # Generate sample universe CSV
│
├── docs/                            # Documentation
│   ├── ARCHITECTURE.md              # Technical architecture and data flows
│   ├── SYSTEM_OVERVIEW.md           # Strategy explanation, risk analysis
│   ├── TRADING_STRATEGY.md          # Position sizing, going-live checklist
│   ├── STRATEGY_SPEC.md             # Exact formulas for backtest alignment
│   └── STRATEGY_FOR_DUMMIES.md      # Plain English strategy + math guide
│
└── data/                            # Runtime data (auto-created)
    ├── screening_results.db         # Screening results + trades log
    ├── drip_queue.db                # Drip-feed work queue state
    └── daily_screens/               # CSV exports
```

---

## Installation

```bash
pip3 install -r requirements.txt
```

For trade execution, set up tastytrade OAuth credentials:
```bash
cp .env.example .env
# Edit .env — add TASTYTRADE_CLIENT_SECRET (or TASTYTRADE_CLIENT_TOKEN) and TASTYTRADE_REFRESH_TOKEN
# Generate at: https://my.tastytrade.com/app.html#/manage/api-access/oauth-applications
```

---

## Usage

### One-Shot Mode (on-demand or scheduled)

```bash
# Screen default candidate list
python3 pipeline.py

# Screen specific tickers
python3 pipeline.py --tickers AAPL MSFT NVDA

# Load universe from file
python3 pipeline.py --universe-file my_stocks.csv

# Schedule via cron (daily at 9 PM ET on weekdays)
# 0 21 * * 1-5 cd /path/to/earnings_day_trading && python3 pipeline.py
```

### Continuous Drip-Feed Mode (recommended)

```bash
# Start with auto-retry on rate limits
./start_drip.sh
or (if running from zsh terminal)
bash start_drip.sh

# Or run directly (single cycle, then exit)
python3 drip_scheduler.py --single-cycle

# Daemon mode (repeats daily)
python3 drip_scheduler.py
```

### Query Results

```bash
python3 tools/query_results.py                              # Last 7 days
python3 tools/query_results.py --classification Recommended  # Only recommended
python3 tools/query_results.py --days 30                     # Last 30 days
```

---

## Key Configuration (`config.yaml`)

| Section | Key Settings |
|---------|-------------|
| `universe` | `min_avg_volume` (1.5M), earnings window (3 days before, 1 after) |
| `strategy` | `min_iv30_rv30_ratio` (1.25), `max_ts_slope_0_45` (-0.00406) |
| `execution` | `enabled`, `dry_run`, `mode`, `strategy` (iron_butterfly/short_straddle), `max_positions`, `max_stock_price`, `wing_width_mode` |
| `drip` | `tier1_batch_size` (500), `tier3_batch_size` (10), `tier4_batch_size` (3), `earnings_source` (nasdaq), rate limiter bounds |

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full configuration reference and data flow diagrams.

---

## Disclaimer

This software is provided solely for educational and research purposes. It is not intended to provide investment advice. Options trading involves significant risk of loss. Always consult a professional financial advisor before making any investment decisions.
