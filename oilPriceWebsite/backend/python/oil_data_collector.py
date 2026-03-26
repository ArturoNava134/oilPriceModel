"""
Oil Price Risk Factor Analysis - Data Collection Script
--------------------------------------------------------
Competition: Citibank Oil Price Risk Factor Challenge

It pulls from three main sources - Yahoo Finance works out of the box,
and FRED/EIA need free API keys (takes 2 mins to set up).

HOW TO RUN:
1. Copy env.example to .env and add your API keys
2. pip install -r requirements.txt
3. python oil_data_collector.py

Author: Arturo
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from scipy import stats

from dotenv import load_dotenv
load_dotenv()

# ── Use centralized paths ────────────────────────────────────
from config import PATHS

FRED_API_KEY = os.getenv("FRED_API_KEY")
EIA_API_KEY = os.getenv("EIA_API_KEY")


def collect_yfinance_data(start_date="2015-01-01", end_date=None):
    import yfinance as yf

    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    print("=" * 60)
    print("PULLING YAHOO FINANCE DATA")
    print("=" * 60)

    tickers = {
        "CL=F": "WTI_Crude",
        "BZ=F": "Brent_Crude",
        "NG=F": "Natural_Gas",
        "HO=F": "Heating_Oil",
        "RB=F": "Gasoline",
        "DX-Y.NYB": "USD_Index",
        "^GSPC": "SP500",
        "^VIX": "VIX",
        "XLE": "Energy_Sector_ETF",
        "USO": "Oil_ETF",
        "GC=F": "Gold",
        "SI=F": "Silver",
    }

    all_data = {}

    for ticker, name in tickers.items():
        print(f"Downloading {name} ({ticker})...")
        try:
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if len(data) > 0:
                # This line MUST be here
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
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


def collect_fred_data(api_key=None, start_date="2015-01-01"):
    api_key = api_key or FRED_API_KEY

    if api_key is None:
        print("\n" + "=" * 60)
        print("FRED DATA - NEED API KEY")
        print("=" * 60)
        print("1. Get free key: https://fred.stlouisfed.org/docs/api/api_key.html")
        print("2. Add to .env: FRED_API_KEY=your_key_here")
        return None

    from fredapi import Fred
    fred = Fred(api_key=api_key)

    print("\n" + "=" * 60)
    print("PULLING FRED DATA")
    print("=" * 60)

    series = {
        'DCOILWTICO': 'WTI_Spot_FRED',
        'DCOILBRENTEU': 'Brent_Spot_FRED',
        'GDP': 'US_GDP',
        'GDPC1': 'Real_GDP',
        'INDPRO': 'Industrial_Production',
        'CPIAUCSL': 'CPI',
        'UNRATE': 'Unemployment_Rate',
        'FEDFUNDS': 'Fed_Funds_Rate',
        'DGS10': 'Treasury_10Y',
        'T10Y2Y': 'Yield_Curve',
        'DTWEXBGS': 'Trade_Weighted_USD',
        'M2SL': 'M2_Money_Supply',
        'UMCSENT': 'Consumer_Sentiment',
        'BSCICP03USM665S': 'Business_Confidence',
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


def collect_eia_data(api_key=None):
    api_key = api_key or EIA_API_KEY

    if api_key is None:
        print("\n" + "=" * 60)
        print("EIA DATA - NEED API KEY")
        print("=" * 60)
        print("1. Get free key: https://www.eia.gov/opendata/register.php")
        print("2. Add to .env: EIA_API_KEY=your_key_here")
        return None

    import requests

    print("\n" + "=" * 60)
    print("PULLING EIA DATA")
    print("=" * 60)

    base_url = "https://api.eia.gov/v2"
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
    Adds statistical features while avoiding lookahead bias.
    Uses only vectorized operations — no slow rolling apply.
    """
    print("Adding statistical features with lookahead protection...")
    result = df.copy()
    
    if price_col not in result.columns:
        print(f"Warning: {price_col} not found - skipping statistical features")
        return result
    
    price = result[price_col]
    returns = price.pct_change()
    
    # Volatility at multiple windows (already fast — vectorized)
    for window in [5, 20, 60]:
        vol = returns.rolling(window=window, min_periods=max(3, window//2)).std() * np.sqrt(252)
        result[f'Volatility_{window}d_lag1'] = vol.shift(1)
    
    # Price percentile: where current price sits vs last 20 days
    rolling_min = price.rolling(20, min_periods=10).min()
    rolling_max = price.rolling(20, min_periods=10).max()
    pctl = (price - rolling_min) / (rolling_max - rolling_min)
    result['Price_Pctl_20d'] = pctl.shift(1)
    
    # Return z-score: how unusual is today's return vs recent history
    rolling_mean = returns.rolling(20, min_periods=10).mean()
    rolling_std = returns.rolling(20, min_periods=10).std()
    result['Return_ZScore_20d'] = ((returns - rolling_mean) / rolling_std).shift(1)
    
    print(f"  Added {3 + 3} statistical features (all lagged by 1 day)")
    return result


def validate_features(df, target_col='Target_Return_1d'):
    print("\n" + "=" * 60)
    print("VALIDATING FEATURES")
    print("=" * 60)

    missing = df.isnull().sum()
    if missing.sum() > 0:
        print(f"Warning: {missing.sum()} missing values found")
        print(f"Columns with most NaNs:")
        print(missing[missing > 0].head())

    if target_col in df.columns:
        numeric_df = df.select_dtypes(include=[np.number])
        correlations = numeric_df.corr()[target_col].abs().sort_values(ascending=False)
        print(f"\nTop 10 features correlated with {target_col}:")
        print(correlations.head(10))

        low_corr = correlations[correlations < 0.05].index.tolist()
        if low_corr:
            print(f"\n{len(low_corr)} features have |correlation| < 0.05 with target")

    constant_features = [col for col in df.columns if df[col].nunique() == 1]
    if constant_features:
        print(f"\nWarning: {len(constant_features)} constant features found")

    return df


def engineer_features(df, price_col='WTI_Crude_Close'):
    print("\n" + "=" * 60)
    print("ENGINEERING FEATURES")
    print("=" * 60)

    if price_col not in df.columns:
        print(f"Error: {price_col} not found in dataset. Available columns:")
        print(df.columns.tolist()[:10])
        return df

    result = df.copy()
    price = result[price_col]

    result['Return_1d'] = price.pct_change(1)
    result['Return_5d'] = price.pct_change(5)
    result['Return_20d'] = price.pct_change(20)

    result['MA_5'] = price.rolling(5).mean()
    result['MA_20'] = price.rolling(20).mean()
    result['MA_50'] = price.rolling(50).mean()
    result['MA_200'] = price.rolling(200).mean()

    result['MA_5_20_Cross'] = (result['MA_5'] > result['MA_20']).astype(int)
    result['MA_50_200_Cross'] = (result['MA_50'] > result['MA_200']).astype(int)

    result['Volatility_20d'] = result['Return_1d'].rolling(20).std() * np.sqrt(252)
    result['Volatility_60d'] = result['Return_1d'].rolling(60).std() * np.sqrt(252)

    delta = price.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    result['RSI_14'] = 100 - (100 / (1 + rs))

    result['BB_Middle'] = price.rolling(20).mean()
    bb_std = price.rolling(20).std()
    result['BB_Upper'] = result['BB_Middle'] + 2 * bb_std
    result['BB_Lower'] = result['BB_Middle'] - 2 * bb_std
    result['BB_Position'] = (price - result['BB_Lower']) / (result['BB_Upper'] - result['BB_Lower'])

    exp1 = price.ewm(span=12, adjust=False).mean()
    exp2 = price.ewm(span=26, adjust=False).mean()
    result['MACD'] = exp1 - exp2
    result['MACD_Signal'] = result['MACD'].ewm(span=9, adjust=False).mean()
    result['MACD_Histogram'] = result['MACD'] - result['MACD_Signal']

    result['Momentum_10'] = price - price.shift(10)
    result['Momentum_30'] = price - price.shift(30)

    if 'Brent_Crude_Close' in result.columns:
        result['Brent_WTI_Spread'] = result['Brent_Crude_Close'] - result[price_col]

    if 'VIX_Close' in result.columns:
        result['VIX_MA_20'] = result['VIX_Close'].rolling(20).mean()

    result['DayOfWeek'] = result.index.dayofweek
    result['Month'] = result.index.month
    result['Quarter'] = result.index.quarter

    print(f"Created {len(result.columns) - len(df.columns)} new basic features")

    result = add_statistical_features(result, price_col)

    result['Target_Return_1d'] = price.pct_change(1).shift(-1)

    original_len = len(result)
    result = result.dropna()
    print(f"Dropped {original_len - len(result)} rows with NaN values")
    print(f"Final dataset shape: {result.shape}")

    return result


def main():
    print("\n" + "=" * 60)
    print("OIL PRICE DATA COLLECTION")
    print("=" * 60)
    print(f"Running at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output dir: {PATHS.price_dir}")
    print("=" * 60)

    # Step 1: Yahoo Finance
    print("\n[STEP 1/4] Collecting Yahoo Finance data...")
    yf_data = collect_yfinance_data(start_date="2015-01-01")

    if yf_data is not None:
        yf_data.to_csv(str(PATHS.price_raw))
        print(f"\n✓ Saved: {PATHS.price_raw}")

        # Step 2: Add technical features
        print("\n[STEP 2/4] Engineering features...")
        featured_data = engineer_features(yf_data)
        featured_data = validate_features(featured_data)

        featured_data.to_csv(str(PATHS.price_featured))
        print(f"✓ Saved: {PATHS.price_featured}")

    # Step 3: FRED and EIA
    print("\n[STEP 3/4] Checking additional data sources...")
    fred_data = collect_fred_data()
    eia_data = collect_eia_data()

    if fred_data is not None:
        fred_data.to_csv(str(PATHS.fred))
        print(f"✓ Saved: {PATHS.fred}")

    # Step 4: Summary
    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)

    if yf_data is not None:
        print(f"\nYahoo Finance data:")
        print(f"  Date range: {yf_data.index.min().date()} to {yf_data.index.max().date()}")
        print(f"  Columns: {len(yf_data.columns)}, Rows: {len(yf_data)}")

    if fred_data is None or eia_data is None:
        print("\nHEADS UP: Some data sources need API keys. Check .env")

    return yf_data


if __name__ == "__main__":
    data = main()