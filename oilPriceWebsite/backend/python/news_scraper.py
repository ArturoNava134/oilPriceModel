"""
Oil News Sentiment Scraper — Standalone Module
================================================
Citibank Oil Price Risk Factor Challenge

TWO MODES:
  python news_scraper.py             → normal: scrape once, produce report
  python news_scraper.py --live      → real-time: poll every 15 min continuously
  python news_scraper.py --live 10   → real-time: poll every 10 min

This module is INDEPENDENT — it does not read, write, or
modify any other project files. All outputs go to:
    Normal mode → data/news/
    Live mode   → data/news_live/

"""

import os, re, sys, json, time, signal, hashlib, logging, argparse
from datetime import datetime, timedelta
from collections import Counter, deque
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from dotenv import load_dotenv; load_dotenv()

# ── Config (CHANGED: use centralized paths) ──────────────────
from config import PATHS

OUT_DIR   = PATHS.news_dir
PLOT_DIR  = PATHS.news_plots
CACHE_DIR = PATHS.news_cache
LIVE_DIR  = PATHS.news_live_dir

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
HEADERS = {"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36","Accept":"text/html,application/xhtml+xml","Accept-Language":"en-US,en;q=0.5"}
REQUEST_DELAY = 1.5
RSS_QUERIES = ["crude oil price","OPEC oil production","oil supply demand","WTI Brent crude","oil sanctions geopolitical"]

def setup_logging(log_path=None):
    p = log_path or PATHS.news_log  # CHANGED: was OUT_DIR / "scraper.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("news_scraper"); logger.setLevel(logging.INFO); logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")
    sh = logging.StreamHandler(sys.stdout); sh.setFormatter(fmt); logger.addHandler(sh)
    fh = logging.FileHandler(p, mode="a"); fh.setFormatter(fmt); logger.addHandler(fh)
    return logger
log = setup_logging()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SCRAPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import requests; from bs4 import BeautifulSoup

