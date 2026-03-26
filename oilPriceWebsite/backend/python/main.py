"""
Oil Price Risk Factor Analysis — Main Pipeline
================================================
Citibank Oil Price Risk Factor Challenge

  python main.py                  → full pipeline
  python main.py --skip-data      → skip data collection
  python main.py --skip-news      → skip news scraping
  python main.py --report-only    → just regenerate report

Author: Arturo
"""

import os, sys, argparse
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns

from config import PATHS

ANALYSIS_DIR = PATHS.analysis_dir
PLOT_DIR = PATHS.analysis_plots


def run_data_collector():
    print("\n" + "=" * 70 + "\n  STEP 1: COLLECTING PRICE DATA\n" + "=" * 70)
    try:
        from oil_data_collector import main as collect_data
        collect_data(); return True
    except Exception as e:
        print(f"  ✗ ERROR: {e}"); return False


def run_news_scraper():
    print("\n" + "=" * 70 + "\n  STEP 2: SCRAPING & ANALYZING NEWS\n" + "=" * 70)
    try:
        from news_scraper import main_normal
        main_normal(); return True
    except Exception as e:
        print(f"  ✗ ERROR: {e}"); return False


def load_price_data():
    if not PATHS.price_featured.exists():
        print(f"  ✗ {PATHS.price_featured} not found"); return None
    df = pd.read_csv(str(PATHS.price_featured), index_col=0, parse_dates=True)
    print(f"  ✓ Price data: {df.shape[0]} rows, {df.index.min().date()} → {df.index.max().date()}")
    return df


def load_news_data():
    scored, daily = None, None
    if PATHS.news_scored.exists():
        scored = pd.read_csv(str(PATHS.news_scored)); scored["date"] = pd.to_datetime(scored["date"])
        print(f"  ✓ News headlines: {len(scored)} scored")
    if PATHS.news_daily.exists():
        daily = pd.read_csv(str(PATHS.news_daily), index_col=0, parse_dates=True)
        print(f"  ✓ Daily sentiment: {len(daily)} days")
    return scored, daily


def analyze_price_data(df):
    insights = {}
    if "WTI_Crude_Close" not in df.columns: return insights
    price = df["WTI_Crude_Close"]
    insights["current_price"] = round(price.iloc[-1], 2)
    insights["price_date"] = df.index[-1].strftime("%Y-%m-%d")
    insights["return_1d"] = round(price.pct_change(1).iloc[-1] * 100, 2)
    insights["return_5d"] = round(price.pct_change(5).iloc[-1] * 100, 2)
    insights["return_20d"] = round(price.pct_change(20).iloc[-1] * 100, 2)
    if "MA_50" in df.columns and "MA_200" in df.columns:
        insights["ma50"] = round(df["MA_50"].iloc[-1], 2); insights["ma200"] = round(df["MA_200"].iloc[-1], 2)
        insights["trend"] = "UPTREND (Golden Cross)" if df["MA_50"].iloc[-1] > df["MA_200"].iloc[-1] else "DOWNTREND (Death Cross)"
    if "Volatility_20d" in df.columns:
        vol = df["Volatility_20d"].iloc[-1]; insights["volatility_20d"] = round(vol * 100, 1)
        insights["vol_assessment"] = "VERY HIGH" if vol>0.40 else ("HIGH" if vol>0.30 else ("MODERATE" if vol>0.20 else "LOW"))
    if "RSI_14" in df.columns:
        rsi = df["RSI_14"].iloc[-1]; insights["rsi"] = round(rsi, 1)
        insights["rsi_assessment"] = "OVERBOUGHT" if rsi>70 else ("OVERSOLD" if rsi<30 else "NEUTRAL")
    if "Brent_WTI_Spread" in df.columns: insights["brent_wti_spread"] = round(df["Brent_WTI_Spread"].iloc[-1], 2)
    if "Target_Return_1d" in df.columns:
        corr = df.select_dtypes(include=[np.number]).corr()["Target_Return_1d"].drop("Target_Return_1d").abs().sort_values(ascending=False)
        insights["top_correlated_features"] = list(corr.head(5).items())
    return insights


def analyze_news_data(scored_df, daily_df):
    insights = {}
    if scored_df is not None:
        insights["total_headlines"] = len(scored_df)
        insights["sources_count"] = scored_df["source"].nunique()
        lc = scored_df["consensus_label"].value_counts()
        insights["bullish_count"] = lc.get("bullish", 0)
        insights["bearish_count"] = lc.get("bearish", 0)
        insights["neutral_count"] = lc.get("neutral", 0)
        insights["overall_score"] = round(scored_df["consensus_score"].mean(), 3)
        insights["top_bullish"] = scored_df.nlargest(3, "consensus_score")[["headline","consensus_score","source"]].to_dict("records")
        insights["top_bearish"] = scored_df.nsmallest(3, "consensus_score")[["headline","consensus_score","source"]].to_dict("records")
    if daily_df is not None and len(daily_df) >= 5:
        recent = daily_df.tail(5)["mean_sentiment"]; trend = recent.iloc[-1] - recent.iloc[0]
        insights["sentiment_trend"] = "IMPROVING" if trend>0.1 else ("DETERIORATING" if trend<-0.1 else "STABLE")
    return insights


