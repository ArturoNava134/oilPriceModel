# Oil News Sentiment Scraper

**Author:** Arturo  
**Competition:** Citibank Oil Price Risk Factor Challenge

---

Hey! This is the news sentiment module. It scrapes real oil/energy headlines from the internet, figures out if each one is bullish or bearish, and spits out a daily sentiment score we can use as a risk factor.

It's **completely standalone** — it doesn't touch `oil_data_collector.py` or any of your CSVs. Everything it creates goes into `news_output/`.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements_news.txt

# 2. Add your NewsAPI key to the EXISTING .env file (optional but recommended)
# Just add this line at the bottom of your .env:
# NEWS_API_KEY=your_key_here

# 3. Run it
python news_scraper.py
```

That's it. Takes about 30-60 seconds. You'll get scored headlines, daily sentiment, 5 charts, and a text report.

---

## API Key Setup

You only need **one key** for this module, and it's optional. The scraper works without it (using Google News RSS, Reuters, and OilPrice.com), but adding it gives you way more headlines from way more sources.

### NewsAPI (optional, recommended)

1. Go to 👉 https://newsapi.org/register
2. Create a free account (30 seconds)
3. Copy your API key
4. **Add it to your existing `.env` file** — just add a new line at the bottom:

```
FRED_API_KEY=your_fred_key
EIA_API_KEY=your_eia_key
NEWS_API_KEY=your_newsapi_key_here    ← add this line
```

Free tier gives you 100 requests/day and 1 month of article history. More than enough.

> **Note:** The `env.example.news` file is just a reference. Since you already have a `.env` with your FRED and EIA keys, just add the `NEWS_API_KEY=` line there. Don't create a second `.env` file.

---

## Where Does the Data Come From?

The scraper hits 4 sources. Here's what each one does and why:

| Source | How it works | API key? | What you get |
|--------|-------------|----------|-------------|
| **Google News RSS** | Fetches an XML feed for oil-related search queries | No | Headlines from hundreds of outlets (Reuters, Bloomberg, FT, etc.) with real publication dates |
| **NewsAPI** | Calls a structured JSON API that searches 80,000+ news sources | Yes (free) | Best metadata — exact dates, descriptions, source names |
| **Reuters** | Scrapes the Reuters energy section HTML | No | High-quality financial journalism headlines |
| **OilPrice.com** | Scrapes a dedicated oil/energy news site | No | Almost every headline is oil-relevant |

The scraper runs all of them, deduplicates (removes repeated headlines), and caches results so you don't re-scrape if you run it twice the same day.

---

## How Does Sentiment Classification Work?

Each headline gets scored from **-1** (very bearish) to **+1** (very bullish) by 3 different methods. Here's what each one does:

### Method 1: Dictionary-Based

The simplest approach. I built two word lists:
- **Positive words** → "surge", "rally", "cut", "shortage", "rebound" (things that push oil up)
- **Negative words** → "crash", "glut", "recession", "fear", "selloff" (things that push oil down)

It counts how many positive vs negative words appear in the headline and gives a score. It also handles **negation** — if the headline says "oil not expected to rally", the word "rally" gets flipped to negative because of "not".

**Pro:** Fast, transparent, you can see exactly why it scored that way.  
**Con:** Dumb about context. "Oil demand growth slowing" has "growth" (positive) and "slowing" (negative) — the dictionary sees both but doesn't understand one modifies the other.

### Method 2: Rule-Based (VADER-like)

Same word lists, but smarter. Each word gets an **intensity score** instead of just +1/-1:
- "crashes" = -0.7 (strong negative)
- "falls" = -0.4 (moderate negative)
- "dips" = -0.2 (mild negative)

It also understands **boosters** — "sharply falls" scores more negative than just "falls", and "slightly drops" scores less negative than "drops".

**Pro:** Captures intensity and degree.  
**Con:** Still keyword-based, can miss sarcasm or complex phrasing.

### Method 3: TF-IDF + Logistic Regression (ML)

This one actually uses machine learning. It converts each headline into a numeric vector using **TF-IDF** (a technique that measures how important each word is in the context of all headlines), then a **logistic regression** classifier decides bullish/neutral/bearish.

The model is trained on synthetic oil headlines I generated from the word lists. In a production setup you'd replace this with **FinBERT** (a neural network trained on real financial text), but this lightweight version works without needing a 400MB model download.

**Pro:** Learns word combinations, not just individual words.  
**Con:** Trained on synthetic data, so it's only as good as the templates.

### Bonus: VADER (if you installed nltk)

If you ran `pip install nltk` and downloaded the VADER lexicon, the scraper automatically adds a 4th method. VADER is a pre-trained general-purpose sentiment analyzer from NLTK. It's not oil-specific but it's good as a cross-check.

### How Consensus Works

The final score for each headline is the **average of all available methods**. The final label (bullish/neutral/bearish) is decided by **majority vote**. The `agreement` column tells you how reliable it is:
- `3/3` or `4/4` = all methods agree → high confidence
- `2/3` = one method disagrees → moderate confidence
- `1/3` = all disagree → ambiguous headline, treat with caution

---

## Output Files

After running the script, check `news_output/`:

| File | What's in it |
|------|-------------|
| `scored_headlines.csv` | Every headline with scores from all methods, consensus label, agreement level |
| `daily_sentiment.csv` | One row per day — daily average sentiment, bullish %, bearish %, volume |
| `report.txt` | Full text summary — top bullish/bearish headlines, daily breakdown, stats |
| `scraper.log` | Debug log if something goes wrong |
| `cache/` | Cached headlines so you don't re-scrape the same day |

### Scored Headlines CSV — Column Guide

| Column | What it means |
|--------|--------------|
| `dict_score` | Dictionary method score (-1 to +1) |
| `rulebased_score` | Rule-based method score (-1 to +1) |
| `tfidf_score` | ML method score (-1 to +1) |
| `vader_score` | VADER score (only if nltk installed) |
| `consensus_score` | **Average of all methods — this is the main number** |
| `consensus_label` | **bullish / neutral / bearish — this is the main label** |
| `agreement` | "3/3" = all agree, "2/3" = one disagrees |

### Daily Sentiment CSV — Column Guide

This is the file you'd eventually feed into XGBoost/LSTM as features:

| Column | What it means | Why it matters for modeling |
|--------|--------------|---------------------------|
| `mean_sentiment` | Average score that day | Main sentiment feature |
| `bullish_pct` | % of headlines that were bullish | Market optimism level |
| `bearish_pct` | % that were bearish | Market fear level |
| `headline_count` | Number of headlines that day | High count = big news event |
| `sentiment_range` | Max score minus min score | High = market disagreement |
| `sentiment_ma3` | 3-day moving average | Smoothed trend |
| `sentiment_delta` | Day-over-day change | Is sentiment improving or worsening? |

---

## Understanding the Charts

### 01 — Score Distributions

Histograms showing how each method distributes its scores. Green bars = bullish scores, red bars = bearish. If all 3 methods show more red than green, the bearish signal is strong. If one method disagrees with the others, it might not be calibrated well for your data.

### 02 — Headline Heatmap

The 15 most bullish + 15 most bearish headlines scored across all methods. Each row is a headline, each column is a method. Look for:
- **All-green rows** = high-confidence bullish headline
- **All-red rows** = high-confidence bearish headline
- **Mixed-color rows** = ambiguous, the methods disagree

### 03 — Daily Timeline

Three stacked panels:
- **Top:** Bar chart of daily sentiment (green bar = bullish day, red = bearish). The dashed line is the 3-day moving average showing the trend.
- **Middle:** Stacked area showing bullish/neutral/bearish proportions over time. When the red area grows, bearish headlines are dominating.
- **Bottom:** Number of headlines per day. Spikes usually mean something big happened (OPEC meeting, geopolitical event, inventory surprise).

### 04 — Consensus & Agreement

- **Pie chart:** Overall sentiment breakdown — what % of all headlines are bullish/neutral/bearish.
- **Bar chart:** How often the methods agree. Lots of "3/3" = reliable classifiers. Lots of "1/3" = noisy signal.

### 05 — Source Breakdown

- **Left:** Which news sources contributed the most headlines.
- **Right:** Average sentiment per source. If Reuters averages -0.15 but OilPrice.com averages +0.05, they're framing the same events differently. Useful for spotting media bias in your dataset.

---

## Re-running & Cache

The scraper caches headlines by date. If you run it twice on the same day, it loads from cache instantly (no network requests). To force a fresh scrape:

```bash
rm -rf news_output/cache/
python news_scraper.py
```