def _safe_get(url, timeout=15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        return (r, None) if r.status_code == 200 else (None, f"HTTP {r.status_code}")
    except requests.exceptions.Timeout: return None, "timeout"
    except requests.exceptions.ConnectionError: return None, "connection refused"
    except Exception as e: return None, str(e)

def scrape_google_news_rss(query="crude oil price", max_items=40):
    log.info(f"  Google News RSS  →  query: '{query}'")
    headlines = []
    resp, err = _safe_get(f"https://news.google.com/rss/search?q={query.replace(' ','+')}&hl=en-US&gl=US&ceid=US:en")
    if err: log.warning(f"    ✗ {err}"); return headlines
    soup = BeautifulSoup(resp.text, "xml")
    for item in soup.find_all("item")[:max_items]:
        title = item.find("title"); pub = item.find("pubDate"); src = item.find("source"); link = item.find("link")
        if not title: continue
        date_str, dt_str = datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if pub:
            try: dt = datetime.strptime(pub.text.strip(), "%a, %d %b %Y %H:%M:%S %Z"); date_str = dt.strftime("%Y-%m-%d"); dt_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError: pass
        headlines.append({"headline": title.text.strip(), "date": date_str, "datetime": dt_str, "source": src.text.strip() if src else "google_news", "url": link.text.strip() if link else ""})
    log.info(f"    ✓ {len(headlines)} headlines"); return headlines

def scrape_newsapi(query="crude oil", days_back=14, page_size=100):
    if not NEWS_API_KEY: log.info("  NewsAPI           →  skipped (no key)"); return []
    log.info(f"  NewsAPI           →  query: '{query}', {days_back}d")
    headlines = []
    try:
        resp = requests.get("https://newsapi.org/v2/everything", params={"q":query,"from":(datetime.now()-timedelta(days=days_back)).strftime("%Y-%m-%d"),"sortBy":"relevancy","language":"en","pageSize":page_size,"apiKey":NEWS_API_KEY}, timeout=15)
        data = resp.json()
        if data.get("status") != "ok": log.warning(f"    ✗ {data.get('message','')}"); return headlines
        for a in data.get("articles",[]):
            headlines.append({"headline":a.get("title",""),"description":a.get("description",""),"date":a.get("publishedAt","")[:10],"datetime":a.get("publishedAt","")[:19].replace("T"," "),"source":a.get("source",{}).get("name","newsapi"),"url":a.get("url","")})
        log.info(f"    ✓ {len(headlines)} articles")
    except Exception as e: log.warning(f"    ✗ {e}")
    return headlines

def scrape_reuters():
    log.info("  Reuters Energy    →  scraping"); headlines = []
    resp, err = _safe_get("https://www.reuters.com/business/energy/")
    if err: log.warning(f"    ✗ {err}"); return headlines
    soup = BeautifulSoup(resp.text, "html.parser"); seen = set()
    for tag in ["h3","a"]:
        for el in soup.find_all(tag):
            t = el.get_text(strip=True)
            if 20 < len(t) < 300 and t not in seen: seen.add(t); headlines.append({"headline":t,"date":datetime.now().strftime("%Y-%m-%d"),"datetime":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"source":"reuters","url":""})
    log.info(f"    ✓ {len(headlines)} headlines"); return headlines

def scrape_oilprice(max_pages=3):
    log.info(f"  OilPrice.com      →  {max_pages} pages"); headlines = []; seen = set()
    for page in range(1, max_pages+1):
        url = "https://oilprice.com/Latest-Energy-News/World-News/" if page == 1 else f"https://oilprice.com/Latest-Energy-News/World-News/{page}"
        resp, err = _safe_get(url)
        if err: log.warning(f"    ✗ page {page}: {err}"); continue
        for a in BeautifulSoup(resp.text,"html.parser").find_all("a",href=True):
            t, h = a.get_text(strip=True), a["href"]
            if 25 < len(t) < 300 and "/Article/" in h and t not in seen: seen.add(t); headlines.append({"headline":t,"date":datetime.now().strftime("%Y-%m-%d"),"datetime":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"source":"oilprice","url":h if h.startswith("http") else f"https://oilprice.com{h}"})
        if page < max_pages: time.sleep(REQUEST_DELAY)
    log.info(f"    ✓ {len(headlines)} headlines"); return headlines

def scrape_all():
    log.info("─"*55); log.info("SCRAPING NEWS SOURCES"); log.info("─"*55)
    CACHE_DIR.mkdir(parents=True, exist_ok=True); cache_file = CACHE_DIR / f"headlines_{datetime.now():%Y%m%d}.json"
    if cache_file.exists():
        log.info(f"Cache hit → {cache_file.name}")
        with open(cache_file) as f: cached = json.load(f)
        log.info(f"Loaded {len(cached)} cached headlines"); return cached
    raw = []
    for q in ["crude oil price","OPEC oil production","oil supply demand","WTI Brent crude","oil geopolitical risk"]: raw.extend(scrape_google_news_rss(query=q, max_items=30)); time.sleep(REQUEST_DELAY)
    for q in ["crude oil","OPEC","oil prices"]: raw.extend(scrape_newsapi(query=q, days_back=14)); time.sleep(REQUEST_DELAY)
    raw.extend(scrape_reuters()); time.sleep(REQUEST_DELAY); raw.extend(scrape_oilprice(max_pages=3))
    seen = set(); unique = []
    for h in raw:
        fp = h["headline"][:60].lower().strip()
        if fp not in seen and len(h["headline"]) > 15: seen.add(fp); unique.append(h)
    log.info(f"\nTotal unique headlines: {len(unique)}")
    with open(cache_file, "w") as f: json.dump(unique, f, indent=2)
    log.info(f"Cached → {cache_file.name}"); return unique

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SENTIMENT CLASSIFIERS
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
def _clean(w): return re.sub(r"[^\w-]","",w.lower())

def classify_dictionary(text):
    words = text.lower().split(); pos, neg = 0, 0
    for i, w in enumerate(words):
        c = _clean(w); negated = i > 0 and _clean(words[i-1]) in _NEGATE
        if c in _POS:
            if negated: neg += 1
            else: pos += 1
        elif c in _NEG:
            if negated: pos += 1
            else: neg += 1
    total = pos + neg; return round((pos-neg)/total, 3) if total else 0.0

def classify_rulebased(text):
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
    return round(float(np.tanh(total*0.8)), 3) if n else 0.0

def _build_tfidf_model():
    pos_t = ["oil prices {w} amid supply concerns","crude {w} on OPEC production cuts","brent crude {w} after supply disruption","energy stocks {w} on strong demand","oil market shows {w} momentum"]
    neg_t = ["oil prices {w} on demand weakness","crude {w} amid economic slowdown","oil market hit by {w} in demand","energy sector {w} as oil weakens","brent crude {w} on oversupply fears"]
    texts, labels = [], []
    for w in list(_POS)[:30]:
        for t in pos_t: texts.append(t.format(w=w)); labels.append(1)
    for w in list(_NEG)[:30]:
        for t in neg_t: texts.append(t.format(w=w)); labels.append(-1)
    neutral = ["oil prices remain unchanged in quiet trading","crude holds near previous close ahead of data release","oil market awaits weekly inventory report from EIA","brent and WTI trade in narrow range today","energy markets mixed on lack of clear catalysts"] * 20
    texts.extend(neutral); labels.extend([0]*len(neutral))
    vec = TfidfVectorizer(max_features=500, ngram_range=(1,2)); X = vec.fit_transform(texts)
    clf = LogisticRegression(max_iter=500, C=1.0, random_state=42); clf.fit(X, labels)
    return vec, clf

def classify_tfidf(text, vec, clf):
    X = vec.transform([text]); proba = clf.predict_proba(X)[0]; order = clf.classes_.tolist()
    p_pos = proba[order.index(1)] if 1 in order else 0; p_neg = proba[order.index(-1)] if -1 in order else 0
    return round(float(p_pos - p_neg), 3)

def classify_vader(text):
    try:
        from nltk.sentiment.vader import SentimentIntensityAnalyzer; import nltk
        try: nltk.data.find("sentiment/vader_lexicon.zip")
        except LookupError: nltk.download("vader_lexicon", quiet=True)
        if not hasattr(classify_vader, "_sia"): classify_vader._sia = SentimentIntensityAnalyzer()
        return round(classify_vader._sia.polarity_scores(text)["compound"], 3)
    except ImportError: return None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLASSIFICATION PIPELINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _label(score):
    if score > 0.05: return "bullish"
    if score < -0.05: return "bearish"
    return "neutral"

def classify_all(headlines):
    log.info("─"*55); log.info("CLASSIFYING HEADLINES"); log.info("─"*55)
    vec, clf = _build_tfidf_model(); log.info("  TF-IDF model trained")
    has_vader = classify_vader("test") is not None
    log.info(f"  VADER {'available ✓' if has_vader else 'unavailable'}")
    rows = []
    for i, h in enumerate(headlines):
        text = h["headline"]; d = classify_dictionary(text); r = classify_rulebased(text); m = classify_tfidf(text, vec, clf)
        v = classify_vader(text) if has_vader else None
        scores = [d, r, m] + ([v] if v is not None else [])
        avg = round(np.mean(scores), 3)
        labels = [_label(d), _label(r), _label(m)] + ([_label(v)] if v is not None else [])
        cl, cn = Counter(labels).most_common(1)[0]
        row = {"date":h["date"],"source":h["source"],"headline":text,"url":h.get("url",""),"dict_score":d,"rulebased_score":r,"tfidf_score":m,"consensus_score":avg,"consensus_label":cl,"agreement":f"{cn}/{len(labels)}"}
        if v is not None: row["vader_score"] = v
        rows.append(row)
        if (i+1) % 50 == 0: log.info(f"  {i+1}/{len(headlines)} classified")
    df = pd.DataFrame(rows); df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date","source"], ascending=[False,True]).reset_index(drop=True)
    lc = df["consensus_label"].value_counts()
    log.info(f"\n  Results ({len(df)} headlines):")
    for l in ["bullish","neutral","bearish"]: n = lc.get(l,0); log.info(f"    {l:>8s}  {n:>4d}  ({n/len(df)*100:5.1f}%)")
    log.info(f"    avg score: {df['consensus_score'].mean():+.3f}"); return df

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DAILY AGGREGATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_daily_index(scored_df):
    log.info("─"*55); log.info("BUILDING DAILY SENTIMENT INDEX"); log.info("─"*55)
    df = scored_df.copy()
    daily = df.groupby("date").agg(mean_sentiment=("consensus_score","mean"),median_sentiment=("consensus_score","median"),sentiment_std=("consensus_score","std"),max_sentiment=("consensus_score","max"),min_sentiment=("consensus_score","min"),headline_count=("consensus_score","count"),bullish_pct=("consensus_label",lambda x:(x=="bullish").mean()),bearish_pct=("consensus_label",lambda x:(x=="bearish").mean()),neutral_pct=("consensus_label",lambda x:(x=="neutral").mean())).round(4)
    daily["sentiment_std"] = daily["sentiment_std"].fillna(0)
    daily["sentiment_range"] = daily["max_sentiment"] - daily["min_sentiment"]
    daily["sentiment_delta"] = daily["mean_sentiment"].diff()
    daily["sentiment_ma3"] = daily["mean_sentiment"].rolling(3, min_periods=1).mean().round(4)
    daily.index.name = "date"
    log.info(f"  {len(daily)} trading days")
    log.info(f"  {daily.index.min().date()} → {daily.index.max().date()}")
    return daily

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VISUALIZATIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PAL = {"bullish":"#27ae60","neutral":"#7f8c8d","bearish":"#e74c3c"}

def _save(fig, name):
    fig.savefig(PLOT_DIR/name, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    log.info(f"    ✓ {name}")

def generate_plots(scored_df, daily_df):
    log.info("─"*55); log.info("GENERATING PLOTS"); log.info("─"*55)
    PLOT_DIR.mkdir(parents=True, exist_ok=True); sns.set_style("whitegrid")
    methods = ["dict_score","rulebased_score","tfidf_score"]; names = ["Dictionary","Rule-Based","TF-IDF ML"]
    if "vader_score" in scored_df.columns: methods.append("vader_score"); names.append("VADER")

    # 1. Distributions
    fig, axes = plt.subplots(1,len(methods),figsize=(5*len(methods),5),sharey=True)
    if len(methods)==1: axes=[axes]
    for ax,col,name in zip(axes,methods,names):
        data = scored_df[col].dropna()
        ax.hist(data[data>0.05],bins=15,color=PAL["bullish"],alpha=.75,label="Bullish")
        ax.hist(data[(data>=-0.05)&(data<=0.05)],bins=5,color=PAL["neutral"],alpha=.75,label="Neutral")
        ax.hist(data[data<-0.05],bins=15,color=PAL["bearish"],alpha=.75,label="Bearish")
        ax.axvline(0,color="black",lw=.8); ax.set_title(name,fontweight="bold"); ax.set_xlabel("Score")
        if ax==axes[0]: ax.set_ylabel("Headlines"); ax.legend(fontsize=8)
    fig.suptitle("Score Distributions by Classification Method",fontweight="bold",fontsize=14,y=1.02)
    _save(fig,"01_score_distributions.png")

    # 2. Heatmap
    sample = pd.concat([scored_df.nlargest(15,"consensus_score"),scored_df.nsmallest(15,"consensus_score")]).drop_duplicates("headline")
    matrix = sample.set_index(sample["headline"].str[:50].to_numpy())[methods+["consensus_score"]]
    matrix.columns = names+["Consensus"]
    fig, ax = plt.subplots(figsize=(10,max(6,len(matrix)*0.35)))
    sns.heatmap(matrix,annot=True,fmt=".2f",cmap="RdYlGn",center=0,vmin=-1,vmax=1,linewidths=.4,ax=ax,cbar_kws={"label":"Sentiment Score"})
    ax.set_title("Top Bullish & Bearish Headlines — All Methods",fontweight="bold",fontsize=12)
    ax.tick_params(axis="y",labelsize=7)
    _save(fig,"02_headline_heatmap.png")

    # 3. Daily timeline
    fig, axes = plt.subplots(3,1,figsize=(14,10),gridspec_kw={"height_ratios":[3,2,1]})
    ax = axes[0]
    colors = ["#27ae60" if v>0 else "#e74c3c" for v in daily_df["mean_sentiment"]]
    ax.bar(daily_df.index,daily_df["mean_sentiment"],color=colors,alpha=.85,width=.7)
    if "sentiment_ma3" in daily_df.columns:
        ax.plot(daily_df.index,daily_df["sentiment_ma3"],"k--",lw=1.2,alpha=.6,label="3-day MA")
        ax.legend(fontsize=9)
    ax.axhline(0,color="black",lw=.8); ax.set_ylabel("Mean Sentiment")
    ax.set_title("Daily Sentiment Index",fontweight="bold",fontsize=13)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d")); ax.grid(True,alpha=.25)

    ax = axes[1]
    ax.stackplot(daily_df.index,daily_df["bullish_pct"],daily_df["neutral_pct"],daily_df["bearish_pct"],
                 labels=["Bullish","Neutral","Bearish"],colors=[PAL["bullish"],PAL["neutral"],PAL["bearish"]],alpha=.8)
    ax.set_ylabel("Proportion"); ax.set_title("Daily Label Mix",fontweight="bold",fontsize=11)
    ax.legend(loc="upper right",fontsize=8); ax.set_ylim(0,1)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))

    ax = axes[2]
    ax.bar(daily_df.index,daily_df["headline_count"],color="steelblue",alpha=.7,width=.7)
    ax.set_ylabel("Headlines"); ax.set_title("News Volume",fontweight="bold",fontsize=11)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.tight_layout(); _save(fig,"03_daily_timeline.png")

    # 4. Consensus
    fig,(ax1,ax2)=plt.subplots(1,2,figsize=(13,5))
    lc=scored_df["consensus_label"].value_counts()
    ax1.pie(lc.values,labels=lc.index,colors=[PAL.get(l,"#bdc3c7") for l in lc.index],autopct="%1.0f%%",startangle=90,textprops={"fontsize":12})
    ax1.set_title("Overall Sentiment\n(Consensus of All Methods)",fontweight="bold")
    ac=scored_df["agreement"].value_counts().sort_index()
    ax2.barh(ac.index,ac.values,color="steelblue",alpha=.8)
    ax2.set_xlabel("Number of Headlines"); ax2.set_title("Method Agreement",fontweight="bold")
    for i,(idx,val) in enumerate(ac.items()): ax2.text(val+0.5,i,str(val),va="center",fontsize=10)
    fig.tight_layout(); _save(fig,"04_consensus_agreement.png")

    # 5. Sources
    top_sources = scored_df["source"].value_counts().head(15); n_src = len(top_sources)
    fig,(ax1,ax2) = plt.subplots(1,2,figsize=(16,max(5,n_src*0.4)))
    ax1.barh(top_sources.index,top_sources.values,color="steelblue",alpha=.8)
    ax1.set_xlabel("Headlines"); ax1.set_title("Headlines by Source (Top 15)",fontweight="bold")
    ax1.invert_yaxis(); ax1.tick_params(axis="y",labelsize=9)
    src_sent = scored_df.groupby("source").filter(lambda x:len(x)>=2).groupby("source")["consensus_score"].mean().sort_values().tail(15)
    colors = [PAL["bullish"] if v>0.05 else PAL["bearish"] if v<-0.05 else PAL["neutral"] for v in src_sent.values]
    ax2.barh(src_sent.index,src_sent.values,color=colors,alpha=.8)
    ax2.axvline(0,color="black",lw=.8); ax2.set_xlabel("Avg Sentiment Score")
    ax2.set_title("Avg Sentiment by Source (≥2 headlines)",fontweight="bold")
    ax2.invert_yaxis(); ax2.tick_params(axis="y",labelsize=9)
    fig.tight_layout(); _save(fig,"05_source_breakdown.png")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# REPORT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def generate_report(scored_df, daily_df):
    log.info("─"*55); log.info("GENERATING REPORT"); log.info("─"*55)
    L = []; w = L.append
    w("="*65); w("  OIL NEWS SENTIMENT ANALYSIS — REPORT"); w(f"  {datetime.now():%Y-%m-%d %H:%M:%S}"); w("="*65)
    w(f"\n  Headlines analyzed : {len(scored_df)}")
    w(f"  Date range         : {scored_df['date'].min():%Y-%m-%d} → {scored_df['date'].max():%Y-%m-%d}")
    w(f"  Sources            : {scored_df['source'].nunique()} ({', '.join(scored_df['source'].unique()[:8])})")
    w(f"\n{'─'*65}"); w("  METHODS"); w(f"{'─'*65}")
    w("  1. Dictionary     — oil-specific word lists + negation")
    w("  2. Rule-Based     — scored lexicon with boosters (VADER-style)")
    w("  3. TF-IDF + LR    — lightweight ML on synthetic training data")
    if "vader_score" in scored_df.columns: w("  4. VADER          — NLTK pre-trained sentiment analyzer")
    w(f"\n{'─'*65}"); w("  OVERALL SENTIMENT"); w(f"{'─'*65}")
    lc = scored_df["consensus_label"].value_counts()
    for l in ["bullish","neutral","bearish"]:
        n=lc.get(l,0); pct=n/len(scored_df)*100
        w(f"    {l:>8s} : {n:4d}  ({pct:5.1f}%)  {'█'*int(pct/2)}")
    avg = scored_df["consensus_score"].mean()
    tilt = "Bullish" if avg>0.05 else "Bearish" if avg<-0.05 else "Neutral"
    w(f"\n    Overall score : {avg:+.3f}  →  {tilt}")
    w(f"\n{'─'*65}"); w("  METHOD AGREEMENT"); w(f"{'─'*65}")
    for level,count in scored_df["agreement"].value_counts().sort_index(ascending=False).items():
        w(f"    {level} agree : {count:4d}  ({count/len(scored_df)*100:5.1f}%)")
    for title, subset in [("MOST BULLISH",scored_df.nlargest(5,"consensus_score")),("MOST BEARISH",scored_df.nsmallest(5,"consensus_score"))]:
        w(f"\n{'─'*65}"); w(f"  {title}"); w(f"{'─'*65}")
        for _,r in subset.iterrows():
            w(f"    [{r['consensus_score']:+.3f}] {r['headline'][:85]}")
            w(f"             — {r['source']}, {r['date']:%Y-%m-%d}")
    w(f"\n{'─'*65}"); w("  DAILY SUMMARY"); w(f"{'─'*65}")
    w(f"    {'Date':<12} {'Score':>8} {'#News':>6} {'Bull%':>7} {'Bear%':>7} {'Range':>7}")
    for d,r in daily_df.iterrows():
        w(f"    {d:%Y-%m-%d}  {r['mean_sentiment']:>+8.3f} {int(r['headline_count']):>6} {r['bullish_pct']:>7.0%} {r['bearish_pct']:>7.0%} {r['sentiment_range']:>7.3f}")
    report = "\n".join(L)
    with open(OUT_DIR/"report.txt","w") as f: f.write(report)
    log.info(f"  ✓ {OUT_DIR/'report.txt'}"); return report

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LIVE MODE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_live_running = True
def _handle_stop(sig, frame):
    global _live_running; _live_running = False; log.info("\nShutting down...")

