"""
Oil News Sentiment Scraper — Standalone Module
================================================
Citibank Oil Price Risk Factor Challenge

Scrapes oil-related news headlines from multiple sources,
classifies sentiment using 3 approaches, and produces
standalone result files.

This module is INDEPENDENT — it does not read, write, or
modify any other project files. All outputs go to:
    → news_output/

Setup:
    pip install -r requirements_news.txt
    cp env.example .env          # add your NewsAPI key (optional)
    python news_scraper.py

Author: Arturo
"""

import os
import re
import sys
import json
import time
import hashlib
import logging
from datetime import datetime, timedelta
from collections import Counter
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from dotenv import load_dotenv
load_dotenv()

# ── Configuration ────────────────────────────────────────────
OUT_DIR     = Path("news_output")
PLOT_DIR    = OUT_DIR / "plots"
CACHE_DIR   = OUT_DIR / "cache"
LOG_FILE    = OUT_DIR / "scraper.log"

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Polite delay between requests (seconds)
REQUEST_DELAY = 1.5


# ── Logging ──────────────────────────────────────────────────

def setup_logging():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_FILE, mode="w"),
        ],
    )
    return logging.getLogger("news_scraper")

log = setup_logging()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 1 — SCRAPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import requests
from bs4 import BeautifulSoup


