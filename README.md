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
│   │       ├── price/                ← data_yfinance_raw.csv, data_yfinance_featured.csv, data_fred.csv
│   │       ├── news/                 ← scored_headlines.csv, daily_sentiment.csv, plots/
│   │       ├── news_live/            ← live_sentiment.json, all_headlines.json
│   │       ├── monitor/              ← current_state.json, risk_history.csv
│   │       ├── predictions/          ← forecast.json
│   │       └── analysis/             ← final_report.txt, combined_summary.csv
│   └── frontend/
│       └── src/
│           ├── App.jsx
│           └── components/
│               ├── pages/Panel.jsx   ← Main dashboard
│               └── auth/Login.jsx
├── requirements.txt                  ← Python dependencies (single file for everything)
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

The frontend uses `react`, `react-router-dom`, `recharts` (for charts), `lucide-react` (for icons), and `tailwindcss`.

### Step 4: Get API Keys

The system works without any keys — Yahoo Finance and Google News RSS need no authentication. Adding these free keys gives significantly more data:

#### FRED API Key (Federal Reserve Economic Data)

Gives macroeconomic indicators: GDP, CPI, interest rates, yield curve, unemployment, money supply, consumer sentiment. These are the fundamental demand-side drivers of oil prices.

1. Go to **https://fred.stlouisfed.org/docs/api/api_key.html**
2. Create an account (takes 2 minutes)
3. Request an API key
4. Copy the key

#### EIA API Key (Energy Information Administration)

Gives actual oil supply/demand data: weekly crude inventories, production numbers, import/export flows. The weekly inventory report is one of the single biggest movers of oil prices — when inventories build up, prices typically drop; when they draw down, prices rise.

1. Go to **https://www.eia.gov/opendata/register.php**
2. Register (takes 2 minutes)
3. Copy the key

#### NewsAPI Key (Optional but Recommended)

Gives more headlines from 80,000+ news sources with better metadata (exact dates, descriptions, source names). Without it, the system still scrapes Google News RSS, Reuters, and OilPrice.com — enough for good sentiment coverage.

1. Go to **https://newsapi.org/register**
2. Create account (30 seconds)
3. Copy the key
4. Free tier: 100 requests/day, 1 month of article history

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

This does everything:
- Starts the Express API server on port 8081
- Automatically spawns the Python monitor as a child process
- Monitor loads price data (downloads on first run, takes ~2 minutes)
- Monitor starts polling news every 10 minutes
- Monitor fetches live WTI price every cycle from Yahoo Finance
- All data is served via JSON API endpoints

**Terminal 2 — Frontend:**
```bash
cd oilPriceWebsite/frontend
npm run dev
```

Open **http://localhost:5173/panel** in your browser.

The dashboard populates within 1-2 minutes as the first news cycle completes.

---

## What the Dashboard Shows

### Risk Assessment (Top Left)

This is the main output — a single score from -1 to +1 that combines all signals into one answer.

* **Score Range: +0.40 to +1.0**
    * **Label:** **LOW RISK**
    * **What It Means:** Strong bullish signals. Oil is likely to hold steady or rise.

* **Score Range: +0.15 to +0.40**
    * **Label:** **LOW-MODERATE**
    * **What It Means:** Slightly bullish. More signals point up than down.

* **Score Range: -0.15 to +0.15**
    * **Label:** **MODERATE**
    * **What It Means:** Mixed signals. Market could go either way.

* **Score Range: -0.40 to -0.15**
    * **Label:** **ELEVATED**
    * **What It Means:** Bearish signals building. Downside is more likely.

* **Score Range: -1.0 to -0.40**
    * **Label:** **HIGH RISK**
    * **What It Means:** Strong bearish signals. Significant decline risk.

Below the score, a **horizontal bar chart** shows what's pushing the number up or down. Green bars are bullish (pushing prices up), red bars are bearish (pushing down). The length shows how strong that signal is, and the percentage is how much weight it gets in the final score.