class LiveWindow:
    def __init__(self, window_minutes=120):
        self.window_minutes = window_minutes; self.headlines = deque()
        self.seen = set(); self.total_seen = 0; self.total_new = 0

    def _prune(self):
        cutoff = datetime.now() - timedelta(minutes=self.window_minutes)
        while self.headlines and self.headlines[0][0] < cutoff: self.headlines.popleft()

    def add(self, raw):
        new = 0
        for h in raw:
            fp = h["headline"][:60].lower().strip()
            if fp in self.seen or len(h["headline"]) < 15: continue
            self.seen.add(fp); self.total_seen += 1
            score = classify_rulebased(h["headline"]); label = _label(score)
            try: dt = datetime.strptime(h.get("datetime",""), "%Y-%m-%d %H:%M:%S")
            except: dt = datetime.now()
            self.headlines.append((dt, score, label, h["headline"], h.get("source","")))
            new += 1; self.total_new += 1
            emoji = "🟢" if label=="bullish" else "🔴" if label=="bearish" else "⚪"
            log.info(f"  {emoji} [{score:+.3f}] {h['headline'][:75]}")
        self._prune(); return new

    def snapshot(self):
        self._prune()
        if not self.headlines:
            return {"status":"waiting","timestamp":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "window_minutes":self.window_minutes,"headlines_in_window":0,"message":"No headlines yet"}
        scores = [h[1] for h in self.headlines]; labels = [h[2] for h in self.headlines]
        n = len(scores); mean = np.mean(scores)
        if mean>0.3: sig="STRONG BULLISH"
        elif mean>0.15: sig="MODERATE BULLISH"
        elif mean>0.05: sig="SLIGHT BULLISH"
        elif mean>-0.05: sig="NEUTRAL"
        elif mean>-0.15: sig="SLIGHT BEARISH"
        elif mean>-0.3: sig="MODERATE BEARISH"
        else: sig="STRONG BEARISH"
        return {
            "status":"active","timestamp":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "window_minutes":self.window_minutes,
            "mean_sentiment":round(float(mean),4),
            "mean_sentiment_explanation": "Average sentiment score. -1.0 (very bearish) to +1.0 (very bullish).",
            "median_sentiment":round(float(np.median(scores)),4),
            "sentiment_std":round(float(np.std(scores)),4),
            "bullish_pct":round(labels.count("bullish")/n,3),
            "bullish_pct_explanation": "Percentage of headlines positive for oil prices.",
            "bearish_pct":round(labels.count("bearish")/n,3),
            "bearish_pct_explanation": "Percentage of headlines negative for oil prices.",
            "neutral_pct":round(labels.count("neutral")/n,3),
            "signal":sig,
            "signal_explanation": f"Overall mood based on the last {self.window_minutes} min of news.",
            "signal_strength":round(abs(float(mean)),3),
            "signal_strength_explanation": "How strong the signal is (0 = none, 0.3+ = strong).",
            "headlines_in_window":n,"total_seen":self.total_seen,"total_new":self.total_new,
            "latest_3":[{"score":h[1],"label":h[2],"headline":h[3],"source":h[4]} for h in list(self.headlines)[-3:]]
        }

