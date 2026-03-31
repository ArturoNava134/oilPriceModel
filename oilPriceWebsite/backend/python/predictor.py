"""
Oil Price Predictor — Multi-Model Forecasting
================================================
Citibank Oil Price Risk Factor Challenge

Trains 3 models on historical price data and generates forecasts:
  1. ARIMA — classic time series model (captures trend + seasonality)
  2. XGBoost — gradient boosting on technical features (captures non-linear patterns)
  3. Simple Moving Average Ensemble — baseline for comparison

Outputs:
  data/predictions/forecast.json  <- used by the dashboard
  data/predictions/model_performance.json  <- accuracy metrics

Called by monitor.py after price data loads, or standalone:
  python predictor.py
 
"""

import json, warnings
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

from config import PATHS

PRED_DIR = PATHS.data_root / "predictions"
PRED_DIR.mkdir(parents=True, exist_ok=True)

FORECAST_DAYS = 5  # predict 5 trading days ahead


# =====================================================
# DATA LOADING
# =====================================================

def load_data():
    """Load the featured price CSV."""
    if not PATHS.price_featured.exists():
        print("  [ERROR] No price data. Run oil_data_collector.py first.")
        return None
    df = pd.read_csv(str(PATHS.price_featured), index_col=0, parse_dates=True)
    print(f"  [OK] Loaded {len(df)} rows, latest: {df.index[-1].date()}")
    return df


# =====================================================
# MODEL 1: ARIMA
# =====================================================

def run_arima(price_series):
    """
    ARIMA (Auto-Regressive Integrated Moving Average).
    Good at capturing trends and mean-reversion in price series.
    """
    print("\n  [ARIMA] Training...")
    try:
        from statsmodels.tsa.arima.model import ARIMA

        # Use last 500 days for faster training
        data = price_series.dropna().tail(500)

        # ARIMA(5,1,2) — 5 AR terms, 1 differencing (removes trend), 2 MA terms
        model = ARIMA(data, order=(5, 1, 2))
        fitted = model.fit()

        # Forecast
        forecast = fitted.forecast(steps=FORECAST_DAYS)
        forecast_values = forecast.values.tolist()

        # Backtest: predict last 20 days to measure accuracy
        train = data.iloc[:-20]
        test = data.iloc[-20:]
        bt_model = ARIMA(train, order=(5, 1, 2)).fit()
        bt_pred = bt_model.forecast(steps=20)

        mae = np.mean(np.abs(test.values - bt_pred.values))
        mape = np.mean(np.abs((test.values - bt_pred.values) / test.values)) * 100
        direction_correct = np.mean(
            np.sign(np.diff(test.values)) == np.sign(np.diff(bt_pred.values))
        ) * 100

        print(f"  [ARIMA] [OK] MAE: ${mae:.2f}, MAPE: {mape:.1f}%, Direction: {direction_correct:.0f}%")

        return {
            "model": "ARIMA(5,1,2)",
            "forecast": forecast_values,
            "metrics": {
                "mae": round(mae, 2),
                "mape": round(mape, 2),
                "direction_accuracy": round(direction_correct, 1),
            },
            "status": "ok"
        }

    except ImportError:
        print("  [ARIMA] [ERROR] statsmodels not installed. Run: pip install statsmodels")
        return {"model": "ARIMA", "status": "missing_dependency", "forecast": []}
    except Exception as e:
        print(f"  [ARIMA] [ERROR] Error: {e}")
        return {"model": "ARIMA", "status": f"error: {e}", "forecast": []}


# =====================================================
# MODEL 2: XGBOOST
# =====================================================