def _safe_get(url, timeout=15):
    """GET with error handling — returns (response, error_msg)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        if resp.status_code == 200:
            return resp, None
        return None, f"HTTP {resp.status_code}"
    except requests.exceptions.Timeout:
        return None, "timeout"
    except requests.exceptions.ConnectionError:
        return None, "connection refused"
    except Exception as e:
        return None, str(e)


# ── 1a. Google News RSS (most reliable, no key needed) ───────

def scrape_google_news_rss(query="crude oil price", max_items=40):
    """
    Google News exposes an RSS feed for any search query.
    RSS = structured XML, so no fragile HTML parsing required.
    """
    log.info(f"  Google News RSS  →  query: '{query}'")
    headlines = []

    encoded = query.replace(" ", "+")
    url = (
        f"https://news.google.com/rss/search?"
        f"q={encoded}&hl=en-US&gl=US&ceid=US:en"
    )

    resp, err = _safe_get(url)
    if err:
        log.warning(f"    ✗ {err}")
        return headlines

    soup = BeautifulSoup(resp.text, "xml")

    for item in soup.find_all("item")[:max_items]:
        title = item.find("title")
        pub   = item.find("pubDate")
        src   = item.find("source")
        link  = item.find("link")

        if not title:
            continue

        date_str = datetime.now().strftime("%Y-%m-%d")
        if pub:
            try:
                dt = datetime.strptime(pub.text.strip(), "%a, %d %b %Y %H:%M:%S %Z")
                date_str = dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

        headlines.append({
            "headline": title.text.strip(),
            "date":     date_str,
            "source":   src.text.strip() if src else "google_news",
            "url":      link.text.strip() if link else "",
        })

    log.info(f"    ✓ {len(headlines)} headlines")
    return headlines


# ── 1b. NewsAPI.org (structured JSON, needs free key) ────────

def scrape_newsapi(query="crude oil", days_back=14, page_size=100):
    """
    NewsAPI returns clean JSON with dates, sources, descriptions.
    Free tier: 100 req/day, 1-month history.
    Key → https://newsapi.org/register → add to .env as NEWS_API_KEY
    """
    if not NEWS_API_KEY:
        log.info("  NewsAPI           →  skipped (no key in .env)")
        return []

    log.info(f"  NewsAPI           →  query: '{query}', {days_back}d lookback")
    headlines = []

    from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    url = "https://newsapi.org/v2/everything"
    params = {
        "q":        query,
        "from":     from_date,
        "sortBy":   "relevancy",
        "language": "en",
        "pageSize": page_size,
        "apiKey":   NEWS_API_KEY,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()

        if data.get("status") != "ok":
            log.warning(f"    ✗ {data.get('message', 'unknown error')}")
            return headlines

        for art in data.get("articles", []):
            headlines.append({
                "headline":    art.get("title", ""),
                "description": art.get("description", ""),
                "date":        art.get("publishedAt", "")[:10],
                "source":      art.get("source", {}).get("name", "newsapi"),
                "url":         art.get("url", ""),
            })
        log.info(f"    ✓ {len(headlines)} articles")
    except Exception as e:
        log.warning(f"    ✗ {e}")

    return headlines


# ── 1c. Reuters Energy ───────────────────────────────────────

def scrape_reuters():
    """Reuters energy section — HTML scraping."""
    log.info("  Reuters Energy    →  scraping")
    headlines = []

    resp, err = _safe_get("https://www.reuters.com/business/energy/")
    if err:
        log.warning(f"    ✗ {err}")
        return headlines

    soup = BeautifulSoup(resp.text, "html.parser")
    seen = set()

    for tag in ["h3", "a"]:
        for el in soup.find_all(tag):
            text = el.get_text(strip=True)
            if 20 < len(text) < 300 and text not in seen:
                seen.add(text)
                headlines.append({
                    "headline": text,
                    "date":     datetime.now().strftime("%Y-%m-%d"),
                    "source":   "reuters",
                    "url":      "",
                })

    log.info(f"    ✓ {len(headlines)} headlines")
    return headlines


# ── 1d. OilPrice.com ─────────────────────────────────────────

def scrape_oilprice(max_pages=3):
    """OilPrice.com — dedicated oil/energy news site."""
    log.info(f"  OilPrice.com      →  {max_pages} pages")
    headlines = []
    seen = set()

    for page in range(1, max_pages + 1):
        url = (
            "https://oilprice.com/Latest-Energy-News/World-News/"
            if page == 1
            else f"https://oilprice.com/Latest-Energy-News/World-News/{page}"
        )

        resp, err = _safe_get(url)
        if err:
            log.warning(f"    ✗ page {page}: {err}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = a["href"]
            if 25 < len(text) < 300 and "/Article/" in href and text not in seen:
                seen.add(text)
                headlines.append({
                    "headline": text,
                    "date":     datetime.now().strftime("%Y-%m-%d"),
                    "source":   "oilprice",
                    "url":      href if href.startswith("http") else f"https://oilprice.com{href}",
                })

        if page < max_pages:
            time.sleep(REQUEST_DELAY)

    log.info(f"    ✓ {len(headlines)} headlines")
    return headlines


# ── Orchestrator ─────────────────────────────────────────────

def scrape_all():
    """
    Runs every scraper, deduplicates, caches to disk.
    Returns list[dict].
    """
    log.info("─" * 55)
    log.info("SCRAPING NEWS SOURCES")
    log.info("─" * 55)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"headlines_{datetime.now():%Y%m%d}.json"

    if cache_file.exists():
        log.info(f"Cache hit → {cache_file.name}")
        with open(cache_file) as f:
            cached = json.load(f)
        log.info(f"Loaded {len(cached)} cached headlines")
        return cached

    raw = []

    # Google News — multiple oil-related queries
    for q in ["crude oil price", "OPEC oil production", "oil supply demand",
              "WTI Brent crude", "oil geopolitical risk"]:
        raw.extend(scrape_google_news_rss(query=q, max_items=30))
        time.sleep(REQUEST_DELAY)

    # NewsAPI (if key present)
    for q in ["crude oil", "OPEC", "oil prices"]:
        raw.extend(scrape_newsapi(query=q, days_back=14))
        time.sleep(REQUEST_DELAY)

    # Reuters & OilPrice
    raw.extend(scrape_reuters())
    time.sleep(REQUEST_DELAY)
    raw.extend(scrape_oilprice(max_pages=3))

    # Deduplicate (first 60 chars lowercased)
    seen = set()
    unique = []
    for h in raw:
        fp = h["headline"][:60].lower().strip()
        if fp not in seen and len(h["headline"]) > 15:
            seen.add(fp)
            unique.append(h)

    log.info(f"\nTotal unique headlines: {len(unique)}")

    with open(cache_file, "w") as f:
        json.dump(unique, f, indent=2)
    log.info(f"Cached → {cache_file.name}")

    return unique


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 2 — SENTIMENT CLASSIFIERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── Oil-domain lexicon ───────────────────────────────────────

_POS = {
    'surge','surges','surging','rally','rallies','rallying',
    'jump','jumps','jumping','soar','soars','soaring',
    'climb','climbs','climbing','gain','gains','gaining',
    'rise','rises','rising','spike','spikes','spiking',
    'rebound','rebounds','recover','recovers','recovery',
    'bullish','boom','booming','uptick','upswing',
    'high','higher','highest','record',
    'shortage','shortfall','deficit','tight','tighten',
    'cut','cuts','cutting','reduce','reduction',
    'drawdown','draw','sanctions','embargo',
    'disruption','disruptions','outage',
    'growth','expanding','strong','robust',
    'optimism','optimistic','confidence',
}
_NEG = {
    'fall','falls','falling','drop','drops','dropping',
    'decline','declines','declining','plunge','plunges',
    'crash','crashes','crashing','tumble','tumbles',
    'slide','slides','sliding','sink','sinks','sinking',
    'slump','slumps','plummet','plummets',
    'bearish','downturn','selloff','sell-off',
    'low','lower','lowest','weak','weaker',
    'surplus','glut','oversupply','overproduction',
    'build','buildup','build-up','flood','flooding','excess',
    'slowdown','recession','contraction','weakness','slowing',
    'fear','fears','concern','concerns','worry','worries',
    'uncertainty','volatile','volatility','risk','risks',
    'war','conflict','tension','tensions','crisis',
    'pressure','pressuring',
}
_NEGATE = {'not','no','never','neither','nor','barely','hardly'}
_BOOST  = {
    'very':1.5,'extremely':2.0,'sharply':1.8,'significantly':1.7,
    'massively':2.0,'deeply':1.6,'strongly':1.5,'heavily':1.5,
    'slightly':0.5,'somewhat':0.6,'marginally':0.5,
}

# Intensity overrides
_SCORE = {}
for w in _POS: _SCORE[w] = 0.4
for w in _NEG: _SCORE[w] = -0.4
for w in ['surge','surging','soar','soaring','spike','spiking','boom','booming']:
    _SCORE[w] = 0.7
for w in ['crash','crashing','plunge','plunges','plummet','collapse']:
    _SCORE[w] = -0.7
for w in ['rally','rallying','rebound','recovery','bullish','record']:
    _SCORE[w] = 0.5
for w in ['recession','crisis','selloff','sell-off','bearish','downturn']:
    _SCORE[w] = -0.6


def _clean(w):
    return re.sub(r"[^\w-]", "", w.lower())


# ── Approach 1: Dictionary ───────────────────────────────────

def classify_dictionary(text):
    words = text.lower().split()
    pos, neg = 0, 0
    for i, w in enumerate(words):
        c = _clean(w)
        negated = i > 0 and _clean(words[i-1]) in _NEGATE
        if c in _POS:
            if negated: neg += 1
            else:       pos += 1
        elif c in _NEG:
            if negated: pos += 1
            else:       neg += 1
    total = pos + neg
    score = (pos - neg) / total if total else 0.0
    return round(score, 3)


# ── Approach 2: Rule-based (VADER-like) ──────────────────────

def classify_rulebased(text):
    words = text.lower().split()
    total = 0.0
    n = 0
    for i, w in enumerate(words):
        c = _clean(w)
        if c not in _SCORE:
            continue
        s = _SCORE[c]
        for j in range(max(0, i-2), i):
            p = _clean(words[j])
            if p in _NEGATE:  s *= -0.8;  break
            if p in _BOOST:   s *= _BOOST[p]; break
        total += s
        n += 1
    return round(float(np.tanh(total * 0.8)), 3) if n else 0.0


# ── Approach 3: TF-IDF + Logistic Regression ─────────────────

def _build_tfidf_model():
    """Trains a small ML classifier from synthetic oil news data."""
    pos_t = [
        "oil prices {w} amid supply concerns",
        "crude {w} on OPEC production cuts",
        "brent crude {w} after supply disruption",
        "energy stocks {w} on strong demand",
        "oil market shows {w} momentum",
    ]
    neg_t = [
        "oil prices {w} on demand weakness",
        "crude {w} amid economic slowdown",
        "oil market hit by {w} in demand",
        "energy sector {w} as oil weakens",
        "brent crude {w} on oversupply fears",
    ]
    texts, labels = [], []
    for w in list(_POS)[:30]:
        for t in pos_t:
            texts.append(t.format(w=w)); labels.append(1)
    for w in list(_NEG)[:30]:
        for t in neg_t:
            texts.append(t.format(w=w)); labels.append(-1)
    neutral = [
        "oil prices remain unchanged in quiet trading",
        "crude holds near previous close ahead of data release",
        "oil market awaits weekly inventory report from EIA",
        "brent and WTI trade in narrow range today",
        "energy markets mixed on lack of clear catalysts",
    ] * 20
    texts.extend(neutral)
    labels.extend([0] * len(neutral))

    vec = TfidfVectorizer(max_features=500, ngram_range=(1, 2))
    X = vec.fit_transform(texts)
    clf = LogisticRegression(max_iter=500, C=1.0, random_state=42)
    clf.fit(X, labels)
    return vec, clf


def classify_tfidf(text, vec, clf):
    X = vec.transform([text])
    pred  = clf.predict(X)[0]
    proba = clf.predict_proba(X)[0]
    order = clf.classes_.tolist()
    p_pos = proba[order.index(1)]  if 1  in order else 0
    p_neg = proba[order.index(-1)] if -1 in order else 0
    return round(float(p_pos - p_neg), 3)


# ── VADER (optional, if nltk is installed) ───────────────────

def classify_vader(text):
    """Uses NLTK VADER if available, otherwise returns None."""
    try:
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        import nltk
        try:
            nltk.data.find("sentiment/vader_lexicon.zip")
        except LookupError:
            nltk.download("vader_lexicon", quiet=True)
        if not hasattr(classify_vader, "_sia"):
            classify_vader._sia = SentimentIntensityAnalyzer()
        return round(classify_vader._sia.polarity_scores(text)["compound"], 3)
    except ImportError:
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 3 — CLASSIFICATION PIPELINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _label(score, pos_thresh=0.05, neg_thresh=-0.05):
    if score > pos_thresh:  return "bullish"
    if score < neg_thresh:  return "bearish"
    return "neutral"


def classify_all(headlines):
    """
    Runs all classification methods on every headline.
    Returns a clean DataFrame.
    """
    log.info("─" * 55)
    log.info("CLASSIFYING HEADLINES")
    log.info("─" * 55)

    vec, clf = _build_tfidf_model()
    log.info("  TF-IDF model trained")

    has_vader = classify_vader("test") is not None
    if has_vader:
        log.info("  VADER available ✓")
    else:
        log.info("  VADER unavailable (install nltk for it)")

    rows = []
    for i, h in enumerate(headlines):
        text = h["headline"]

        d_score = classify_dictionary(text)
        r_score = classify_rulebased(text)
        m_score = classify_tfidf(text, vec, clf)
        v_score = classify_vader(text) if has_vader else None

        # Consensus: average available scores
        scores = [d_score, r_score, m_score]
        if v_score is not None:
            scores.append(v_score)
        avg = round(np.mean(scores), 3)

        # Label agreement
        labels = [_label(d_score), _label(r_score), _label(m_score)]
        if v_score is not None:
            labels.append(_label(v_score))
        counts = Counter(labels)
        consensus_label, consensus_n = counts.most_common(1)[0]

        row = {
            "date":                h["date"],
            "source":              h["source"],
            "headline":            text,
            "url":                 h.get("url", ""),
            "dict_score":          d_score,
            "rulebased_score":     r_score,
            "tfidf_score":         m_score,
            "consensus_score":     avg,
            "consensus_label":     consensus_label,
            "agreement":           f"{consensus_n}/{len(labels)}",
        }
        if v_score is not None:
            row["vader_score"] = v_score

        rows.append(row)

        if (i + 1) % 50 == 0:
            log.info(f"  {i+1}/{len(headlines)} classified")

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "source"], ascending=[False, True]).reset_index(drop=True)

    # Summary
    lc = df["consensus_label"].value_counts()
    log.info(f"\n  Results ({len(df)} headlines):")
    for label in ["bullish", "neutral", "bearish"]:
        n = lc.get(label, 0)
        log.info(f"    {label:>8s}  {n:>4d}  ({n/len(df)*100:5.1f}%)")
    log.info(f"    avg score: {df['consensus_score'].mean():+.3f}")

    return df


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 4 — DAILY AGGREGATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_daily_index(scored_df):
    """Collapses per-headline scores into one row per day."""
    log.info("─" * 55)
    log.info("BUILDING DAILY SENTIMENT INDEX")
    log.info("─" * 55)

    df = scored_df.copy()

    daily = df.groupby("date").agg(
        mean_sentiment    = ("consensus_score", "mean"),
        median_sentiment  = ("consensus_score", "median"),
        sentiment_std     = ("consensus_score", "std"),
        max_sentiment     = ("consensus_score", "max"),
        min_sentiment     = ("consensus_score", "min"),
        headline_count    = ("consensus_score", "count"),
        bullish_pct       = ("consensus_label", lambda x: (x == "bullish").mean()),
        bearish_pct       = ("consensus_label", lambda x: (x == "bearish").mean()),
        neutral_pct       = ("consensus_label", lambda x: (x == "neutral").mean()),
    ).round(4)

    daily["sentiment_std"]   = daily["sentiment_std"].fillna(0)
    daily["sentiment_range"] = daily["max_sentiment"] - daily["min_sentiment"]
    daily["sentiment_delta"] = daily["mean_sentiment"].diff()
    daily["sentiment_ma3"]   = daily["mean_sentiment"].rolling(3, min_periods=1).mean().round(4)
    daily.index.name = "date"

    log.info(f"  {len(daily)} trading days")
    log.info(f"  {daily.index.min().date()} → {daily.index.max().date()}")

    return daily


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 5 — VISUALIZATIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PAL = {"bullish": "#27ae60", "neutral": "#7f8c8d", "bearish": "#e74c3c"}

def _save(fig, name):
    fig.savefig(PLOT_DIR / name, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    log.info(f"    ✓ {name}")


def generate_plots(scored_df, daily_df):
    log.info("─" * 55)
    log.info("GENERATING PLOTS")
    log.info("─" * 55)
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    sns.set_style("whitegrid")

    # ── 1. Score distribution per method ──────────────────────
    methods = ["dict_score", "rulebased_score", "tfidf_score"]
    names   = ["Dictionary", "Rule-Based", "TF-IDF ML"]
    if "vader_score" in scored_df.columns:
        methods.append("vader_score")
        names.append("VADER")

    fig, axes = plt.subplots(1, len(methods), figsize=(5 * len(methods), 5), sharey=True)
    if len(methods) == 1:
        axes = [axes]
    for ax, col, name in zip(axes, methods, names):
        data = scored_df[col].dropna()
        ax.hist(data[data > 0.05],  bins=15, color=PAL["bullish"], alpha=.75, label="Bullish")
        ax.hist(data[(data >= -0.05) & (data <= 0.05)], bins=5, color=PAL["neutral"], alpha=.75, label="Neutral")
        ax.hist(data[data < -0.05], bins=15, color=PAL["bearish"], alpha=.75, label="Bearish")
        ax.axvline(0, color="black", lw=.8)
        ax.set_title(name, fontweight="bold")
        ax.set_xlabel("Score")
        if ax == axes[0]:
            ax.set_ylabel("Headlines")
            ax.legend(fontsize=8)
    fig.suptitle("Score Distributions by Classification Method", fontweight="bold", fontsize=14, y=1.02)
    _save(fig, "01_score_distributions.png")

    # ── 2. Heatmap: headline × method ────────────────────────
    sample = pd.concat([
        scored_df.nlargest(15, "consensus_score"),
        scored_df.nsmallest(15, "consensus_score"),
    ]).drop_duplicates("headline")

    matrix = sample.set_index(
    sample["headline"].str[:50].to_numpy()  # Force conversion to a standard array
    )[methods + ["consensus_score"]]
    matrix.columns = names + ["Consensus"]

    fig, ax = plt.subplots(figsize=(10, max(6, len(matrix) * 0.35)))
    sns.heatmap(matrix, annot=True, fmt=".2f", cmap="RdYlGn", center=0,
                vmin=-1, vmax=1, linewidths=.4, ax=ax,
                cbar_kws={"label": "Sentiment Score"})
    ax.set_title("Top Bullish & Bearish Headlines — All Methods", fontweight="bold", fontsize=12)
    ax.tick_params(axis="y", labelsize=7)
    _save(fig, "02_headline_heatmap.png")

    # ── 3. Daily sentiment timeline ──────────────────────────
    fig, axes = plt.subplots(3, 1, figsize=(14, 10),
                             gridspec_kw={"height_ratios": [3, 2, 1]})

    ax = axes[0]
    colors = ["#27ae60" if v > 0 else "#e74c3c" for v in daily_df["mean_sentiment"]]
    ax.bar(daily_df.index, daily_df["mean_sentiment"], color=colors, alpha=.85, width=.7)
    if "sentiment_ma3" in daily_df.columns:
        ax.plot(daily_df.index, daily_df["sentiment_ma3"], "k--", lw=1.2, alpha=.6, label="3-day MA")
        ax.legend(fontsize=9)
    ax.axhline(0, color="black", lw=.8)
    ax.set_ylabel("Mean Sentiment")
    ax.set_title("Daily Sentiment Index", fontweight="bold", fontsize=13)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.grid(True, alpha=.25)

    ax = axes[1]
    ax.stackplot(
        daily_df.index,
        daily_df["bullish_pct"], daily_df["neutral_pct"], daily_df["bearish_pct"],
        labels=["Bullish", "Neutral", "Bearish"],
        colors=[PAL["bullish"], PAL["neutral"], PAL["bearish"]], alpha=.8,
    )
    ax.set_ylabel("Proportion")
    ax.set_title("Daily Label Mix", fontweight="bold", fontsize=11)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_ylim(0, 1)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))

    ax = axes[2]
    ax.bar(daily_df.index, daily_df["headline_count"], color="steelblue", alpha=.7, width=.7)
    ax.set_ylabel("Headlines")
    ax.set_title("News Volume", fontweight="bold", fontsize=11)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.tight_layout()
    _save(fig, "03_daily_timeline.png")

    # ── 4. Consensus pie + agreement ─────────────────────────
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    lc = scored_df["consensus_label"].value_counts()
    ax1.pie(lc.values, labels=lc.index,
            colors=[PAL.get(l, "#bdc3c7") for l in lc.index],
            autopct="%1.0f%%", startangle=90, textprops={"fontsize": 12})
    ax1.set_title("Overall Sentiment\n(Consensus of All Methods)", fontweight="bold")

    agree_counts = scored_df["agreement"].value_counts().sort_index()
    ax2.barh(agree_counts.index, agree_counts.values, color="steelblue", alpha=.8)
    ax2.set_xlabel("Number of Headlines")
    ax2.set_title("Method Agreement", fontweight="bold")
    for i, (idx, val) in enumerate(agree_counts.items()):
        ax2.text(val + 0.5, i, str(val), va="center", fontsize=10)

    fig.tight_layout()
    _save(fig, "04_consensus_agreement.png")

    # ── 5. Source breakdown ──────────────────────────
    top_sources = scored_df["source"].value_counts().head(15)

    n_src = len(top_sources)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, max(5, n_src * 0.4)))

    ax1.barh(top_sources.index, top_sources.values, color="steelblue", alpha=.8)
    ax1.set_xlabel("Headlines")
    ax1.set_title("Headlines by Source (Top 15)", fontweight="bold")
    ax1.invert_yaxis()
    ax1.tick_params(axis="y", labelsize=9)

    # Only show sentiment for sources with 2+ headlines (avoids noise)
    src_sent = (
        scored_df.groupby("source")
        .filter(lambda x: len(x) >= 2)
        .groupby("source")["consensus_score"]
        .mean()
        .sort_values()
        .tail(15)
    )
    colors = [PAL["bullish"] if v > 0.05 else PAL["bearish"] if v < -0.05 else PAL["neutral"]
              for v in src_sent.values]
    ax2.barh(src_sent.index, src_sent.values, color=colors, alpha=.8)
    ax2.axvline(0, color="black", lw=.8)
    ax2.set_xlabel("Avg Sentiment Score")
    ax2.set_title("Avg Sentiment by Source (≥2 headlines)", fontweight="bold")
    ax2.invert_yaxis()
    ax2.tick_params(axis="y", labelsize=9)

    fig.tight_layout()
    _save(fig, "05_source_breakdown.png")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 6 — TEXT REPORT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_report(scored_df, daily_df):
    log.info("─" * 55)
    log.info("GENERATING REPORT")
    log.info("─" * 55)

    L = []
    w = L.append

    w("=" * 65)
    w("  OIL NEWS SENTIMENT ANALYSIS — REPORT")
    w(f"  {datetime.now():%Y-%m-%d %H:%M:%S}")
    w("=" * 65)

    w(f"\n  Headlines analyzed : {len(scored_df)}")
    w(f"  Date range         : {scored_df['date'].min():%Y-%m-%d} → {scored_df['date'].max():%Y-%m-%d}")
    w(f"  Sources            : {scored_df['source'].nunique()} ({', '.join(scored_df['source'].unique()[:8])})")

    w(f"\n{'─' * 65}")
    w("  METHODS")
    w(f"{'─' * 65}")
    w("  1. Dictionary     — oil-specific word lists + negation")
    w("  2. Rule-Based     — scored lexicon with boosters (VADER-style)")
    w("  3. TF-IDF + LR    — lightweight ML on synthetic training data")
    if "vader_score" in scored_df.columns:
        w("  4. VADER          — NLTK pre-trained sentiment analyzer")

    w(f"\n{'─' * 65}")
    w("  OVERALL SENTIMENT")
    w(f"{'─' * 65}")
    lc = scored_df["consensus_label"].value_counts()
    for label in ["bullish", "neutral", "bearish"]:
        n = lc.get(label, 0)
        pct = n / len(scored_df) * 100
        bar = "█" * int(pct / 2)
        w(f"    {label:>8s} : {n:4d}  ({pct:5.1f}%)  {bar}")
    avg = scored_df["consensus_score"].mean()
    tilt = "Bullish" if avg > 0.05 else "Bearish" if avg < -0.05 else "Neutral"
    w(f"\n    Overall score : {avg:+.3f}  →  {tilt}")

    # Agreement
    w(f"\n{'─' * 65}")
    w("  METHOD AGREEMENT")
    w(f"{'─' * 65}")
    ag = scored_df["agreement"].value_counts().sort_index(ascending=False)
    for level, count in ag.items():
        w(f"    {level} agree : {count:4d}  ({count/len(scored_df)*100:5.1f}%)")

    # Top headlines
    for title, subset in [("MOST BULLISH", scored_df.nlargest(5, "consensus_score")),
                          ("MOST BEARISH", scored_df.nsmallest(5, "consensus_score"))]:
        w(f"\n{'─' * 65}")
        w(f"  {title}")
        w(f"{'─' * 65}")
        for _, r in subset.iterrows():
            w(f"    [{r['consensus_score']:+.3f}] {r['headline'][:85]}")
            w(f"             — {r['source']}, {r['date']:%Y-%m-%d}")

    # Daily table
    w(f"\n{'─' * 65}")
    w("  DAILY SUMMARY")
    w(f"{'─' * 65}")
    w(f"    {'Date':<12} {'Score':>8} {'#News':>6} {'Bull%':>7} {'Bear%':>7} {'Range':>7}")
    for d, r in daily_df.iterrows():
        w(f"    {d:%Y-%m-%d}  {r['mean_sentiment']:>+8.3f} {int(r['headline_count']):>6}"
          f" {r['bullish_pct']:>7.0%} {r['bearish_pct']:>7.0%} {r['sentiment_range']:>7.3f}")

    report = "\n".join(L)

    path = OUT_DIR / "report.txt"
    with open(path, "w") as f:
        f.write(report)
    log.info(f"  ✓ {path}")

    return report


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    log.info("=" * 55)
    log.info("  OIL NEWS SENTIMENT SCRAPER")
    log.info(f"  {datetime.now():%Y-%m-%d %H:%M:%S}")
    log.info("=" * 55)

    # 1  Scrape
    headlines = scrape_all()
    if not headlines:
        log.error("No headlines scraped. Check your internet connection.")
        sys.exit(1)

    # 2  Classify
    scored_df = classify_all(headlines)

    # 3  Daily index
    daily_df = build_daily_index(scored_df)

    # 4  Plots
    generate_plots(scored_df, daily_df)

    # 5  Save CSVs
    log.info("─" * 55)
    log.info("SAVING FILES")
    log.info("─" * 55)

    scored_df.to_csv(OUT_DIR / "scored_headlines.csv", index=False)
    log.info(f"  ✓ scored_headlines.csv   ({len(scored_df)} rows)")

    daily_df.to_csv(OUT_DIR / "daily_sentiment.csv")
    log.info(f"  ✓ daily_sentiment.csv    ({len(daily_df)} rows)")

    # 6  Report
    report = generate_report(scored_df, daily_df)
    print("\n" + report)

    log.info("\n" + "=" * 55)
    log.info(f"  DONE — all files in {OUT_DIR}/")
    log.info("=" * 55)

    return scored_df, daily_df


if __name__ == "__main__":
    main()