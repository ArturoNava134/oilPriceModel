"""
Oil Price Risk Factor Analysis - Data Collection Script
--------------------------------------------------------
Competition: Citibank Oil Price Risk Factor Challenge

It pulls from three main sources - Yahoo Finance works out of the box,
and FRED/EIA need free API keys (takes 2 mins to set up).

HOW TO RUN:
1. Copy env.example to .env and add your API keys
this is the .env example 

# Oil Price Data Collector - Environment Variables
# ================================================
# Copy this file to .env and fill in your API keys
# NEVER commit your actual .env file to git!

# FRED API Key (Federal Reserve Economic Data)
# Get yours free at: https://fred.stlouisfed.org/docs/api/api_key.html
FRED_API_KEY=your_fred_api_key_here

# EIA API Key (Energy Information Administration)
# Get yours free at: https://www.eia.gov/opendata/register.php
EIA_API_KEY=your_eia_api_key_here


2. pip install -r requirements.txt
3. python oil_data_collector.py

The script will generate two CSV files we can use for modeling.
Hit me up if anything breaks!
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# NEW IMPORTS for statistical features and validation
from scipy import stats

# Loading our API keys from the .env file
# This keeps them out of git - never commit real keys!
from dotenv import load_dotenv
load_dotenv()

FRED_API_KEY = os.getenv("FRED_API_KEY")
EIA_API_KEY = os.getenv("EIA_API_KEY")


# YAHOO FINANCE DATA
# This is our main data source - no API key needed, just works

def collect_yfinance_data(start_date="2015-01-01", end_date=None):
    """
    Pulls oil prices and related market data from Yahoo Finance.
    
    I chose these specific tickers because they give us good coverage of:
    - Oil benchmarks (WTI, Brent)
    - Related energy commodities (natural gas, heating oil, gasoline)
    - Key factors that affect oil prices (USD, stock market, volatility)
    
    No API key needed - this should just work.
    """
    import yfinance as yf
    
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    print("=" * 60)
    print("PULLING YAHOO FINANCE DATA")
    print("=" * 60)
    
    # Here's what we're downloading and why:
    tickers = {
        # Our main targets - these are what we're trying to predict
        "CL=F": "WTI_Crude",           # WTI is the US benchmark
        "BZ=F": "Brent_Crude",         # Brent is the international benchmark
        
        # Related energy products - they move together, useful for features
        "NG=F": "Natural_Gas",
        "HO=F": "Heating_Oil",
        "RB=F": "Gasoline",
        
        # USD Index - super important! Oil is priced in dollars,
        # so when USD goes up, oil typically goes down
        "DX-Y.NYB": "USD_Index",
        
        # Market health indicators
        "^GSPC": "SP500",              # Overall economy proxy
        "^VIX": "VIX",                 # Fear gauge - spikes during crises
        
        # Energy sector specific
        "XLE": "Energy_Sector_ETF",
        "USO": "Oil_ETF",
        
        # Safe haven assets - inverse correlation with risk assets
        "GC=F": "Gold",
        "SI=F": "Silver",
    }
    
    all_data = {}
    
    for ticker, name in tickers.items():
        print(f"Downloading {name} ({ticker})...")
        try:
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if len(data) > 0:
                df = data[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
                df.columns = [f"{name}_{col}" for col in df.columns]
                all_data[name] = df
                print(f"  ✓ Got {len(df)} rows")
            else:
                print(f"  ✗ No data returned")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    if all_data:
        combined = pd.concat(all_data.values(), axis=1)
        combined.index = pd.to_datetime(combined.index)
        print(f"\nCombined dataset: {combined.shape[0]} rows, {combined.shape[1]} columns")
        return combined
    return None


# FRED DATA (Federal Reserve Economic Data)
# This gives us the macro indicators - GDP, inflation, interest rates, etc.

def collect_fred_data(api_key=None, start_date="2015-01-01"):
    """
    Pulls macroeconomic data from the Federal Reserve.
    
    You need a free API key for this:
    1. Go to https://fred.stlouisfed.org/docs/api/api_key.html
    2. Create account, request key
    3. Add to your .env file: FRED_API_KEY=your_key_here
    
    This data is crucial for our factor analysis - things like GDP growth,
    inflation, and interest rates all impact oil demand and prices.
    """
    api_key = api_key or FRED_API_KEY
    
    if api_key is None:
        print("\n" + "=" * 60)
        print("FRED DATA - NEED API KEY")
        print("=" * 60)
        print("To get this data working:")
        print("1. Get free key: https://fred.stlouisfed.org/docs/api/api_key.html")
        print("2. Add to .env: FRED_API_KEY=your_key_here")
        print("3. Re-run the script")
        return None
    
    from fredapi import Fred
    fred = Fred(api_key=api_key)
    
    print("\n" + "=" * 60)
    print("PULLING FRED DATA")
    print("=" * 60)
    
    # I picked these series because they're the main macro drivers of oil:
    series = {
        # Official oil spot prices (good for validation against yfinance)
        'DCOILWTICO': 'WTI_Spot_FRED',
        'DCOILBRENTEU': 'Brent_Spot_FRED',
        
        # Economic growth - more growth = more oil demand
        'GDP': 'US_GDP',
        'GDPC1': 'Real_GDP',
        'INDPRO': 'Industrial_Production',  # Factories use lots of oil
        
        # Inflation - oil is a big component of CPI
        'CPIAUCSL': 'CPI',
        
        # Labor market
        'UNRATE': 'Unemployment_Rate',
        
        # Interest rates - affect USD strength and economic activity
        'FEDFUNDS': 'Fed_Funds_Rate',
        'DGS10': 'Treasury_10Y',
        'T10Y2Y': 'Yield_Curve',  # Negative = recession warning
        
        # Dollar strength (different measure than DXY)
        'DTWEXBGS': 'Trade_Weighted_USD',
        
        # Money supply - more money printing can mean inflation/higher oil
        'M2SL': 'M2_Money_Supply',
        
        # Sentiment indicators
        'UMCSENT': 'Consumer_Sentiment',
        'BSCICP03USM665S': 'Business_Confidence',
        
        # Retail gas prices - downstream indicator
        'GASREGW': 'US_Gas_Price',
    }
    
    all_data = {}
    
    for series_id, name in series.items():
        print(f"Downloading {name} ({series_id})...")
        try:
            data = fred.get_series(series_id, observation_start=start_date)
            if len(data) > 0:
                all_data[name] = data
                print(f"  ✓ Got {len(data)} observations")
            else:
                print(f"  ✗ No data")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    if all_data:
        combined = pd.DataFrame(all_data)
        combined.index = pd.to_datetime(combined.index)
        print(f"\nFRED dataset: {combined.shape[0]} rows, {combined.shape[1]} columns")
        return combined
    return None



# EIA DATA (Energy Information Administration)
# actual inventory and production numbers


def collect_eia_data(api_key=None):
    """
    Pulls energy-specific data from the US Energy Information Administration.
    
    You need a free API key:
    1. Go to https://www.eia.gov/opendata/register.php
    2. Register, get key
    3. Add to .env: EIA_API_KEY=your_key_here
    
    This data is gold for our model - weekly inventory reports are one of
    the biggest movers of oil prices. When inventories build up, prices drop.
    When they draw down, prices rise.
    """
    api_key = api_key or EIA_API_KEY
    
    if api_key is None:
        print("\n" + "=" * 60)
        print("EIA DATA - NEED API KEY")
        print("=" * 60)
        print("To get this data working:")
        print("1. Get free key: https://www.eia.gov/opendata/register.php")
        print("2. Add to .env: EIA_API_KEY=your_key_here")
        print("3. Re-run the script")
        return None
    
    import requests
    
    print("\n" + "=" * 60)
    print("PULLING EIA DATA")
    print("=" * 60)
    
    base_url = "https://api.eia.gov/v2"
    
    # These are the key supply/demand indicators
    series_list = [
        ("petroleum/stoc/wstk", "Weekly US Crude Stocks"),
        ("petroleum/pri/spt", "Spot Prices"),
        ("petroleum/move/wkly", "Weekly Movements"),
    ]
    
    all_data = {}
    
    for series_path, description in series_list:
        print(f"Downloading {description}...")
        try:
            url = f"{base_url}/{series_path}/data?api_key={api_key}&frequency=weekly&data[0]=value"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                if 'response' in data and 'data' in data['response']:
                    df = pd.DataFrame(data['response']['data'])
                    all_data[description] = df
                    print(f"  ✓ Got {len(df)} records")
            else:
                print(f"  ✗ Error: {response.status_code}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    return all_data


def add_statistical_features(df, price_col='WTI_Crude_Close'):
    """
    NEW: Adds statistical features while avoiding lookahead bias.
    
    Key improvements:
    1. Rolling statistics use min_periods to avoid NaN padding issues
    2. Features are shifted by 1 to prevent using future information
    3. Adds statistical moments (skewness, kurtosis) for return distributions
    
    This prevents the common ML pitfall of accidentally using tomorrow's
    data to predict today's price.
    """
    print("Adding statistical features with lookahead protection...")
    result = df.copy()
    
    if price_col not in result.columns:
        print(f"Warning: {price_col} not found - skipping statistical features")
        return result
    
    price = result[price_col]
    returns = price.pct_change()
    
    # NEW: Rolling statistics with min_periods to avoid expanding windows
    # This ensures we only use past data available at each point in time
    for window in [5, 20, 60]:
        # Rolling standard deviation (volatility)
        result[f'Volatility_{window}d'] = returns.rolling(
            window=window, min_periods=int(window/2)
        ).std() * np.sqrt(252)
        
        # NEW: Rolling skewness and kurtosis
        # Measures asymmetry and tail risk of return distribution
        result[f'Skewness_{window}d'] = returns.rolling(
            window=window, min_periods=int(window/2)
        ).apply(lambda x: stats.skew(x) if len(x[x.notna()]) >= 10 else np.nan)
        
        result[f'Kurtosis_{window}d'] = returns.rolling(
            window=window, min_periods=int(window/2)
        ).apply(lambda x: stats.kurtosis(x) if len(x[x.notna()]) >= 10 else np.nan)
    
    # NEW: Shift all rolling features by 1 day
    # Critical! This prevents using today's data to predict today's price
    rolling_cols = [col for col in result.columns if any(x in col for x in ['Volatility_', 'Skewness_', 'Kurtosis_'])]
    for col in rolling_cols:
        result[f'{col}_lag1'] = result[col].shift(1)
        result.drop(columns=[col], inplace=True)
    
    # NEW: Price percentiles (how current price compares to recent history)
    result['Price_Pctl_20d'] = price.rolling(20, min_periods=10).apply(
        lambda x: stats.percentileofscore(x, x[-1]) if len(x[x.notna()]) >= 10 else np.nan
    )
    result['Price_Pctl_20d'] = result['Price_Pctl_20d'].shift(1)
    
    return result


def validate_features(df, target_col='Target_Return_1d'):
    """
    NEW: Quick validation check to ensure features are statistically useful.
    
    Performs three checks:
    1. Missing values check
    2. Correlation with target (abs > 0.05 considered potentially useful)
    3. Constant value check (features that don't change are useless)
    
    This helps catch data issues early.
    """
    print("\n" + "=" * 60)
    print("VALIDATING FEATURES")
    print("=" * 60)
    
    # Check 1: Missing values
    missing = df.isnull().sum()
    if missing.sum() > 0:
        print(f"Warning: {missing.sum()} missing values found")
        print(f"Columns with most NaNs:")
        print(missing[missing > 0].head())
    
    # Check 2: Correlation with target (if target exists)
    if target_col in df.columns:
        # Calculate correlations, handling NaN values
        numeric_df = df.select_dtypes(include=[np.number])
        correlations = numeric_df.corr()[target_col].abs().sort_values(ascending=False)
        print(f"\nTop 10 features correlated with {target_col}:")
        print(correlations.head(10))
        
        # Flag low-correlation features
        low_corr = correlations[correlations < 0.05].index.tolist()
        if low_corr:
            print(f"\n{len(low_corr)} features have |correlation| < 0.05 with target")
            print("Consider removing or transforming these")
    
    # Check 3: Constant features
    constant_features = []
    for col in df.columns:
        if df[col].nunique() == 1:
            constant_features.append(col)
    
    if constant_features:
        print(f"\nWarning: {len(constant_features)} constant features found")
        print(f"These will be useless for ML: {constant_features[:5]}")
    
    return df


# FEATURE ENGINEERING
# This is where we create the indicators for our ML models


def engineer_features(df, price_col='WTI_Crude_Close'):
    """
    Creates technical indicators and derived features from raw price data.
    
    I've included the standard stuff that quant traders use:
    - Moving averages and crossovers
    - RSI, MACD, Bollinger Bands
    - Volatility measures
    - Momentum indicators
    
    Feel free to add more features if you have ideas!
    """
    print("\n" + "=" * 60)
    print("ENGINEERING FEATURES")
    print("=" * 60)
    
    if price_col not in df.columns:
        print(f"Error: {price_col} not found in dataset. Available columns:")
        print(df.columns.tolist()[:10])
        return df
    
    result = df.copy()
    price = result[price_col]
    
    # Returns at different horizons
    result['Return_1d'] = price.pct_change(1)
    result['Return_5d'] = price.pct_change(5)
    result['Return_20d'] = price.pct_change(20)
    
    # Moving averages - classic trend indicators
    result['MA_5'] = price.rolling(5).mean()
    result['MA_20'] = price.rolling(20).mean()
    result['MA_50'] = price.rolling(50).mean()
    result['MA_200'] = price.rolling(200).mean()
    
    # MA crossover signals - when short MA crosses above long MA, bullish signal
    result['MA_5_20_Cross'] = (result['MA_5'] > result['MA_20']).astype(int)
    result['MA_50_200_Cross'] = (result['MA_50'] > result['MA_200']).astype(int)  # "Golden cross"
    
    # Volatility - annualized standard deviation of returns
    result['Volatility_20d'] = result['Return_1d'].rolling(20).std() * np.sqrt(252)
    result['Volatility_60d'] = result['Return_1d'].rolling(60).std() * np.sqrt(252)
    
    # RSI - momentum oscillator, >70 overbought, <30 oversold
    delta = price.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    result['RSI_14'] = 100 - (100 / (1 + rs))
    
    # Bollinger Bands - price relative to its recent range
    result['BB_Middle'] = price.rolling(20).mean()
    bb_std = price.rolling(20).std()
    result['BB_Upper'] = result['BB_Middle'] + 2 * bb_std
    result['BB_Lower'] = result['BB_Middle'] - 2 * bb_std
    result['BB_Position'] = (price - result['BB_Lower']) / (result['BB_Upper'] - result['BB_Lower'])
    
    # MACD - trend following momentum indicator
    exp1 = price.ewm(span=12, adjust=False).mean()
    exp2 = price.ewm(span=26, adjust=False).mean()
    result['MACD'] = exp1 - exp2
    result['MACD_Signal'] = result['MACD'].ewm(span=9, adjust=False).mean()
    result['MACD_Histogram'] = result['MACD'] - result['MACD_Signal']
    
    # Momentum - simple price change over N days
    result['Momentum_10'] = price - price.shift(10)
    result['Momentum_30'] = price - price.shift(30)
    
    # Brent-WTI Spread - important arbitrage indicator
    if 'Brent_Crude_Close' in result.columns:
        result['Brent_WTI_Spread'] = result['Brent_Crude_Close'] - result[price_col]
    
    # VIX moving average - smoothed fear gauge
    if 'VIX_Close' in result.columns:
        result['VIX_MA_20'] = result['VIX_Close'].rolling(20).mean()
    
    # Seasonality features - oil has seasonal patterns
    result['DayOfWeek'] = result.index.dayofweek
    result['Month'] = result.index.month
    result['Quarter'] = result.index.quarter
    
    print(f"Created {len(result.columns) - len(df.columns)} new basic features")
    
    # NEW: Add statistical features with lookahead protection
    result = add_statistical_features(result, price_col)
    
    # NEW: Create lagged returns for ML models (predict next day's return)
    result['Target_Return_1d'] = price.pct_change(1).shift(-1)  # What we're trying to predict
    
    # NEW: Drop rows with NaN values (from rolling windows)
    # This is cleaner for ML and prevents data leakage
    original_len = len(result)
    result = result.dropna()
    print(f"Dropped {original_len - len(result)} rows with NaN values")
    print(f"Final dataset shape: {result.shape}")
    
    return result



# MAIN EXECUTION


def main():
    """
    Main function - runs all data collection and saves to CSV files.
    """
    print("\n" + "=" * 60)
    print("OIL PRICE DATA COLLECTION")
    print("=" * 60)
    print(f"Running at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Step 1: Yahoo Finance (always works)
    print("\n[STEP 1/4] Collecting Yahoo Finance data...")
    yf_data = collect_yfinance_data(start_date="2015-01-01")
    
    if yf_data is not None:
        yf_data.to_csv("data_yfinance_raw.csv")
        print(f"\n✓ Saved: data_yfinance_raw.csv")
        
        # Step 2: Add technical features
        print("\n[STEP 2/4] Engineering features...")
        featured_data = engineer_features(yf_data)
        
        # NEW: Validate the features we created
        featured_data = validate_features(featured_data)
        
        featured_data.to_csv("data_yfinance_featured.csv")
        print(f"✓ Saved: data_yfinance_featured.csv")
    
    # Step 3: Try FRED and EIA (need API keys)
    print("\n[STEP 3/4] Checking additional data sources...")
    fred_data = collect_fred_data()
    eia_data = collect_eia_data()
    
    # Save FRED data if we got it
    if fred_data is not None:
        fred_data.to_csv("data_fred.csv")
        print(f"✓ Saved: data_fred.csv")
    
    # Step 4: Summary
    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)
    
    if yf_data is not None:
        print(f"\nYahoo Finance data collected:")
        print(f"  - Date range: {yf_data.index.min().date()} to {yf_data.index.max().date()}")
        print(f"  - Columns: {len(yf_data.columns)}")
        print(f"  - Rows: {len(yf_data)}")
        
        print("\nKey columns for modeling:")
        print("  - WTI_Crude_Close → our main target")
        print("  - Brent_Crude_Close → alternative target")
        print("  - USD_Index_Close → key driver (inverse correlation)")
        print("  - VIX_Close → volatility/fear indicator")
        print("  - SP500_Close → economic health proxy")
        
        # NEW: Display information about the improved features
        print("\nNEW IMPROVEMENTS ADDED:")
        print("  - Statistical features (skewness, kurtosis, percentiles)")
        print("  - Lookahead bias protection (all features lagged by 1 day)")
        print("  - Target variable: 'Target_Return_1d' (next day's return)")
        print("  - Feature validation (correlation checks, NaN handling)")
    
    if fred_data is None or eia_data is None:
        print("\n" + "-" * 60)
        print("HEADS UP: Some data sources need API keys")
        print("-" * 60)
        print("Check the messages above and add keys to your .env file")
        print("to get the full dataset for our factor analysis.")
    
    print("\n" + "=" * 60)
    print("TERMUX USERS NOTE:")
    print("=" * 60)
    print("If running on Android Termux, you may need to:")
    print("1. Install additional packages: pkg install python numpy scipy")
    print("2. Some dependencies may need manual installation")
    print("3. Check README.md for full Termux setup instructions")
    
    return yf_data


if __name__ == "__main__":
    data = main()