The signals and their weights:
- **Trend (30%)** — Is the 50-day moving average above or below the 200-day? This is the most reliable long-term directional signal. When the shorter MA crosses above the longer one, it's called a "Golden Cross" (bullish). Below = "Death Cross" (bearish).
- **RSI Momentum (15%)** — Relative Strength Index, a momentum oscillator from 0-100. Think of it like a speedometer: above 70 means oil has risen too fast and might slow down (overbought). Below 30 means it's fallen too fast and might bounce (oversold). 30-70 is normal.
- **MACD Direction (15%)** — Moving Average Convergence Divergence. Confirms whether momentum is accelerating upward (positive = bullish) or downward (negative = bearish).
- **Recent Returns (15%)** — What actually happened in the last 5 trading days. If oil dropped 5%, that's a strong bearish signal regardless of what indicators say.
- **VIX / Market Fear (10%)** — The "fear index" for the stock market. Below 20 = calm markets. 20-30 = worried. Above 30 = panicking. When VIX spikes, oil usually gets volatile too.
- **News Sentiment (empirically measured)** — The overall mood of recent oil headlines. The weight isn't guessed — it's calculated from the historical correlation between yesterday's sentiment and today's price movement.

### Live Price + Technicals (Top Center)

The current WTI crude oil price, fetched from Yahoo Finance every 10 minutes. Below it, three return cards show:
- **Today** — price change in the last trading session
- **This Week** — change over the last 5 trading days
- **This Month** — change over the last 20 trading days (~1 month)

Green = price went up. Red = price went down.

The **technical indicators** section:
- **Trend** — uptrend ("Golden Cross": 50-day MA > 200-day MA) or downtrend ("Death Cross": 50-day MA < 200-day MA). The most reliable long-term signal.
- **RSI** — momentum from 0-100. Above 70 = overbought (might pull back). Below 30 = oversold (might bounce). 30-70 = normal.
- **VIX** — fear gauge. Below 20 = calm. 20-30 = elevated worry. Above 30 = market panic.
- **MACD** — bullish (positive) or bearish (negative) momentum direction.
- **Volatility** — how wild the price swings are, annualized. Below 20% = very calm. 20-35% = normal. Above 40% = extremely choppy, expect big daily moves.
- **Brent-WTI Spread** — the gap between international oil (Brent) and US oil (WTI). A positive spread is normal. Wide spread (>$5) means global supply is tighter than US supply.

Every indicator has a **?** icon — hover over it for a plain-English explanation of what it means and why it matters.

### 5-Day Forecast (Top Right)

Click **"Run Models"** to train prediction models and generate a 5-day price forecast. Takes about 15 seconds. Shows:

- **Direction call** — UP, DOWN, or FLAT with the predicted price and percentage change
- **Area chart** — visual trajectory of the forecast (green if up, red if down)
- **Individual models** — each model's prediction with its backtest accuracy
- **Top Price Drivers** — the features XGBoost found most important for predicting next-day returns. This directly answers the competition question about key risk factors.

The Models
ARIMA(5,1,2)

Type: Time series

Function: Captures trend and mean-reversion patterns.

Strength: Particularly effective at identifying short-term momentum.

XGBoost

Type: Gradient boosting

Function: Processes over 80 features to predict next-day returns.

Strength: Excels at finding non-linear patterns and providing feature importance rankings.

Trend Baseline

Type: Simple extrapolation

Function: Projects recent momentum directly forward.

Strength: Serves as a vital sanity check; sophisticated models must outperform this to prove their worth.


The ensemble averages all three. Backtesting uses walk-forward validation (train on all-but-last-20-days, test on last 20) to prevent overfitting.

### News Feed (Bottom Left)

All scraped headlines in a scrollable list, newest first. Each headline shows:
- **Colored dot** — green (bullish), red (bearish), gray (neutral)
- **Headline text**
- **Source** (Reuters, Bloomberg, etc.) and **date**
- **Sentiment score** — from -1.0 to +1.0