def run_live(interval=15, window=120):
    global _live_running, log
    signal.signal(signal.SIGINT, _handle_stop); signal.signal(signal.SIGTERM, _handle_stop)
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    log = setup_logging(PATHS.live_log)  # CHANGED: was LIVE_DIR/"listener.log"
    log.info("="*55); log.info("  OIL NEWS — LIVE MODE"); log.info(f"  {datetime.now():%Y-%m-%d %H:%M:%S}")
    log.info(f"  Poll: {interval} min | Window: {window} min | Output: {LIVE_DIR}/")
    log.info(f"  Ctrl+C to stop"); log.info("="*55)
    w = LiveWindow(window); cycle = 0

    while _live_running:
        cycle += 1; log.info(f"\n── Cycle {cycle} ──")
        raw = []
        for q in RSS_QUERIES:
            raw.extend(scrape_google_news_rss(query=q, max_items=20)); time.sleep(0.8)
        log.info(f"  Fetched {len(raw)} raw")
        new = w.add(raw); log.info(f"  {new} new headlines")
        snap = w.snapshot()

        # CHANGED: was LIVE_DIR/"live_sentiment.json"
        with open(str(PATHS.live_sentiment),"w") as f: json.dump(snap, f, indent=2)

        # Append headline log
        if w.headlines:
            rows = [{"datetime":h[0].strftime("%Y-%m-%d %H:%M:%S"),"score":h[1],"label":h[2],"headline":h[3],"source":h[4]} for h in w.headlines]
            lp = PATHS.live_headlines_log  # CHANGED: was LIVE_DIR/"headlines_log.csv"
            exists = lp.exists()
            if not exists:
                pd.DataFrame(rows).to_csv(str(lp), index=False)
            else:
                ex = pd.read_csv(str(lp)); efp = set(ex["headline"].str[:60].str.lower())
                nr = [r for r in rows if r["headline"][:60].lower() not in efp]
                if nr: pd.DataFrame(nr).to_csv(str(lp), mode="a", header=False, index=False)

        # Append sentiment history
        if snap["status"]=="active":
            hr = {"timestamp":snap["timestamp"],"mean_sentiment":snap["mean_sentiment"],
                  "bullish_pct":snap["bullish_pct"],"bearish_pct":snap["bearish_pct"],
                  "headline_count":snap["headlines_in_window"],"signal":snap["signal"]}
            hp = PATHS.live_history  # CHANGED: was LIVE_DIR/"sentiment_history.csv"
            exists = hp.exists()
            pd.DataFrame([hr]).to_csv(str(hp), mode="a", header=not exists, index=False)

        # Dashboard
        if snap["status"]=="active":
            m=snap["mean_sentiment"]; sig=snap["signal"]; n=snap["headlines_in_window"]
            b=snap["bullish_pct"]; be=snap["bearish_pct"]; ne=snap["neutral_pct"]
            std=snap["sentiment_std"]; strength=snap["signal_strength"]
            icon = "📈" if "BULLISH" in sig else "📉" if "BEARISH" in sig else "➡️ "

            bar_pos = int((m + 1) / 2 * 30); bar_pos = max(0, min(30, bar_pos))
            score_bar = "─" * bar_pos + "●" + "─" * (30 - bar_pos)

            if std < 0.15: conf_text = "High agreement (headlines mostly say the same thing)"
            elif std < 0.30: conf_text = "Mixed signals (headlines disagree somewhat)"
            else: conf_text = "Very divided (headlines strongly contradict each other)"

            if "STRONG BULLISH" in sig: meaning = "News is overwhelmingly positive — prices likely under upward pressure"
            elif "MODERATE BULLISH" in sig: meaning = "More good news than bad — mild upward sentiment"
            elif "SLIGHT BULLISH" in sig: meaning = "Slightly more positive headlines, but close to neutral"
            elif "NEUTRAL" in sig: meaning = "Balanced mix of positive and negative news — no clear direction"
            elif "SLIGHT BEARISH" in sig: meaning = "Slightly more negative headlines, but close to neutral"
            elif "MODERATE BEARISH" in sig: meaning = "More bad news than good — mild downward sentiment"
            else: meaning = "News is overwhelmingly negative — prices likely under downward pressure"

            print(f"\n{'═' * 70}")
            print(f"  OIL MARKET SENTIMENT — LIVE MONITOR")
            print(f"  {snap['timestamp']}  (updates every {interval} min)")
            print(f"{'═' * 70}")
            print(f"\n  {icon}  SIGNAL: {sig}")
            print(f"  └─ {meaning}")
            print(f"\n  SENTIMENT SCORE: {m:>+.4f}")
            print(f"  Bearish ←  {score_bar}  → Bullish")
            print(f"  Scale: -1.0 (very bearish) to +1.0 (very bullish)")
            print(f"\n  HEADLINE BREAKDOWN:")
            bull_bar = "█" * max(1, int(b * 30))
            bear_bar = "█" * max(1, int(be * 30))
            neut_bar = "█" * max(1, int(ne * 30))
            print(f"    🟢 Bullish:  {b:>5.0%}  {bull_bar}")
            print(f"    ⚪ Neutral:  {ne:>5.0%}  {neut_bar}")
            print(f"    🔴 Bearish:  {be:>5.0%}  {bear_bar}")
            print(f"    (out of {n} headlines in the last {snap['window_minutes']} min)")
            print(f"\n  CONFIDENCE: {conf_text}")
            print(f"\n  THIS CYCLE: scraped {len(raw)} headlines, {new} were new")
            print(f"  SESSION TOTAL: {snap['total_seen']} headlines seen, {snap['total_new']} unique")

            if snap.get("latest_3"):
                print(f"\n  LATEST HEADLINES:")
                for h in snap["latest_3"]:
                    e = "🟢" if h["label"]=="bullish" else "🔴" if h["label"]=="bearish" else "⚪"
                    print(f"    {e} [{h['score']:+.3f}] {h['headline'][:65]}")
                    if h["source"]: print(f"       └─ {h['source']}")

            print(f"\n{'─' * 70}")
            print(f"  Files: {PATHS.live_sentiment} (read this from your model)")
            print(f"  Stop:  Ctrl+C")
            print(f"{'─' * 70}\n")

        else:
            log.info("  Waiting for headlines...")

        if _live_running:
            log.info(f"  Next poll in {interval} min...")
            for _ in range(interval*60):
                if not _live_running: break
                time.sleep(1)

    log.info("="*55)
    log.info(f"  STOPPED | Seen: {w.total_seen} | New: {w.total_new} | Files: {LIVE_DIR}/")
    log.info("="*55)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main_normal():
    log.info("="*55); log.info("  OIL NEWS SENTIMENT SCRAPER")
    log.info(f"  {datetime.now():%Y-%m-%d %H:%M:%S}"); log.info("="*55)
    headlines = scrape_all()
    if not headlines: log.error("No headlines. Check internet."); sys.exit(1)
    scored_df = classify_all(headlines)
    daily_df = build_daily_index(scored_df)
    generate_plots(scored_df, daily_df)
    log.info("─"*55); log.info("SAVING FILES"); log.info("─"*55)
    scored_df.to_csv(OUT_DIR/"scored_headlines.csv", index=False)
    log.info(f"  ✓ scored_headlines.csv ({len(scored_df)} rows)")
    daily_df.to_csv(OUT_DIR/"daily_sentiment.csv")
    log.info(f"  ✓ daily_sentiment.csv ({len(daily_df)} rows)")
    report = generate_report(scored_df, daily_df)
    print("\n"+report)
    log.info(f"\n{'='*55}"); log.info(f"  DONE — {OUT_DIR}/"); log.info("="*55)
    return scored_df, daily_df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Oil News Sentiment Scraper")
    parser.add_argument("--live", nargs="?", const=15, type=int, metavar="MINS",
                        help="Live mode: poll every N min (default 15)")
    parser.add_argument("--window", type=int, default=120,
                        help="Rolling window in minutes for live mode (default 120)")
    args = parser.parse_args()
    if args.live is not None:
        run_live(interval=args.live, window=args.window)
    else:
        main_normal()