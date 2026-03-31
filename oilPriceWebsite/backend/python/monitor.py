"""
Oil Price Risk Monitor — Unified Live System
==============================================
Citibank Oil Price Risk Factor Challenge

ONE COMMAND, ALWAYS ON:
  python monitor.py

"""

import os, sys, json, time, signal, argparse, logging, re
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque

import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup

from dotenv import load_dotenv
load_dotenv()

from config import PATHS

# ── Config ───────────────────────────────────────────────────
NEWS_POLL_MINUTES = 10
DATA_REFRESH_HOUR = 17
SENTIMENT_WINDOW = 120

HEADERS_HTTP = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
RSS_QUERIES = ["crude oil price", "OPEC oil production", "oil supply demand", "WTI Brent crude", "oil sanctions geopolitical"]

# ── Logging ──────────────────────────────────────────────────
logger = logging.getLogger("monitor")
logger.setLevel(logging.INFO)
logger.handlers.clear()
fmt = logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S")
sh = logging.StreamHandler(sys.stdout); sh.setFormatter(fmt); logger.addHandler(sh)
fh = logging.FileHandler(str(PATHS.monitor_log), mode="a"); fh.setFormatter(fmt); logger.addHandler(fh)
log = logger

_running = True
def _stop(sig, frame):
    global _running; _running = False; log.info("\nStopping...")
signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PRICE DATA LAYER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PriceState:
    def __init__(self):
        self.df = None; self.last_refresh = None; self.signals = {}

    def needs_refresh(self):
        if self.df is None or self.last_refresh is None: return True
        now = datetime.now()
        if now.hour >= DATA_REFRESH_HOUR and self.last_refresh.date() < now.date(): return True
        return False

    def refresh(self):
        csv_path = PATHS.price_featured
        if csv_path.exists():
            self.df = pd.read_csv(str(csv_path), index_col=0, parse_dates=True)
            self.last_refresh = datetime.now()
            log.info(f"  Price data loaded: {len(self.df)} rows, latest: {self.df.index[-1].date()}")
            days_old = (datetime.now() - self.df.index[-1].to_pydatetime().replace(tzinfo=None)).days
            if days_old > 3:
                log.info(f"  Data is {days_old} days old, refreshing...")
                self._run_collector()
        else:
            log.info("  No price data found, running collector...")
            self._run_collector()
        self._extract_signals()

    def _run_collector(self):
        try:
            from oil_data_collector import main as collect
            collect()
            if PATHS.price_featured.exists():
                self.df = pd.read_csv(str(PATHS.price_featured), index_col=0, parse_dates=True)
                self.last_refresh = datetime.now()
                log.info(f"  ✓ Price data refreshed: {len(self.df)} rows")
        except Exception as e:
            log.warning(f"  ✗ Collector failed: {e}")

    def _extract_signals(self):
        if self.df is None or len(self.df) == 0: return
        df = self.df; s = {}
        if "WTI_Crude_Close" in df.columns:
            price = df["WTI_Crude_Close"]
            s["price"] = round(price.iloc[-1], 2)
            s["price_date"] = df.index[-1].strftime("%Y-%m-%d")
            s["return_1d"] = round(price.pct_change(1).iloc[-1] * 100, 2)
            s["return_5d"] = round(price.pct_change(5).iloc[-1] * 100, 2)
            s["return_20d"] = round(price.pct_change(20).iloc[-1] * 100, 2)
        if "MA_50" in df.columns and "MA_200" in df.columns:
            s["trend"] = "UP" if df["MA_50"].iloc[-1] > df["MA_200"].iloc[-1] else "DOWN"
        if "RSI_14" in df.columns: s["rsi"] = round(df["RSI_14"].iloc[-1], 1)
        if "Volatility_20d" in df.columns: s["volatility"] = round(df["Volatility_20d"].iloc[-1] * 100, 1)
        if "MACD_Histogram" in df.columns: s["macd_hist"] = round(df["MACD_Histogram"].iloc[-1], 3)
        if "Brent_WTI_Spread" in df.columns: s["brent_wti_spread"] = round(df["Brent_WTI_Spread"].iloc[-1], 2)
        if "VIX_Close" in df.columns: s["vix"] = round(df["VIX_Close"].iloc[-1], 1)
        self.signals = s

    def fetch_live_price(self):
        """Fetch current WTI price from Yahoo Finance (lightweight, no download)."""
        try:
            import yfinance as yf
            ticker = yf.Ticker("CL=F")
            info = ticker.fast_info
            live_price = round(info.get("lastPrice", 0) or info.get("last_price", 0), 2)
            if live_price > 0:
                self.signals["live_price"] = live_price
                self.signals["live_time"] = datetime.now().strftime("%H:%M:%S")
                log.info(f"  Live WTI: ${live_price}")
            else:
                # Fallback: try history
                hist = yf.download("CL=F", period="1d", progress=False)
                if isinstance(hist.columns, pd.MultiIndex):
                    hist.columns = hist.columns.get_level_values(0)
                if len(hist) > 0:
                    live_price = round(hist["Close"].iloc[-1], 2)
                    self.signals["live_price"] = live_price
                    self.signals["live_time"] = datetime.now().strftime("%H:%M:%S")
                    log.info(f"  Live WTI (fallback): ${live_price}")
        except Exception as e:
            log.warning(f"  Live price fetch failed: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NEWS SENTIMENT LAYER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_POS = {'surge','surges','surging','rally','rallies','rallying','jump','jumps','jumping','soar','soars','soaring','climb','climbs','climbing','gain','gains','gaining','rise','rises','rising','spike','spikes','spiking','rebound','rebounds','recover','recovers','recovery','bullish','boom','booming','uptick','upswing','high','higher','highest','record','shortage','shortfall','deficit','tight','tighten','cut','cuts','cutting','reduce','reduction','drawdown','draw','sanctions','embargo','disruption','disruptions','outage','growth','expanding','strong','robust','optimism','optimistic','confidence'}
_NEG = {'fall','falls','falling','drop','drops','dropping','decline','declines','declining','plunge','plunges','crash','crashes','crashing','tumble','tumbles','slide','slides','sliding','sink','sinks','sinking','slump','slumps','plummet','plummets','bearish','downturn','selloff','sell-off','low','lower','lowest','weak','weaker','surplus','glut','oversupply','overproduction','build','buildup','build-up','flood','flooding','excess','slowdown','recession','contraction','weakness','slowing','fear','fears','concern','concerns','worry','worries','uncertainty','volatile','volatility','risk','risks','war','conflict','tension','tensions','crisis','pressure','pressuring'}
_NEGATE = {'not','no','never','neither','nor','barely','hardly'}
_BOOST = {'very':1.5,'extremely':2.0,'sharply':1.8,'significantly':1.7,'massively':2.0,'deeply':1.6,'strongly':1.5,'heavily':1.5,'slightly':0.5,'somewhat':0.6,'marginally':0.5}
_SCORE = {}
for w in _POS: _SCORE[w] = 0.4
for w in _NEG: _SCORE[w] = -0.4
for w in ['surge','surging','soar','soaring','spike','spiking','boom','booming']: _SCORE[w] = 0.7
for w in ['crash','crashing','plunge','plunges','plummet','collapse']: _SCORE[w] = -0.7
for w in ['rally','rallying','rebound','recovery','bullish','record']: _SCORE[w] = 0.5
for w in ['recession','crisis','selloff','sell-off','bearish','downturn']: _SCORE[w] = -0.6

def _clean(w): return re.sub(r"[^\w-]", "", w.lower())
def _label(score):
    if score > 0.05: return "bullish"
    if score < -0.05: return "bearish"
    return "neutral"

def score_headline(text):
    words = text.lower().split(); total = 0.0; n = 0
    for i, w in enumerate(words):
        c = _clean(w)
        if c not in _SCORE: continue
        s = _SCORE[c]
        for j in range(max(0,i-2),i):
            p = _clean(words[j])
            if p in _NEGATE: s *= -0.8; break
            if p in _BOOST: s *= _BOOST[p]; break
        total += s; n += 1
    return round(float(np.tanh(total * 0.8)), 3) if n else 0.0

def fetch_rss(query, max_items=20):
    try:
        r = requests.get(f"https://news.google.com/rss/search?q={query.replace(' ','+')}&hl=en-US&gl=US&ceid=US:en", headers=HEADERS_HTTP, timeout=12)
        if r.status_code != 200: return []
        soup = BeautifulSoup(r.text, "xml"); results = []
        for item in soup.find_all("item")[:max_items]:
            title = item.find("title"); src = item.find("source"); pub = item.find("pubDate")
            if not title: continue
            dt_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if pub:
                try: dt_str = datetime.strptime(pub.text.strip(), "%a, %d %b %Y %H:%M:%S %Z").strftime("%Y-%m-%d %H:%M:%S")
                except: pass
            results.append({"headline": title.text.strip(), "datetime": dt_str, "source": src.text.strip() if src else "google_news"})
        return results
    except: return []


class NewsState:
    def __init__(self, window_minutes=120):
        self.window = window_minutes; self.headlines = deque(); self.seen = set(); self.total_seen = 0; self.total_new = 0
    def poll(self):
        raw = []
        for q in RSS_QUERIES: raw.extend(fetch_rss(q, max_items=20)); time.sleep(0.6)
        new = 0
        for h in raw:
            fp = h["headline"][:60].lower().strip()
            if fp in self.seen or len(h["headline"]) < 15: continue
            self.seen.add(fp); self.total_seen += 1; self.total_new += 1
            score = score_headline(h["headline"]); label = _label(score)
            try: dt = datetime.strptime(h["datetime"], "%Y-%m-%d %H:%M:%S")
            except: dt = datetime.now()
            self.headlines.append((dt, score, label, h["headline"], h.get("source",""))); new += 1
        cutoff = datetime.now() - timedelta(minutes=self.window)
        while self.headlines and self.headlines[0][0] < cutoff: self.headlines.popleft()
        return new
    def get_metrics(self):
        if not self.headlines: return {"active": False, "count": 0, "all_headlines": []}
        scores = [h[1] for h in self.headlines]; labels = [h[2] for h in self.headlines]
        n = len(scores); mean = float(np.mean(scores))
        # Build full headline list (newest first)
        all_h = [{"datetime":h[0].strftime("%Y-%m-%d %H:%M:%S"),"score":h[1],"label":h[2],
                  "headline":h[3],"source":h[4]} for h in reversed(list(self.headlines))]
        return {"active":True,"mean":round(mean,4),"std":round(float(np.std(scores)),4),
            "bullish_pct":round(labels.count("bullish")/n,3),"bearish_pct":round(labels.count("bearish")/n,3),
            "neutral_pct":round(labels.count("neutral")/n,3),"count":n,
            "latest":[{"score":h[1],"label":h[2],"headline":h[3][:70],"source":h[4]} for h in list(self.headlines)[-3:]],
            "all_headlines": all_h}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NEWS IMPACT WEIGHT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def measure_news_weight(price_df):
    if not PATHS.news_daily.exists() or price_df is None:
        return 0.10, "estimated (no historical overlap yet)"
    try:
        sentiment = pd.read_csv(str(PATHS.news_daily), index_col=0, parse_dates=True)
        if "WTI_Crude_Close" not in price_df.columns: return 0.10, "estimated"
        returns = price_df["WTI_Crude_Close"].pct_change()
        sentiment_shifted = sentiment["mean_sentiment"].shift(1)
        combined = pd.DataFrame({"return": returns, "sentiment": sentiment_shifted}).dropna()
        if len(combined) < 10: return 0.10, f"estimated ({len(combined)} days)"
        corr = combined["return"].corr(combined["sentiment"])
        weight = min(abs(corr), 0.5); weight = max(weight, 0.05)
        return round(weight, 3), f"measured (corr={corr:.3f}, {len(combined)} days)"
    except Exception as e:
        return 0.10, f"estimated (error: {e})"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RISK ASSESSMENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def compute_risk(price_signals, news_metrics, news_weight):
    components = []
    if "trend" in price_signals:
        components.append(("Trend (MA50 vs MA200)", 1.0 if price_signals["trend"]=="UP" else -1.0, 0.30))
    if "rsi" in price_signals:
        rsi = price_signals["rsi"]
        s = -0.7 if rsi>70 else (0.3 if rsi>60 else (0.7 if rsi<30 else (-0.3 if rsi<40 else 0.0)))
        components.append(("Momentum (RSI)", s, 0.15))
    if "macd_hist" in price_signals:
        components.append(("MACD Direction", float(np.clip(price_signals["macd_hist"]*10,-1,1)), 0.15))
    if "return_5d" in price_signals:
        components.append(("Recent Returns (5d)", float(np.clip(price_signals["return_5d"]/5,-1,1)), 0.15))
    if "vix" in price_signals:
        vix = price_signals["vix"]
        s = -0.8 if vix>30 else (-0.4 if vix>25 else (0.3 if vix<15 else 0.0))
        components.append(("Market Fear (VIX)", s, 0.10))
    remaining = max(0.05, 1.0 - sum(c[2] for c in components))
    if news_metrics.get("active"):
        components.append(("News Sentiment", float(np.clip(news_metrics["mean"]*3,-1,1)), min(news_weight, remaining)))
    if not components: return {"score":0,"label":"NO DATA","components":[]}
    tw = sum(c[2] for c in components); ws = sum(c[1]*c[2] for c in components)
    score = ws/tw if tw>0 else 0
    if score>0.4: label="LOW RISK — bullish signals dominate"
    elif score>0.15: label="LOW-MODERATE RISK — slight upward bias"
    elif score>-0.15: label="MODERATE RISK — mixed signals"
    elif score>-0.4: label="ELEVATED RISK — bearish signals building"
    else: label="HIGH RISK — strong bearish signals"
    return {"score":round(score,4),"label":label,"components":[(n,round(s,3),round(w,3)) for n,s,w in components]}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DASHBOARD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def print_dashboard(ps, nm, risk, nw, nws, new_h, cycle, interval):
    bar_pos = int((risk["score"]+1)/2*40); bar_pos = max(0,min(40,bar_pos))
    risk_bar = "#"*bar_pos + "|" + "."*(40-bar_pos)
    print(f"\033[2J\033[H", end="")
    print(f"{'='*72}\n  OIL PRICE RISK MONITOR\n  {datetime.now():%Y-%m-%d %H:%M:%S}  -  Cycle {cycle}  -  Updates every {interval} min\n{'='*72}")
    icon = "[OK]" if risk["score"]>0.15 else ("[!!]" if risk["score"]>-0.15 else "[!!]")
    print(f"\n  +{'-'*68}+\n  |  {icon} {risk['label']:<63s}|\n  |  Risk Score: {risk['score']:>+.4f}{'':>49s}|\n  |  High Risk <- {risk_bar} -> Low Risk   |\n  +{'-'*68}+")
    if "price" in ps:
        r1=ps.get('return_1d',0); r5=ps.get('return_5d',0); r20=ps.get('return_20d',0)
        c1="(+)" if r1>0 else "(-)"; c5="(+)" if r5>0 else "(-)"; c20="(+)" if r20>0 else "(-)"
        print(f"\n  PRICE: ${ps['price']}  ({ps.get('price_date','?')})\n    {c1} Day:{r1:>+.2f}%  {c5} Week:{r5:>+.2f}%  {c20} Month:{r20:>+.2f}%")
    if risk["components"]:
        print(f"\n  SIGNALS:")
        for name,score,weight in risk["components"]:
            bl=int(abs(score)*15); d=f"[+] {'#'*bl}{'.'*(15-bl)}" if score>0.05 else (f"[-] {'#'*bl}{'.'*(15-bl)}" if score<-0.05 else f"[=] {'.'*15}")
            print(f"    {name:<25s} {d}  {score:>+.3f}  ({weight:.0%})")
    if nm.get("active"):
        print(f"\n  NEWS: score={nm['mean']:+.4f} | bull:{nm['bullish_pct']:.0%} neut:{nm['neutral_pct']:.0%} bear:{nm['bearish_pct']:.0%} | {nm['count']} headlines | weight:{nw:.0%}")
    print(f"\n{'-'*72}\n  Output: {PATHS.monitor_dir}  |  Ctrl+C to stop\n{'-'*72}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PERSISTENCE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def save_state(ps, nm, risk, nw, nws):
    state = {"timestamp":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"risk_score":risk["score"],"risk_label":risk["label"],
        "price":ps.get("price"),"return_1d":ps.get("return_1d"),"return_5d":ps.get("return_5d"),"trend":ps.get("trend"),
        "rsi":ps.get("rsi"),"vix":ps.get("vix"),"volatility":ps.get("volatility"),
        "live_price":ps.get("live_price"),"live_time":ps.get("live_time"),
        "news_score":nm.get("mean") if nm.get("active") else None,"news_bullish_pct":nm.get("bullish_pct") if nm.get("active") else None,
        "news_weight":nw,"news_weight_source":nws,"headlines_in_window":nm.get("count",0),"components":risk["components"]}
    with open(str(PATHS.monitor_state),"w") as f: json.dump(state,f,indent=2)

    # Write live sentiment for the news endpoint
    if nm.get("active"):
        live = {"status":"active","timestamp":state["timestamp"],"mean_sentiment":nm["mean"],
            "bullish_pct":nm["bullish_pct"],"bearish_pct":nm["bearish_pct"],"neutral_pct":nm["neutral_pct"],
            "signal":"BULLISH" if nm["mean"]>0.05 else ("BEARISH" if nm["mean"]<-0.05 else "NEUTRAL"),
            "headlines_in_window":nm["count"],"latest_3":nm.get("latest",[])}
        with open(str(PATHS.live_sentiment),"w") as f: json.dump(live,f,indent=2)

    # Write ALL headlines to a separate file for the frontend
    all_headlines = nm.get("all_headlines", [])
    if all_headlines:
        headlines_path = PATHS.news_live_dir / "all_headlines.json"
        with open(str(headlines_path), "w") as f:
            json.dump({"timestamp": state["timestamp"], "count": len(all_headlines), "headlines": all_headlines}, f, indent=2)

    flat = {k:v for k,v in state.items() if not isinstance(v,list)}
    exists = PATHS.monitor_history.exists()
    pd.DataFrame([flat]).to_csv(str(PATHS.monitor_history), mode="a", header=not exists, index=False)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    global SENTIMENT_WINDOW, NEWS_POLL_MINUTES
    parser = argparse.ArgumentParser(description="Oil Price Risk Monitor")
    parser.add_argument("--interval", type=int, default=NEWS_POLL_MINUTES)
    parser.add_argument("--window", type=int, default=SENTIMENT_WINDOW)
    args = parser.parse_args()
    interval = args.interval; SENTIMENT_WINDOW = args.window; NEWS_POLL_MINUTES = interval

    log.info("="*50); log.info("  OIL PRICE RISK MONITOR"); log.info(f"  {datetime.now():%Y-%m-%d %H:%M:%S}")
    log.info(f"  Poll: {interval} min | Window: {args.window} min"); log.info(f"  Data: {PATHS.data_root}"); log.info("="*50)

    price = PriceState(); news = NewsState(window_minutes=args.window)
    log.info("\nLoading price data..."); price.refresh()
    log.info("Measuring news weight..."); nw, nws = measure_news_weight(price.df)
    log.info(f"  News weight: {nw:.1%} ({nws})")

    cycle = 0
    while _running:
        cycle += 1
        if price.needs_refresh(): price.refresh(); nw, nws = measure_news_weight(price.df)
        price.fetch_live_price()  # Get real-time WTI price
        new_h = news.poll(); nm = news.get_metrics()
        risk = compute_risk(price.signals, nm, nw)
        print_dashboard(price.signals, nm, risk, nw, nws, new_h, cycle, interval)
        save_state(price.signals, nm, risk, nw, nws)
        for _ in range(interval*60):
            if not _running: break
            time.sleep(1)
    log.info(f"\nSTOPPED | {news.total_seen} headlines | {cycle} cycles")

if __name__ == "__main__":
    main()