Use the **filter tabs** (All / Bullish / Bearish / Neutral) to focus on specific types.

The system scrapes Google News RSS every 10 minutes with 5 different oil-related queries ("crude oil price", "OPEC oil production", "oil supply demand", "WTI Brent crude", "oil sanctions geopolitical"). It deduplicates headlines and keeps a 120-minute rolling window. You'll see ~95 headlines on the first cycle, then new ones trickling in as outlets publish fresh articles.

### Sentiment Overview (Bottom Right)

**Donut chart** showing the bullish/neutral/bearish split across all headlines in the window.

The **sentiment score** is the average across all headlines. Positive means the market narrative leans bullish, negative means bearish. Near zero means balanced.

### System Log

Live feed of what the Python monitor is doing: data refreshes, headline counts, risk score updates, errors. Color-coded: blue = system, green = data, red = errors, purple = predictions.

---

## How the Data Collection Works

### Yahoo Finance — Price Data

Downloads 10 years of daily OHLCV (Open, High, Low, Close, Volume) data for 12 tickers:

* **Ticker:** CL=F
    * **Name:** WTI Crude
    * **Why It's Included:** **Main prediction target** — the US oil benchmark

* **Ticker:** BZ=F
    * **Name:** Brent Crude
    * **Why It's Included:** International benchmark — used for spread analysis

* **Ticker:** NG=F
    * **Name:** Natural Gas
    * **Why It's Included:** Correlated energy commodity

* **Ticker:** HO=F
    * **Name:** Heating Oil
    * **Why It's Included:** Downstream oil product

* **Ticker:** RB=F
    * **Name:** Gasoline
    * **Why It's Included:** Downstream oil product

* **Ticker:** DX-Y.NYB
    * **Name:** US Dollar Index
    * **Why It's Included:** Oil is priced in USD — strong inverse correlation

* **Ticker:** ^GSPC
    * **Name:** S&P 500
    * **Why It's Included:** Proxy for overall economic health

* **Ticker:** ^VIX
    * **Name:** VIX
    * **Why It's Included:** Fear gauge — spikes during market crises

* **Ticker:** XLE
    * **Name:** Energy Sector ETF
    * **Why It's Included:** Sector-level sentiment

* **Ticker:** USO
    * **Name:** Oil ETF
    * **Why It's Included:** Retail investor sentiment

* **Ticker:** GC=F
    * **Name:** Gold
    * **Why It's Included:** Safe haven — tends to move opposite to risk assets

* **Ticker:** SI=F
    * **Name:** Silver
    * **Why It's Included:** Safe haven asset

### FRED — Macroeconomic Data

Pulls 15 economic indicators that drive oil demand:

* **Series: GDP / Real GDP**
    * **Name:** Economic growth
    * **Why It Matters:** More growth = more oil demand

* **Series: Industrial Production**
    * **Name:** Factory output
    * **Why It Matters:** Factories are heavy oil consumers

* **Series: CPI**
    * **Name:** Inflation
    * **Why It Matters:** Oil is a big component of consumer prices

* **Series: Unemployment Rate**
    * **Name:** Labor market
    * **Why It Matters:** Affects driving, spending, economic outlook

* **Series: Fed Funds Rate**
    * **Name:** Interest rates
    * **Why It Matters:** Affects USD strength and economic activity

* **Series: 10Y Treasury**
    * **Name:** Long-term rates
    * **Why It Matters:** Bond market's view of the economy

* **Series: Yield Curve (T10Y2Y)**
    * **Name:** Recession indicator
    * **Why It Matters:** Negative = recession warning

* **Series: Trade Weighted USD**
    * **Name:** Dollar strength
    * **Why It Matters:** Stronger dollar = cheaper imports = lower oil

* **Series: M2 Money Supply**
    * **Name:** Money printing
    * **Why It Matters:** More money = potential inflation = higher commodities