def generate_final_report(pi, ni):
    L = []; w = L.append
    w("╔"+"═"*68+"╗"); w("║"+"  OIL PRICE RISK FACTOR ANALYSIS — FINAL REPORT".center(68)+"║")
    w("║"+f"  {datetime.now():%Y-%m-%d %H:%M:%S}".center(68)+"║"); w("╚"+"═"*68+"╝")

    w(f"\n{'━'*70}\n  1. EXECUTIVE SUMMARY\n{'━'*70}")
    w("\n  This report combines price analysis (60+ indicators) with news sentiment")
    w("  (hundreds of headlines) to answer: what drives oil prices right now?\n")

    if "current_price" in pi:
        w(f"{'━'*70}\n  2. CURRENT STATE\n{'━'*70}")
        w(f"\n  WTI: ${pi['current_price']} ({pi['price_date']})")
        w(f"  Day: {pi.get('return_1d',0):+.2f}%  Week: {pi.get('return_5d',0):+.2f}%  Month: {pi.get('return_20d',0):+.2f}%")

    w(f"\n{'━'*70}\n  3. TECHNICAL ANALYSIS\n{'━'*70}")
    if "trend" in pi: w(f"\n  Trend: {pi['trend']}")
    if "rsi" in pi: w(f"  RSI: {pi['rsi']} ({pi['rsi_assessment']})")
    if "volatility_20d" in pi: w(f"  Volatility: {pi['volatility_20d']}% ({pi['vol_assessment']})")

    if "total_headlines" in ni:
        w(f"\n{'━'*70}\n  4. NEWS SENTIMENT\n{'━'*70}")
        t=ni["total_headlines"]; b=ni["bullish_count"]; be=ni["bearish_count"]
        w(f"\n  {t} headlines: 🟢{b} bullish, 🔴{be} bearish")
        w(f"  Overall score: {ni['overall_score']:+.3f}")

    # Conclusion
    signals = []; scores = []
    if "return_20d" in pi:
        r=pi["return_20d"]; signals.append(f"Monthly return: {r:+.1f}%"); scores.append(1 if r>5 else (-1 if r<-5 else 0))
    if "trend" in pi:
        signals.append(f"Trend: {pi['trend']}"); scores.append(1 if "UP" in pi["trend"] else -1)
    if "overall_score" in ni:
        a=ni["overall_score"]; signals.append(f"News: {a:+.3f}"); scores.append(1 if a>0.1 else (-1 if a<-0.1 else 0))

    w(f"\n{'━'*70}\n  5. CONCLUSION\n{'━'*70}")
    for s in signals: w(f"  • {s}")
    if scores:
        avg = np.mean(scores)
        if avg>0.3: w("\n  ➤ OUTLOOK: BULLISH")
        elif avg<-0.3: w("\n  ➤ OUTLOOK: BEARISH")
        elif avg>0: w("\n  ➤ OUTLOOK: SLIGHTLY BULLISH")
        elif avg<0: w("\n  ➤ OUTLOOK: SLIGHTLY BEARISH")
        else: w("\n  ➤ OUTLOOK: NEUTRAL / MIXED")

    w(f"\n{'━'*70}\n  Generated: {datetime.now():%Y-%m-%d %H:%M:%S}\n{'━'*70}")
    return "\n".join(L)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-data", action="store_true")
    parser.add_argument("--skip-news", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    PLOT_DIR.mkdir(parents=True, exist_ok=True)

    print("╔"+"═"*68+"╗"); print("║"+"  OIL PRICE RISK FACTOR ANALYSIS".center(68)+"║"); print("╚"+"═"*68+"╝")

    if not args.skip_data and not args.report_only: run_data_collector()
    else: print("\n  ⏭  Skipping data collection")

    if not args.skip_news and not args.report_only: run_news_scraper()
    else: print("\n  ⏭  Skipping news scraping")

    print("\n" + "=" * 70 + "\n  LOADING RESULTS\n" + "=" * 70)
    price_df = load_price_data(); news_scored, news_daily = load_news_data()

    pi = analyze_price_data(price_df) if price_df is not None else {}
    ni = analyze_news_data(news_scored, news_daily)

    report = generate_final_report(pi, ni)
    with open(str(PATHS.analysis_report), "w") as f: f.write(report)
    print(f"\n  ✓ {PATHS.analysis_report}")

    summary = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **{k:v for k,v in pi.items() if not isinstance(v,(list,dict))},
        **{f"news_{k}":v for k,v in ni.items() if not isinstance(v,(list,dict))}}
    pd.DataFrame([summary]).to_csv(str(PATHS.analysis_summary), index=False)

    print("\n" + report)
    print(f"\n{'═'*70}\n  DONE — {ANALYSIS_DIR}/\n{'═'*70}")

if __name__ == "__main__":
    main()