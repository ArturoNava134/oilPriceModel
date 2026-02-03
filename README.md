# Oil Price Risk Factor Analysis - Data Collection

**Author:** Arturo  
**Competition:** Citibank Oil Price Risk Factor Challenge

---

Hey! I set up our data pipeline. This doc explains how to get everything running and what data we're working with.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up your API keys (copy the template)
cp env.example .env
# Then edit .env and add your keys

# 3. Run the collector
python oil_data_collector.py
```

That's it. You'll get ~2,500 rows of daily data going back to 2015.

---

## What Data We're Collecting

### Yahoo Finance (works immediately, no setup)

This is our main data source. I picked these tickers:

| Ticker | What it is | Why we need it |
|--------|------------|----------------|
| CL=F | WTI Crude Futures | **Our main prediction target** |
| BZ=F | Brent Crude Futures | International benchmark, good for spread analysis |
| DX-Y.NYB | US Dollar Index | Oil is priced in USD - strong inverse correlation |
| ^VIX | Volatility Index | Spikes during crises, affects oil volatility |
| ^GSPC | S&P 500 | Proxy for economic health |
| NG=F | Natural Gas | Correlated energy commodity |
| XLE | Energy Sector ETF | Sector sentiment indicator |

### FRED - Federal Reserve Data (need free API key)

Macro indicators that drive oil demand. Get your key here:  
👉 https://fred.stlouisfed.org/docs/api/api_key.html

Key series:
- **GDP, Industrial Production** → economic activity = oil demand
- **CPI** → oil is a big inflation component
- **Fed Funds Rate, 10Y Treasury** → affects USD and economic growth
- **Yield Curve (T10Y2Y)** → negative = recession warning
- **Consumer Sentiment** → spending/driving expectations

### EIA - Energy Information Administration (need free API key)

This is the really good stuff - actual supply/demand data. Get your key:  
👉 https://www.eia.gov/opendata/register.php

What we get:
- **Weekly crude inventories** → this moves prices every Wednesday
- **US production data** → supply side
- **Import/export flows** → trade dynamics

---

## Output Files

After running the script, you'll have:

| File | What's in it |
|------|--------------|
| `data_yfinance_raw.csv` | Raw OHLCV data from Yahoo Finance |
| `data_yfinance_featured.csv` | Same data + 25 technical indicators I added |
| `data_fred.csv` | Macro indicators (if you set up the API key) |

---

## Feature Engineering

I already built in a bunch of technical indicators:

**Trend indicators:**
- Moving averages (5, 20, 50, 200 day)
- MA crossover signals (golden cross, etc.)
- MACD

**Momentum:**
- RSI (14-day)
- Price momentum (10, 30 day)

**Volatility:**
- Bollinger Bands
- 20-day and 60-day volatility (annualized)

**Other:**
- Brent-WTI spread
- Day of week, month, quarter (seasonality)

Feel free to add more in the `engineer_features()` function!

---

## Factor Categories for Our Model

Based on the challenge requirements, here's how I'm thinking about organizing our factors:

### 1. Supply Factors
- US crude inventories (EIA weekly data)
- OPEC production announcements (we might need to scrape this)
- US shale rig counts
- SPR releases

### 2. Demand Factors
- GDP growth
- Industrial production
- PMI data
- Driving season (summer = more gas demand)

### 3. Financial/Macro Factors
- USD strength (DXY) - **this is huge, inverse correlation**
- Interest rates
- Stock market performance
- VIX (fear = oil volatility)

### 4. Geopolitical (harder to quantify)
- Middle East tensions
- Russia/Ukraine
- OPEC+ decisions
- US sanctions

---

## Backup Option: Manual Download

If the APIs are giving you trouble, you can manually grab data from Investing.com:

1. **WTI:** https://www.investing.com/commodities/crude-oil-historical-data
2. **Brent:** https://www.investing.com/commodities/brent-oil-historical-data

Just set your date range and click "Download Data". But try to use the script - it's more reproducible for our submission.

---

## Next Steps

Once we have the data, here's the modeling approach I'm thinking but isn't implemented yet:

1. **EDA** - correlation matrix, see which factors actually matter
2. **Stationarity tests** - ADF test, might need to difference the series
3. **Factor analysis** - PCA to reduce dimensions, Granger causality
4. **Models to try:**
   - ARIMA as baseline
   - XGBoost (gives us feature importance for free)
   - LSTM if we want to go deep learning
5. **Backtesting** - walk-forward validation, not just train/test split
