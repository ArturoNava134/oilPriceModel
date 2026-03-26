# Oil Price Risk Factor Analysis

**Citibank Oil Price Risk Factor Challenge**

---

## What This Project Does

This is a real-time oil market risk analysis system. It answers one question: **what factors are driving oil prices right now, and is oil at risk of going up or down?**

It works by combining two independent data streams:

1. **Price data** — 10 years of daily oil prices from Yahoo Finance, plus macroeconomic indicators from FRED and EIA. From this raw data, the system engineers 60+ technical indicators (RSI, MACD, Bollinger Bands, moving averages, volatility, momentum, etc.) and feeds them into prediction models.

2. **News sentiment** — every 10 minutes, the system scrapes oil-related headlines from Google News RSS, Reuters, and OilPrice.com. Each headline gets scored from -1 (very bearish) to +1 (very bullish) using three independent classification methods: a dictionary-based approach with oil-specific word lists, a rule-based scorer with intensity boosters and negation handling, and a TF-IDF + Logistic Regression ML classifier. The consensus of all three determines the final label.

These two streams feed into a **risk assessment engine** that weights each signal (trend 30%, momentum 15%, MACD 15%, recent returns 15%, VIX 10%, news sentiment empirically measured) and produces a single risk score from -1 (high risk, strong bearish signals) to +1 (low risk, bullish signals dominate).

On top of that, a **prediction module** trains ARIMA and XGBoost models on the historical data to forecast the next 5 trading days of oil prices. XGBoost also provides feature importance rankings — a direct answer to the competition question about key risk factors.

Everything is displayed on a live React dashboard that auto-refreshes every 30 seconds.

---

## Project Structure

```
oilPriceModel/
├── oilPriceWebsite/
│   ├── backend/
│   │   ├── server.js                 ← Express API (starts Python automatically)
│   │   ├── package.json
│   │   ├── nodemon.json              ← Prevents restart loops
│   │   ├── .env                      ← API keys (you create this)
│   │   ├── python/                   ← All analysis scripts
│   │   │   ├── config.py             ← Centralized path configuration
│   │   │   ├── oil_data_collector.py ← Price data + feature engineering
│   │   │   ├── news_scraper.py       ← News scraping + sentiment classification
│   │   │   ├── monitor.py            ← Live risk monitor (runs continuously)
│   │   │   ├── predictor.py          ← ARIMA + XGBoost forecasting
│   │   │   ├── main.py               ← One-shot full analysis + report
│   │   │   └── regime_detector.py    ← Market regime detection
│   │   └── data/                     ← All outputs (auto-created, don't commit)
│   │       ├── price/                ← data_yfinance_raw.csv, etc.
│   │       ├── news/                 ← scored_headlines.csv, plots/
│   │       ├── news_live/            ← live_sentiment.json, all_headlines.json
│   │       ├── monitor/              ← current_state.json, risk_history.csv
│   │       ├── predictions/          ← forecast.json
│   │       ├── regime/               ← regime_labels.csv, plots/
│   │       └── analysis/             ← final_report.txt
│   └── frontend/
│       └── src/
│           ├── App.jsx
│           └── components/
│               ├── pages/Panel.jsx   ← Main dashboard
│               └── auth/Login.jsx
├── requirements.txt                  ← Python dependencies (single file)
└── README.md                         ← This file
```

---

## Setup Guide

### Prerequisites