* **Series: Consumer Sentiment**
    * **Name:** Confidence
    * **Why It Matters:** Optimistic consumers drive more, spend more

* **Series: Gas Prices**
    * **Name:** Retail fuel
    * **Why It Matters:** Downstream demand indicator

### EIA — Supply/Demand Data

Weekly reports that move oil prices every Wednesday:
- **Crude oil inventories** — building up = bearish, drawing down = bullish
- **Spot prices** — official government price data
- **Weekly movements** — imports, exports, production flows

---

## How the Feature Engineering Works

Starting from raw OHLCV data, the system creates 60+ technical features:

**Returns** — price change over 1, 5, and 20 trading days

**Moving Averages** — 5-day, 20-day, 50-day, 200-day
- MA crossover signals: when the short MA crosses above the long MA, it's a bullish signal ("Golden Cross")

**Momentum Indicators:**
- RSI(14) — relative strength index, overbought/oversold oscillator
- MACD — trend-following momentum, includes signal line and histogram
- Momentum(10, 30) — raw price change over N days

**Volatility:**
- 20-day and 60-day annualized volatility (how wild the price swings are)
- Bollinger Bands — price relative to its recent range (position 0-1)

**Spreads:**
- Brent-WTI spread — gap between international and US oil

**Statistical Features (with lookahead protection):**
- Volatility at 5/20/60-day windows, all lagged by 1 day
- Price percentile — where current price sits vs the last 20 days
- Return z-score — how unusual today's return is vs recent history

**Seasonality:**
- Day of week, month, quarter (oil has seasonal demand patterns)

**Target variable:** `Target_Return_1d` = next day's return (what we're predicting)

**Anti-lookahead bias:** All rolling features are lagged by 1 day using `.shift(1)`. The target uses `.shift(-1)`. This means at any point in time, the model only sees data that was actually available — it never accidentally uses tomorrow's information to predict tomorrow.

---

## How the News Sentiment Works

### Where the Data Comes From

* **Source: Google News RSS**
    * **Method:** XML feed for oil search queries
    * **API Key?:** No
    * **What You Get:** Headlines from hundreds of outlets with real dates

* **Source: NewsAPI**
    * **Method:** Structured JSON API
    * **API Key?:** Yes (free)
    * **What You Get:** Best metadata — exact dates, descriptions

* **Source: Reuters**
    * **Method:** HTML scraping of energy section
    * **API Key?:** No
    * **What You Get:** High-quality financial journalism

* **Source: OilPrice.com**
    * **Method:** HTML scraping
    * **API Key?:** No
    * **What You Get:** Almost every headline is oil-relevant

### Classification Methods

Each headline gets scored by 3 methods independently:

**Method 1: Dictionary-Based**
Two word lists — positive words ("surge", "rally", "cut", "shortage", "rebound") and negative words ("crash", "glut", "recession", "fear", "selloff"). Counts matches and produces a score. Handles negation — "oil not expected to rally" flips "rally" to negative because of "not."

*Pro:* Fast, transparent. *Con:* Misses context.

**Method 2: Rule-Based (VADER-like)**
Same word lists, but each word has an intensity score: "crashes" = -0.7, "falls" = -0.4, "dips" = -0.2. Also understands boosters: "sharply falls" scores more negative than just "falls." "Slightly drops" scores less negative than "drops."

*Pro:* Captures intensity. *Con:* Still keyword-based.

**Method 3: TF-IDF + Logistic Regression**
Machine learning. Converts headlines into numeric vectors using TF-IDF (measures how important each word is in the context of all headlines), then a logistic regression classifier decides bullish/neutral/bearish. Trained on synthetic oil headlines generated from the word lists.

*Pro:* Learns word combinations. *Con:* Only as good as the training templates.

**Bonus: VADER (if nltk installed)**
Pre-trained general-purpose sentiment analyzer from NLTK. Not oil-specific but good as a cross-check. Automatically enabled if you run `pip install nltk`.