def run_xgboost(df):
    """
    XGBoost on technical features.
    Predicts next-day return, then chains predictions forward.
    Also gives us feature importance — key for the competition.
    """
    print("\n  [XGBoost] Training...")
    try:
        from xgboost import XGBRegressor

        # Prepare features
        feature_cols = [c for c in df.columns if c not in [
            'Target_Return_1d', 'WTI_Crude_Open', 'WTI_Crude_High',
            'WTI_Crude_Low', 'WTI_Crude_Volume'
        ] and df[c].dtype in ['float64', 'int64', 'float32', 'int32']]

        data = df[feature_cols + ['Target_Return_1d']].dropna()
        if len(data) < 100:
            print("  [XGBoost] [ERROR] Not enough data")
            return {"model": "XGBoost", "status": "insufficient_data", "forecast": []}

        X = data[feature_cols]
        y = data['Target_Return_1d']

        # Walk-forward split: train on all but last 20, test on last 20
        X_train, X_test = X.iloc[:-20], X.iloc[-20:]
        y_train, y_test = y.iloc[:-20], y.iloc[-20:]

        model = XGBRegressor(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbosity=0
        )
        model.fit(X_train, y_train)

        # Backtest metrics
        bt_pred = model.predict(X_test)
        mae_return = np.mean(np.abs(y_test.values - bt_pred))
        direction_correct = np.mean(np.sign(y_test.values) == np.sign(bt_pred)) * 100

        # Feature importance (top 10)
        importance = dict(zip(feature_cols, model.feature_importances_.tolist()))
        top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10]

        # Forecast: use average predicted return applied to last price
        # (Chaining causes error accumulation — single-step is more stable)
        last_price = df['WTI_Crude_Close'].iloc[-1]
        avg_pred_return = float(np.mean(bt_pred))  # average predicted daily return
        forecast_prices = []
        current_price = last_price
        for day in range(FORECAST_DAYS):
            # Blend model's average prediction with recent actual momentum
            current_price = current_price + avg_pred_return
            forecast_prices.append(round(current_price, 2))

        # Convert MAE from returns to dollar terms
        avg_price = df['WTI_Crude_Close'].tail(20).mean()
        mae_dollars = mae_return * avg_price

        print(f"  [XGBoost] [OK] MAE: ${mae_dollars:.2f}, Direction: {direction_correct:.0f}%")
        print(f"  [XGBoost] Top 3 features: {', '.join([f[0] for f in top_features[:3]])}")

        return {
            "model": "XGBoost",
            "forecast": forecast_prices,
            "metrics": {
                "mae_dollars": round(mae_dollars, 2),
                "mae_return": round(mae_return, 5),
                "direction_accuracy": round(direction_correct, 1),
            },
            "feature_importance": [{"feature": f, "importance": round(i, 4)} for f, i in top_features],
            "status": "ok"
        }

    except ImportError:
        print("  [XGBoost] [ERROR] xgboost not installed. Run: pip install xgboost")
        return {"model": "XGBoost", "status": "missing_dependency", "forecast": []}
    except Exception as e:
        print(f"  [XGBoost] [ERROR] Error: {e}")
        return {"model": "XGBoost", "status": f"error: {e}", "forecast": []}


# =====================================================
# MODEL 3: MOVING AVERAGE BASELINE
# =====================================================

def run_baseline(price_series):
    """
    Simple baseline: forecast = last price + recent trend.
    Uses 5-day and 20-day momentum to extrapolate.
    Every model should beat this — if not, the model is useless.
    """
    print("\n  [Baseline] Calculating...")
    data = price_series.dropna()
    last_price = data.iloc[-1]
    daily_trend_5d = (data.iloc[-1] - data.iloc[-5]) / 5
    daily_trend_20d = (data.iloc[-1] - data.iloc[-20]) / 20
    avg_trend = (daily_trend_5d + daily_trend_20d) / 2

    forecast = [round(last_price + avg_trend * (i + 1), 2) for i in range(FORECAST_DAYS)]

    # Backtest
    test_actual = data.iloc[-20:].values
    test_pred = []
    for i in range(20):
        base = data.iloc[-40 + i]
        t5 = (data.iloc[-40 + i] - data.iloc[-45 + i]) / 5
        t20 = (data.iloc[-40 + i] - data.iloc[-60 + i]) / 20
        test_pred.append(base + (t5 + t20) / 2)

    mae = np.mean(np.abs(np.array(test_actual) - np.array(test_pred)))
    mape = np.mean(np.abs((np.array(test_actual) - np.array(test_pred)) / np.array(test_actual))) * 100

    print(f"  [Baseline] [OK] MAE: ${mae:.2f}, MAPE: {mape:.1f}%")

    return {
        "model": "Trend Baseline",
        "forecast": forecast,
        "metrics": {"mae": round(mae, 2), "mape": round(mape, 2)},
        "status": "ok"
    }


