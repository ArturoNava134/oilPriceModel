"""
Shared path configuration for all Python scripts.
Import this at the top of any script that reads or writes data files.

When run from the Node backend, DATA_ROOT is set via environment variable.
When run standalone (python script.py), it defaults to a 'data' folder
in the current directory.

Usage:
    from config import PATHS
    df.to_csv(PATHS.price_featured)
"""

import os
from pathlib import Path

# DATA_ROOT is set by server.js when spawning Python processes.
# If not set (running standalone), default to ./data relative to this file.
_root = Path(os.environ.get('DATA_ROOT', Path(__file__).parent.parent / 'data'))

class PATHS:
    """All data file paths, centralized."""

    # Root
    data_root = _root

    # Price data
    price_dir           = _root / 'price'
    price_raw           = _root / 'price' / 'data_yfinance_raw.csv'
    price_featured      = _root / 'price' / 'data_yfinance_featured.csv'
    fred                = _root / 'price' / 'data_fred.csv'

    # News (one-shot scraper)
    news_dir            = _root / 'news'
    news_plots          = _root / 'news' / 'plots'
    news_cache          = _root / 'news' / 'cache'
    news_scored         = _root / 'news' / 'scored_headlines.csv'
    news_daily          = _root / 'news' / 'daily_sentiment.csv'
    news_report         = _root / 'news' / 'report.txt'
    news_log            = _root / 'news' / 'scraper.log'

    # News live
    news_live_dir       = _root / 'news_live'
    live_sentiment      = _root / 'news_live' / 'live_sentiment.json'
    live_headlines_log  = _root / 'news_live' / 'headlines_log.csv'
    live_history        = _root / 'news_live' / 'sentiment_history.csv'
    live_log            = _root / 'news_live' / 'listener.log'

    # Monitor
    monitor_dir         = _root / 'monitor'
    monitor_state       = _root / 'monitor' / 'current_state.json'
    monitor_history     = _root / 'monitor' / 'risk_history.csv'
    monitor_log         = _root / 'monitor' / 'monitor.log'

    # Analysis (from main.py)
    analysis_dir        = _root / 'analysis'
    analysis_plots      = _root / 'analysis' / 'plots'
    analysis_report     = _root / 'analysis' / 'final_report.txt'
    analysis_summary    = _root / 'analysis' / 'combined_summary.csv'

    # Regime detection
    regime_dir          = _root / 'regime'
    regime_labels       = _root / 'regime' / 'regime_labels.csv'
    regime_importance   = _root / 'regime' / 'regime_factor_importance.csv'
    regime_report       = _root / 'regime' / 'report.txt'
    regime_plots        = _root / 'regime' / 'plots'

    @classmethod
    def ensure_dirs(cls):
        """Create all output directories."""
        dirs = [
            cls.price_dir, cls.news_dir, cls.news_plots, cls.news_cache,
            cls.news_live_dir, cls.monitor_dir, cls.analysis_dir,
            cls.analysis_plots, cls.regime_dir, cls.regime_plots,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

# Auto-create on import
PATHS.ensure_dirs()