- **Node.js** v18+ — [nodejs.org](https://nodejs.org)
- **Python** 3.10+ — [python.org](https://www.python.org/downloads/)

### Step 1: Install Python Dependencies

From the project root:

```bash
pip install -r requirements.txt
```

This single file covers everything needed: data collection (`yfinance`, `fredapi`), news scraping (`beautifulsoup4`, `lxml`), ML models (`scikit-learn`, `xgboost`, `statsmodels`), visualization (`matplotlib`, `seaborn`), and utilities (`scipy`, `python-dotenv`, `openpyxl`).

Optional — adds a 4th sentiment classification method (VADER):
```bash
pip install nltk
python -c "import nltk; nltk.download('vader_lexicon')"
```

Optional — adds HMM regime detection:
```bash
pip install hmmlearn
```

### Step 2: Install Backend

```bash
cd oilPriceWebsite/backend
npm install
```

### Step 3: Install Frontend

```bash
cd oilPriceWebsite/frontend
npm install
```

The frontend uses `react`, `react-router-dom`, `recharts` (charts), `lucide-react` (icons), and `tailwindcss`.

### Step 4: Get API Keys

The system works without any keys — Yahoo Finance and Google News RSS need no authentication. Adding these free keys gives significantly more data:

**FRED API Key** (Federal Reserve Economic Data)
Gives macroeconomic indicators: GDP, CPI, interest rates, yield curve, unemployment, money supply, consumer sentiment. These are the fundamental demand-side drivers of oil prices.
→ Get yours free at **https://fred.stlouisfed.org/docs/api/api_key.html** (2 min signup)

**EIA API Key** (Energy Information Administration)
Gives actual oil supply/demand data: weekly crude inventories, production numbers, import/export flows. The weekly inventory report is one of the single biggest movers of oil prices.
→ Get yours free at **https://www.eia.gov/opendata/register.php** (2 min signup)

**NewsAPI Key** (Optional but Recommended)
Gives more headlines from 80,000+ news sources with better metadata. Free tier: 100 requests/day, 1 month of article history.
→ Get yours free at **https://newsapi.org/register** (30 sec signup)

### Step 5: Create the .env File

Create a file called `.env` inside `oilPriceWebsite/backend/`:

```env
# Oil Price Risk Factor Analysis
# ================================
# NEVER commit this file to git!

# FRED API Key (Federal Reserve Economic Data)
# Get yours free at: https://fred.stlouisfed.org/docs/api/api_key.html
FRED_API_KEY=your_fred_key_here

# EIA API Key (Energy Information Administration)
# Get yours free at: https://www.eia.gov/opendata/register.php
EIA_API_KEY=your_eia_key_here

# NewsAPI Key (optional — more headlines from more sources)
# Get yours free at: https://newsapi.org/register
NEWS_API_KEY=your_newsapi_key_here
```

Replace the placeholder values with your actual keys. If you don't have a key yet, just leave the placeholder — the system skips that data source and tells you what's missing.

### Step 6: Run the Project

You need two terminals:

**Terminal 1 — Backend:**
```bash
cd oilPriceWebsite/backend
npm start
```

This does everything: starts Express on port 8081, spawns the Python monitor, loads price data (downloads on first run ~2 min), polls news every 10 min, and fetches live WTI price.

**Terminal 2 — Frontend:**
```bash
cd oilPriceWebsite/frontend
npm run dev
```

Open **http://localhost:5173/panel** — dashboard populates within 1-2 minutes.

---

## What the Dashboard Shows

### Risk Assessment (Top Left)

The main output — a single score from -1 to +1 that combines all signals.

- **+0.40 to +1.0 → LOW RISK** — Strong bullish signals. Oil likely to hold or rise.
- **+0.15 to +0.40 → LOW-MODERATE** — Slightly bullish. More signals point up.
- **-0.15 to +0.15 → MODERATE** — Mixed signals. Could go either way.
- **-0.40 to -0.15 → ELEVATED** — Bearish signals building. Downside more likely.
- **-1.0 to -0.40 → HIGH RISK** — Strong bearish signals. Significant decline risk.

Below the score, a **horizontal bar chart** shows what's driving it. Green bars push bullish, red push bearish. The signals and their weights:

- **Trend (30%)** — Is the 50-day moving average above or below the 200-day? Above = "Golden Cross" (bullish). Below = "Death Cross" (bearish). Most reliable long-term signal.
- **RSI Momentum (15%)** — Relative Strength Index, 0-100. Think of it like a speedometer: above 70 = going too fast, might slow down. Below 30 = oversold, might bounce. 30-70 = normal.
- **MACD Direction (15%)** — Confirms whether momentum is accelerating up (bullish) or down (bearish).
- **Recent Returns (15%)** — What actually happened in the last 5 trading days. Hard to argue with reality.
- **VIX / Market Fear (10%)** — Below 20 = calm. 20-30 = worried. Above 30 = panicking. High VIX = oil gets volatile.
- **News Sentiment (empirically measured)** — Overall mood of recent headlines. Weight is calculated from actual correlation with price moves, not guessed.

### Live Price + Technicals (Top Center)

Current WTI crude price from Yahoo Finance, updated every 10 minutes. Three return cards:

- **Today** — price change in the last trading session
- **This Week** — change over last 5 trading days
- **This Month** — change over last 20 trading days

Technical indicators explained for non-economists:

- **Trend** — Uptrend ("Golden Cross") or downtrend ("Death Cross"). The most reliable long-term signal.
- **RSI** — Momentum speedometer: 70+ = going too fast, 30- = oversold, 30-70 = normal.
- **VIX** — Fear gauge: below 20 = calm, 20-30 = worried, above 30 = panic.
- **MACD** — Bullish (positive) or bearish (negative) momentum direction.
- **Volatility** — How wild the swings are: below 20% = calm, 20-35% = normal, above 40% = choppy.
- **Brent-WTI Spread** — Gap between international and US oil. Wide (>$5) = global supply tighter.

Every indicator has a **?** tooltip with a plain-English explanation.

### 5-Day Forecast (Top Right)

Click **"Run Models"** (~15 seconds) to train and generate a forecast. Shows:

- **Direction call** — UP, DOWN, or FLAT with predicted price and % change
- **Area chart** — visual price trajectory (green if up, red if down)
- **Individual models** — each model's prediction with backtest accuracy
- **Top Price Drivers** — XGBoost's feature importance rankings

The models:

- **ARIMA(5,1,2)** — Time series model. 5 autoregressive terms, 1 differencing step (removes trend), 2 moving average terms. Good at short-term momentum and mean-reversion.
- **XGBoost** — Gradient boosted trees on 80+ features. Predicts next-day returns. Key advantage: **feature importance** rankings that directly answer the competition question.
- **Trend Baseline** — Simple momentum extrapolation. Every real model should beat this — if they don't, they're overfitting.

The ensemble averages all three. Backtesting uses walk-forward validation (train on all-but-last-20, test on last 20).

### News Feed (Bottom Left)

Scrollable list of all scraped headlines, newest first. Each shows:

- **Colored dot** — green (bullish), red (bearish), gray (neutral)
- **Headline text**
- **Source and date**
- **Sentiment score** — from -1.0 to +1.0

Filter tabs: All / Bullish / Bearish / Neutral. System scrapes 5 RSS queries every 10 minutes, deduplicates, and keeps a 120-minute rolling window.

### Sentiment Overview

**Donut chart** of bullish/neutral/bearish split. The sentiment score averages all headlines — positive = market narrative leans bullish, negative = bearish.

### Market Regime

Shows the current market state (BULL / BEAR / CRISIS) detected by K-Means clustering or HMM. Includes historical distribution and — most importantly — the **top risk factors per regime**, showing how they change between bull and bear markets. Click **"Detect Regimes"** to run (~10 seconds).

### System Log

Live feed of Python monitor activity. Color-coded: blue = system, green = data, red = errors, purple = predictions.

---

## How the Data Collection Works

### Yahoo Finance — Price Data

Downloads 10 years of daily OHLCV for 12 tickers:

**Oil benchmarks:**
- `CL=F` → **WTI Crude** — main prediction target, the US oil benchmark
- `BZ=F` → **Brent Crude** — international benchmark, used for spread analysis

**Related energy products:**
- `NG=F` → **Natural Gas** — correlated energy commodity
- `HO=F` → **Heating Oil** — downstream oil product
- `RB=F` → **Gasoline** — downstream oil product

**Market health indicators:**
- `DX-Y.NYB` → **US Dollar Index** — oil is priced in USD, strong inverse correlation
- `^GSPC` → **S&P 500** — proxy for overall economic health
- `^VIX` → **VIX** — fear gauge, spikes during market crises

**Sector-specific:**
- `XLE` → **Energy Sector ETF** — sector-level sentiment
- `USO` → **Oil ETF** — retail investor sentiment

**Safe havens:**
- `GC=F` → **Gold** — tends to move opposite to risk assets
- `SI=F` → **Silver** — safe haven asset

### FRED — Macroeconomic Data (15 indicators)

**Economic growth:**
- GDP / Real GDP — more growth = more oil demand
- Industrial Production — factories are heavy oil consumers

**Inflation & prices:**
- CPI — oil is a big component of consumer prices
- Gas Prices — downstream demand indicator

**Labor market:**
- Unemployment Rate — affects driving, spending, economic outlook

**Interest rates & monetary policy:**
- Fed Funds Rate — affects USD strength and economic activity
- 10Y Treasury — bond market's view of the economy
- Yield Curve (T10Y2Y) — negative = recession warning
- M2 Money Supply — more money printing = potential inflation = higher commodities

**Dollar & sentiment:**
- Trade Weighted USD — stronger dollar = cheaper imports = lower oil
- Consumer Sentiment — optimistic consumers drive more, spend more
- Business Confidence — corporate outlook indicator

**Oil-specific from FRED:**
- WTI Spot Price — validation against yfinance
- Brent Spot Price — validation source

### EIA — Supply/Demand Data

Weekly reports that move oil prices every Wednesday:
- **Crude oil inventories** — building up = bearish, drawing down = bullish
- **Spot prices** — official government price data
- **Weekly movements** — imports, exports, production flows

---

## How the Feature Engineering Works

Starting from raw OHLCV data, the system creates 60+ technical features:

**Returns:** 1-day, 5-day, 20-day price changes

**Moving Averages:** 5-day, 20-day, 50-day, 200-day, plus MA crossover signals (Golden Cross / Death Cross)

**Momentum Indicators:** RSI(14), MACD + signal line + histogram, Momentum(10, 30)

**Volatility:** 20-day and 60-day annualized, Bollinger Bands position (0-1)

**Spreads:** Brent-WTI spread

**Statistical Features (lagged 1 day):** Volatility at 5/20/60-day windows, price percentile vs last 20 days, return z-score

**Seasonality:** Day of week, month, quarter

**Target:** `Target_Return_1d` = next day's return

**Anti-lookahead bias:** All rolling features lagged by 1 day. Target uses `.shift(-1)`. The model only sees data actually available at each point.

---

## How the News Sentiment Works

### Sources

**Google News RSS** — XML feed, no key, headlines from hundreds of outlets.
**NewsAPI** — JSON API, free key, 80,000+ sources, best metadata.
**Reuters** — HTML scraping, no key, high-quality journalism.
**OilPrice.com** — HTML scraping, no key, oil-focused.

### Classification Methods

**Dictionary-Based** — Oil word lists + negation. Fast, transparent. Misses context.
**Rule-Based** — Intensity scores + boosters ("sharply falls" > "falls"). Captures degree.
**TF-IDF + LogReg** — ML on word patterns. Learns combinations. Limited by training data.
**VADER** (optional) — General sentiment from NLTK. Good cross-check.

### Consensus

Score = average of all methods. Label = majority vote.
- `3/3` = all agree → high confidence
- `2/3` = one disagrees → moderate
- `1/3` = all disagree → ambiguous

### News Weight

Not guessed — measured empirically. Correlation between yesterday's sentiment and today's price return determines the weight (typically 0.05-0.20).

---

## How the Prediction Models Work

**ARIMA(5,1,2)** — Classic time series. 5 AR terms, 1 differencing, 2 MA terms. Captures momentum and mean-reversion.

**XGBoost** — Gradient boosted trees on 80+ features. Predicts returns, provides **feature importance**. Key competition deliverable.

**Trend Baseline** — Momentum extrapolation. Sanity check — real models must beat it.

**Ensemble** — Averages all three. Walk-forward validation prevents overfitting.

---

## How the Regime Detection Works

Identifies bull/bear/crisis market states and shows **how risk factors change by regime**.

**HMM** — Hidden Markov Model, gold standard. Requires `pip install hmmlearn`.
**K-Means** — Clusters similar days. No extra dependencies.
**Rule-Based** — Explicit thresholds (drawdown >20% = crisis). Most transparent.

**Key insight:** Top factors are DIFFERENT per regime. Bull market: Heating Oil, Gasoline, RSI, USD. Bear market: Brent price, WTI price, Natural Gas, VIX.

---

## Output Files Reference

### `data/price/`
- `data_yfinance_raw.csv` — raw OHLCV, ~2800 rows
- `data_yfinance_featured.csv` — + 60 features, ~1800 rows
- `data_fred.csv` — macro indicators

### `data/news/`
- `scored_headlines.csv` — every headline scored (columns: `dict_score`, `rulebased_score`, `tfidf_score`, `consensus_score`, `consensus_label`, `agreement`)
- `daily_sentiment.csv` — daily aggregated (columns: `mean_sentiment`, `bullish_pct`, `bearish_pct`, `headline_count`, `sentiment_range`, `sentiment_ma3`, `sentiment_delta`)
- `report.txt`, `plots/`, `cache/`

### `data/news_live/`
- `live_sentiment.json` — rolling sentiment snapshot
- `all_headlines.json` — all headlines for dashboard

### `data/monitor/`
- `current_state.json` — latest risk assessment
- `risk_history.csv` — time series of readings
- `monitor.log`

### `data/predictions/`
- `forecast.json` — models, ensemble, feature importance

### `data/regime/`
- `regime_labels.csv` — every day labeled
- `regime_factor_importance.csv` — importance per regime
- `regime_report.txt`, `regime_summary.json`, `plots/`

---

## News Charts

**01 — Score Distributions:** Histograms per method. Green = bullish, red = bearish.
**02 — Headline Heatmap:** Top bullish + bearish across all methods. All-green = confident bullish.
**03 — Daily Timeline:** Sentiment bars + label proportions + volume per day.
**04 — Consensus & Agreement:** Pie chart of split + how often methods agree.
**05 — Source Breakdown:** Headlines per source + average sentiment per source.

---

## API Endpoints

All at `http://localhost:8081`:

**GET endpoints:**
- `/api/state` — main dashboard data (risk, price, technicals, sentiment)
- `/api/headlines` — all headlines in window
- `/api/predictions` — 5-day forecast
- `/api/regime` — regime analysis results
- `/api/news` — live sentiment snapshot
- `/api/daily` — daily sentiment history
- `/api/logs` — system log entries
- `/api/health` — server status

**POST endpoints:**
- `/api/predict` — run prediction models (~15 sec)
- `/api/regime/run` — run regime detection (~10 sec)
- `/api/collect` — re-collect price data
- `/api/scrape` — one-shot news scrape
- `/api/monitor/start` — start monitor
- `/api/monitor/stop` — stop monitor

---

## Running Components Standalone

```bash
cd oilPriceWebsite/backend/python

python oil_data_collector.py          # collect price data
python news_scraper.py                # one-shot scrape + report
python news_scraper.py --live 10      # live mode (10 min polls)
python monitor.py --interval 10       # risk monitor
python predictor.py                   # run predictions
python regime_detector.py             # regime detection
python main.py                        # full pipeline
python main.py --skip-data            # reuse existing CSVs
python main.py --report-only          # just regenerate report
```

---

## Troubleshooting

**"WTI_Crude_Close not found"**
→ yfinance MultiIndex fix needed. Add `if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)` after `yf.download()`.

**"Dropped all rows" / shape (0, N)**
→ Use vectorized `add_statistical_features` without `rolling.apply` lambdas.

**nodemon restart loop**
→ Add `nodemon.json`: `{"watch": ["server.js"], "ignore": ["data/", "python/"]}`.

**"name used prior to global declaration"**
→ Python 3.13. Move `global` to first line of function.

**Frontend "Cannot connect"**
→ Check backend running. Check Panel.jsx has `API_URL = 'http://localhost:8081/api'`.

**Prediction shows unrealistic price**
→ Delete `data/predictions/forecast.json`, click "Run Models" again.

**Same headlines every cycle**
→ Normal. RSS returns same until new articles publish.

**"int64 not JSON serializable"**
→ In regime_detector.py: `{k: int(v) for k, v in primary_labels.value_counts().items()}`.

**Missing modules**
→ `pip install xgboost statsmodels hmmlearn`

---

## Competition Strategy

1. **Quantitative factor ranking** — XGBoost ranks 80+ features by importance. Direct answer.
2. **Regime-dependent analysis** — factors CHANGE in bull vs bear vs crisis. Dynamic, not static.
3. **Geopolitics quantified** — 500+ headlines classified, correlation measured. Risk becomes a number.
4. **Real-time monitoring** — updates every 10 min with breaking news. Operational capability.
5. **Anti-bias architecture** — lagged features, walk-forward validation, measured weights. Defensible.