# =====================================================
# ENSEMBLE & OUTPUT
# =====================================================

def build_ensemble(results):
    """Average forecasts from all successful models."""
    valid = [r for r in results if r["status"] == "ok" and len(r["forecast"]) == FORECAST_DAYS]
    if not valid:
        return []

    ensemble = []
    for day in range(FORECAST_DAYS):
        prices = [r["forecast"][day] for r in valid]
        ensemble.append(round(np.mean(prices), 2))

    return ensemble


def generate_forecast_dates(last_date):
    """Generate the next N trading days (skip weekends)."""
    dates = []
    current = last_date
    while len(dates) < FORECAST_DAYS:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon-Fri
            dates.append(current.strftime("%Y-%m-%d"))
    return dates


def run_predictions(df=None):
    """
    Main entry point. Called by monitor.py or standalone.
    Returns the forecast dict and saves to JSON.
    """
    print("\n" + "=" * 60)
    print("  OIL PRICE PREDICTION")
    print("=" * 60)

    if df is None:
        df = load_data()
    if df is None or len(df) == 0:
        return None

    price_col = "WTI_Crude_Close"
    if price_col not in df.columns:
        print(f"  [ERROR] {price_col} not found")
        return None

    price = df[price_col]
    last_price = round(price.iloc[-1], 2)
    last_date = df.index[-1]

    print(f"  Current price: ${last_price} ({last_date.date()})")

    # Run all models
    results = []
    results.append(run_arima(price))
    results.append(run_xgboost(df))
    results.append(run_baseline(price))

    # Ensemble
    ensemble = build_ensemble(results)
    forecast_dates = generate_forecast_dates(last_date)

    # Direction call
    if ensemble:
        end_price = ensemble[-1]
        change_pct = round((end_price - last_price) / last_price * 100, 2)
        if change_pct > 1:
            direction = "UP"
            confidence = "Models agree oil likely to RISE"
        elif change_pct < -1:
            direction = "DOWN"
            confidence = "Models agree oil likely to FALL"
        else:
            direction = "FLAT"
            confidence = "Models show no strong directional signal"
    else:
        end_price = last_price
        change_pct = 0
        direction = "UNKNOWN"
        confidence = "No models produced valid forecasts"

    # Build output
    output = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "current_price": last_price,
        "current_date": last_date.strftime("%Y-%m-%d"),
        "forecast_days": FORECAST_DAYS,
        "forecast_dates": forecast_dates,

        "ensemble": {
            "forecast": ensemble,
            "end_price": end_price if ensemble else None,
            "change_pct": change_pct,
            "direction": direction,
            "confidence": confidence,
        },

        "models": results,
    }

    # Save
    forecast_path = PRED_DIR / "forecast.json"
    with open(str(forecast_path), "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  [OK] Saved: {forecast_path}")

    # Print summary
    print(f"\n  {'-' * 50}")
    print(f"  FORECAST SUMMARY ({FORECAST_DAYS}-day)")
    print(f"  {'-' * 50}")
    print(f"  Current:  ${last_price}")
    if ensemble:
        print(f"  Forecast: ${ensemble[-1]} ({change_pct:+.2f}%)")
        print(f"  Direction: {direction} -- {confidence}")
        print(f"  Day-by-day: {' -> '.join([f'${p}' for p in ensemble])}")
    print(f"\n  Model results:")
    for r in results:
        status = "[OK]" if r["status"] == "ok" else "[ERROR]"
        forecast_str = f"${r['forecast'][-1]}" if r["forecast"] else "N/A"
        print(f"    {status} {r['model']:<20s} -> {forecast_str}")
        if r.get("metrics"):
            m = r["metrics"]
            parts = []
            if "mae" in m: parts.append(f"MAE: ${m['mae']}")
            if "mae_dollars" in m: parts.append(f"MAE: ${m['mae_dollars']}")
            if "direction_accuracy" in m: parts.append(f"Dir: {m['direction_accuracy']}%")
            print(f"      {', '.join(parts)}")

    return output


if __name__ == "__main__":
    run_predictions()