### How Consensus Works

The final score is the **average** of all available methods. The label is decided by **majority vote**. The `agreement` field tells you confidence:
- `3/3` or `4/4` = all methods agree → high confidence
- `2/3` = one method disagrees → moderate confidence
- `1/3` = all disagree → ambiguous headline, treat with caution

### How the News Weight Is Measured

The weight news sentiment gets in the risk model isn't guessed. The monitor calculates the historical correlation between yesterday's sentiment and today's price return. If the correlation is 0.12, news gets 12% weight. If it's 0.03, it's effectively noise. This is recalculated every time price data refreshes.

Typical values for oil are 0.05-0.20 depending on how eventful the news period is.

---

## How the Prediction Models Work

### ARIMA(5,1,2)
Classic time series model. The (5,1,2) means: 5 autoregressive terms (last 5 days of prices), 1 differencing step (removes trend to make the series stationary), and 2 moving average terms (smooths random noise). Good at capturing short-term momentum and mean-reversion.

### XGBoost
Gradient boosted decision trees trained on all 80+ features from the price dataset. Predicts next-day returns, then applies the average predicted return forward for 5 days. The key advantage is **feature importance** — XGBoost ranks which features it relied on most, which directly answers the competition question.

### Trend Baseline
Simple extrapolation: takes the recent 5-day and 20-day price trends, averages them, and extends forward. Every real model should beat this. If they don't, the real models are overfitting.

### Ensemble
Averages all three forecasts. Backtesting uses walk-forward validation: train on everything except the last 20 days, test on those 20 days. This prevents the common ML pitfall of overfitting to the training set.

---

## Output Files Reference

### Price Data (`data/price/`)

* **File: data_yfinance_raw.csv**
    * **Contents:** Raw OHLCV data, ~2800 rows, 60 columns

* **File: data_yfinance_featured.csv**
    * **Contents:** Same + 60 engineered features, ~1800 rows (after dropna)

* **File: data_fred.csv**
    * **Contents:** FRED macro indicators, 15 columns

### News Data (`data/news/`)

* **File: scored_headlines.csv**
    * **Contents:** Every headline with scores from all methods

* **File: daily_sentiment.csv**
    * **Contents:** One row per day — aggregated sentiment

* **File: report.txt**
    * **Contents:** Full text report with top headlines and daily summary

* **File: plots/**
    * **Contents:** 5 visualization charts

* **File: cache/**
    * **Contents:** Cached headlines by date (avoids re-scraping)

**Scored Headlines CSV — Column Guide:**

* **Column: dict_score**
    * **What It Means:** Dictionary method score (-1 to +1)

* **Column: rulebased_score**
    * **What It Means:** Rule-based method score (-1 to +1)

* **Column: tfidf_score**
    * **What It Means:** ML method score (-1 to +1)

* **Column: vader_score**
    * **What It Means:** VADER score (only if nltk installed)

* **Column: consensus_score**
    * **What It Means:** **Average of all methods — the main number**

* **Column: consensus_label**
    * **What It Means:** **bullish / neutral / bearish — the main label**

* **Column: agreement**
    * **What It Means:** "3/3" = all agree, "2/3" = one disagrees

**Daily Sentiment CSV — Column Guide:**

* **Column: mean_sentiment**
    * **What It Means:** Average score that day
    * **Why It Matters:** Main sentiment feature for modeling

* **Column: bullish_pct**
    * **What It Means:** % of headlines that were bullish
    * **Why It Matters:** Market optimism level

* **Column: bearish_pct**
    * **What It Means:** % that were bearish
    * **Why It Matters:** Market fear level

* **Column: headline_count**
    * **What It Means:** Headlines that day
    * **Why It Matters:** Spikes = big news event

* **Column: sentiment_range**
    * **What It Means:** Max minus min score
    * **Why It Matters:** High = headlines contradict each other

* **Column: sentiment_ma3**
    * **What It Means:** 3-day moving average
    * **Why It Matters:** Smoothed trend direction

* **Column: sentiment_delta**
    * **What It Means:** Day-over-day change
    * **Why It Matters:** Is sentiment improving or worsening?

### Live Data (`data/news_live/`)

* **File: live_sentiment.json**
    * **Contents:** Current rolling sentiment snapshot

* **File: all_headlines.json**
    * **Contents:** Every headline in the current window (for the dashboard)

### Monitor Data (`data/monitor/`)

* **File: current_state.json**
    * **Contents:** Latest risk assessment with all metrics

* **File: risk_history.csv**
    * **Contents:** Time series of every risk reading

* **File: monitor.log**
    * **Contents:** Debug log

### Predictions (`data/predictions/`)

* **File: forecast.json**
    * **Contents:** Latest forecast from all models, ensemble, feature importance

---

## News Charts (from `news_scraper.py` normal mode)

### 01 — Score Distributions
Histograms showing how each method distributes its scores. Green = bullish scores, red = bearish. If all 3 methods show more red than green, the bearish signal is strong.

### 02 — Headline Heatmap
The 15 most bullish + 15 most bearish headlines scored across all methods. All-green rows = high-confidence bullish. All-red = high-confidence bearish. Mixed colors = ambiguous.

### 03 — Daily Timeline
Three stacked panels: daily sentiment bars (green/red) with 3-day MA, bullish/neutral/bearish proportions stacked over time, and news volume per day (spikes = big events).

### 04 — Consensus & Agreement
Pie chart of overall bullish/neutral/bearish split. Bar chart showing how often methods agree ("3/3" = reliable, "1/3" = noisy).

### 05 — Source Breakdown
Which sources contributed the most headlines, and average sentiment per source. Useful for spotting media bias.

---

## API Endpoints

All served from `http://localhost:8081`:

* **Endpoint: /api/state**
    * **Method:** GET
    * **Returns:** Risk score, live price, technicals, sentiment — everything for the dashboard

* **Endpoint: /api/headlines**
    * **Method:** GET
    * **Returns:** All headlines in the current news window

* **Endpoint: /api/predictions**
    * **Method:** GET
    * **Returns:** Latest 5-day forecast from all models

* **Endpoint: /api/news**
    * **Method:** GET
    * **Returns:** Live sentiment snapshot

* **Endpoint: /api/daily**
    * **Method:** GET
    * **Returns:** Daily sentiment history

* **Endpoint: /api/logs**
    * **Method:** GET
    * **Returns:** System log entries

* **Endpoint: /api/health**
    * **Method:** GET
    * **Returns:** Server status and file availability checks

* **Endpoint: /api/predict**
    * **Method:** POST
    * **Returns:** Trigger prediction model training (~15 sec)

* **Endpoint: /api/collect**
    * **Method:** POST
    * **Returns:** Trigger price data re-collection

* **Endpoint: /api/scrape**
    * **Method:** POST
    * **Returns:** Trigger one-shot news scrape with full report

* **Endpoint: /api/monitor/start**
    * **Method:** POST
    * **Returns:** Start the Python monitor process

* **Endpoint: /api/monitor/stop**
    * **Method:** POST
    * **Returns:** Stop the Python monitor process

---

## Running Individual Components

The backend runs everything automatically, but you can also run scripts standalone:

```bash
cd oilPriceWebsite/backend/python

# Collect price data (downloads from Yahoo Finance, FRED, EIA)
python oil_data_collector.py

# Run news scraper — one-shot with full report + 5 charts
python news_scraper.py

# Run news scraper in live mode (polls every 10 min)
python news_scraper.py --live 10

# Run the live risk monitor (same as what server.js spawns)
python monitor.py --interval 10 --window 120

# Run prediction models
python predictor.py

# Run the full analysis pipeline (collector + scraper + report)
python main.py
python main.py --skip-data      # reuse existing price CSVs
python main.py --skip-news      # reuse existing news data
python main.py --report-only    # just regenerate the final report
```

---

## Troubleshooting

* **Problem: "WTI_Crude_Close not found"**
    * **Fix:** yfinance changed its column format to MultiIndex. Make sure `oil_data_collector.py` has: `if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)` right after `yf.download()`.

* **Problem: "Dropped all rows" / shape (0, N)**
    * **Fix:** The `add_statistical_features` function is producing all-NaN columns. Use the vectorized version without `rolling.apply` lambdas.

* **Problem: nodemon keeps restarting in a loop**
    * **Fix:** Monitor writes JSON files → nodemon detects → restarts. Add `nodemon.json` in backend/: `{"watch": ["server.js"], "ignore": ["data/", "python/"]}`. Or just use `node server.js` instead of `npm start`.

* **Problem: "SyntaxError: name used prior to global declaration"**
    * **Fix:** Python 3.13 strictness. Move `global VARIABLE` to the very first line of the function.

* **Problem: "datetime.utcnow() is deprecated"**
    * **Fix:** Cosmetic warning in Python 3.12+. Replace `datetime.utcnow()` with `datetime.now()`. Doesn't affect functionality.

* **Problem: Frontend shows "Cannot connect to API server"**
    * **Fix:** Check backend is running (`node server.js` in `oilPriceWebsite/backend/`). Check `Panel.jsx` has `const API_URL = 'http://localhost:8081/api'`.

* **Problem: Prediction shows unrealistic price ($0.14)**
    * **Fix:** Stale forecast from a bugged run. Delete `data/predictions/forecast.json` and click "Run Models" again.

* **Problem: Same ~97 headlines every 10 minutes**
    * **Fix:** Normal behavior. Google News RSS returns the same articles until new ones are published. Over hours, the count grows as outlets publish. Old headlines are pruned after the 120-minute window.

* **Problem: Price doesn't match OilPrice.com**
    * **Fix:** The CSV price is from the last data collection run. The live price (shown as "WTI LIVE" on the dashboard) updates every 10 minutes and should match within a few cents.

* **Problem: "ModuleNotFoundError: No module named 'xgboost'"**
    * **Fix:** `pip install xgboost` — needed for predictions.

* **Problem: "ModuleNotFoundError: No module named 'statsmodels'"**
    * **Fix:** `pip install statsmodels` — needed for ARIMA.

* **Problem: "FRED DATA - NEED API KEY"**
    * **Fix:** Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html and add `FRED_API_KEY=your_key` to `.env`.

* **Problem: No headlines scraped at all**
    * **Fix:** Check internet connection. Google News RSS is the most reliable source — if it fails, it's probably a network issue.

---

## Competition Strategy

The competition asks: "What are the key risk factors for oil prices?"

This project answers from multiple angles:

1. **Quantitative factor ranking** — XGBoost trains on 80+ features and ranks which ones matter most for predicting next-day price movements. Top factors typically include USD strength, VIX, Bollinger Band position, S&P 500, and energy ETF prices. This is a direct, data-driven answer with numbers attached.

2. **Regime-dependent analysis** — the top factors change depending on whether the market is in a bull, bear, or crisis state. In calm markets, USD strength is the #1 driver. During crises, volatility and drawdown dominate. This insight separates a good submission from a great one.

3. **Geopolitics quantified** — most teams list "geopolitics" as a risk factor but can't measure it. This system actually scrapes 500+ headlines from real news sources, classifies them with 3 independent methods, produces a daily sentiment index, and measures its empirical correlation with price movements. Geopolitical risk becomes a number, not a bullet point.

4. **Real-time monitoring** — the system doesn't just produce a static report. It runs continuously, updates every 10 minutes, and shows how the risk assessment changes in response to breaking news. This demonstrates operational capability, not just analytical capability.

5. **Anti-bias architecture** — all features lagged by 1 day, walk-forward validation instead of random splits, empirically measured weights instead of guesses. The methodology is designed to be defensible under scrutiny.