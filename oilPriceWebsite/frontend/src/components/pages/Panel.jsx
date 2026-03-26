import React, { useState, useEffect } from 'react';
import {
  TrendingUp, TrendingDown, Activity, ShieldAlert,
  Globe, Newspaper, Zap, Terminal, RefreshCw, Wifi, WifiOff,
  HelpCircle, ArrowUp, ArrowDown, Minus, Clock, BarChart3
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, ReferenceLine, Cell, PieChart, Pie
} from 'recharts';

const API_URL = 'http://localhost:8081/api';
const POLL_INTERVAL = 30000;

// ── Tooltip component for explanations ──
const InfoTip = ({ text }) => {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-block">
      <HelpCircle
        size={11}
        className="text-slate-600 hover:text-blue-400 cursor-help inline ml-1 transition-colors"
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
      />
      {show && (
        <span className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-[11px] text-slate-300 leading-relaxed shadow-xl pointer-events-none">
          {text}
          <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-800"></span>
        </span>
      )}
    </span>
  );
};

const Panel = () => {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [logs, setLogs] = useState([]);
  const [allHeadlines, setAllHeadlines] = useState([]);
  const [predictions, setPredictions] = useState(null);
  const [predicting, setPredicting] = useState(false);
  const [newsFilter, setNewsFilter] = useState('all');
  const [regime, setRegime] = useState(null);
  const [regimeRunning, setRegimeRunning] = useState(false);

  const fetchData = async () => {
    try {
      const [stateRes, headlinesRes, predRes, regimeRes] = await Promise.all([
        fetch(`${API_URL}/state`),
        fetch(`${API_URL}/headlines`).catch(() => null),
        fetch(`${API_URL}/predictions`).catch(() => null),
        fetch(`${API_URL}/regime`).catch(() => null),
      ]);
      if (!stateRes.ok) throw new Error(`HTTP ${stateRes.status}`);
      const result = await stateRes.json();
      setData(result); setError(null); setLastUpdate(new Date());
      if (headlinesRes?.ok) {
        const hData = await headlinesRes.json();
        if (hData.headlines?.length > 0) setAllHeadlines(hData.headlines);
      }
      if (predRes?.ok) {
        const pData = await predRes.json();
        if (pData.ensemble?.forecast) setPredictions(pData);
      }
      if (regimeRes?.ok) {
        const rData = await regimeRes.json();
        if (rData.current_regime) setRegime(rData);
      }
      addLog('INFO', `Refreshed. Risk: ${result.risk_score?.toFixed(3) || 'N/A'}`);
    } catch (err) { setError(err.message); addLog('ERROR', err.message); }
  };

  const addLog = (level, message) => {
    setLogs(prev => [{ time: new Date().toLocaleTimeString(), level, message }, ...prev].slice(0, 25));
  };

  useEffect(() => { fetchData(); const i = setInterval(fetchData, POLL_INTERVAL); return () => clearInterval(i); }, []);

  // ── Derived values ──
  const d = data || {};
  const riskScore = d.risk_score ?? 0;
  const riskLabel = d.risk_label ?? 'Connecting...';
  const livePrice = d.live_price;
  const csvPrice = d.price;
  const price = livePrice || csvPrice || '--';
  const r1d = d.return_1d ?? 0;
  const r5d = d.return_5d ?? 0;
  const r20d = d.return_20d ?? 0;
  const rsi = d.rsi; const vol = d.volatility; const vix = d.vix;
  const macd = d.macd; const trend = d.trend; const spread = d.brent_wti_spread;
  const newsScore = d.news_score;
  const bull = d.news_bullish_pct ?? 0;
  const bear = d.news_bearish_pct ?? 0;
  const neut = d.news_neutral_pct ?? 0;
  const components = d.components ?? [];
  const connected = d.monitor_running ?? false;
  const newsLive = d.news_live_running ?? false;

  // ── Filtered headlines ──
  const filteredHeadlines = newsFilter === 'all' ? allHeadlines
    : allHeadlines.filter(h => h.label === newsFilter);

  // ── Sentiment pie data ──
  const sentimentPie = [
    { name: 'Bullish', value: bull, fill: '#10b981' },
    { name: 'Neutral', value: neut, fill: '#475569' },
    { name: 'Bearish', value: bear, fill: '#ef4444' },
  ].filter(s => s.value > 0);

  // ── Signal bar chart data ──
  const signalData = components.map(([name, score, weight]) => ({
    name: name.replace(/\(.*\)/, '').trim(),
    score: score,
    weight: weight,
    fill: score > 0.05 ? '#10b981' : score < -0.05 ? '#ef4444' : '#64748b'
  }));

  // ── Forecast chart data ──
  const forecastChartData = predictions?.forecast_dates?.map((date, i) => ({
    date: date.slice(5),
    price: predictions.ensemble.forecast[i],
  })) || [];
  if (predictions?.current_price && forecastChartData.length > 0) {
    forecastChartData.unshift({ date: 'Now', price: predictions.current_price });
  }

  // ── Risk color helpers ──
  const riskColor = riskScore > 0.15 ? '#10b981' : riskScore > -0.15 ? '#f59e0b' : '#ef4444';
  const riskBg = riskScore > 0.15 ? 'bg-emerald-500/8' : riskScore > -0.15 ? 'bg-amber-500/8' : 'bg-rose-500/8';

  return (
    <div className="min-h-screen bg-[#0a0e1a] text-slate-200 p-4 md:p-6" style={{ fontFamily: "'DM Sans', 'Segoe UI', sans-serif" }}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />

      {/* ── HEADER ── */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-3">
        <div>
          <h1 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
            Oil Risk Terminal
            <span className="text-slate-500 font-normal text-sm">Citibank Challenge</span>
          </h1>
          <p className="text-[11px] text-slate-500 mt-0.5">
            Live oil market risk analysis powered by news sentiment + technical indicators
          </p>
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          <span className={`px-2 py-1 rounded ${connected ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'}`}>
            {connected ? '● Connected' : '● Offline'}
          </span>
          <span className={`px-2 py-1 rounded ${newsLive ? 'bg-blue-500/15 text-blue-400' : 'bg-slate-800 text-slate-500'}`}>
            {newsLive ? '● News Live' : '○ News Idle'}
          </span>
          <span className="text-slate-600">{lastUpdate?.toLocaleTimeString() || '--'}</span>
          <button onClick={fetchData} className="p-1 rounded hover:bg-white/5 transition">
            <RefreshCw size={13} className="text-slate-500" />
          </button>
        </div>
      </header>

      {error && (
        <div className="mb-4 bg-rose-500/10 border border-rose-500/20 text-rose-400 px-4 py-2 rounded-lg text-xs">
          Cannot connect to backend. Run <code className="bg-black/30 px-1 rounded">node server.js</code> in backend/.
        </div>
      )}

      {/* ═══════════════════════════════════════════════════
          ROW 1: THE ANSWER — Risk + Live Price + Forecast
          ═══════════════════════════════════════════════════ */}
      <div className="grid grid-cols-12 gap-4 mb-4">

        {/* Risk Gauge */}
        <div className={`col-span-12 md:col-span-4 ${riskBg} border border-white/5 rounded-2xl p-5`}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldAlert size={13} /> Risk Assessment
              <InfoTip text="This score combines trend direction, momentum (RSI), MACD, recent returns, VIX fear index, and news sentiment into a single number. Positive = less risk (bullish). Negative = more risk (bearish)." />
            </h2>
          </div>

          <div className="text-center">
            <div className="text-5xl font-bold tracking-tight" style={{ color: riskColor, fontFamily: "'JetBrains Mono', monospace" }}>
              {riskScore.toFixed(2)}
            </div>
            <p className="text-sm font-semibold mt-2" style={{ color: riskColor }}>
              {riskLabel.split('—')[0]?.trim()}
            </p>
            <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
              {riskLabel.includes('—') ? riskLabel.split('—')[1]?.trim() : 'Analyzing market conditions...'}
            </p>
          </div>

          {/* Signal bars */}
          {signalData.length > 0 && (
            <div className="mt-5">
              <p className="text-[10px] text-slate-600 uppercase mb-2">What's driving this</p>
              <ResponsiveContainer width="100%" height={signalData.length * 28 + 10}>
                <BarChart data={signalData} layout="vertical" margin={{ left: 0, right: 0, top: 0, bottom: 0 }}>
                  <XAxis type="number" domain={[-1, 1]} hide />
                  <YAxis type="category" dataKey="name" width={85} tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <ReferenceLine x={0} stroke="#334155" />
                  <Tooltip
                    content={({ payload }) => {
                      if (!payload?.[0]) return null;
                      const d = payload[0].payload;
                      return (
                        <div className="bg-slate-800 border border-slate-700 px-3 py-2 rounded-lg text-[11px]">
                          <p className="text-white font-medium">{d.name}</p>
                          <p className="text-slate-400">Score: {d.score > 0 ? '+' : ''}{d.score.toFixed(3)} (weight: {(d.weight * 100).toFixed(0)}%)</p>
                          <p className="text-slate-500">{d.score > 0.05 ? 'Pushing prices UP' : d.score < -0.05 ? 'Pushing prices DOWN' : 'Neutral effect'}</p>
                        </div>
                      );
                    }}
                  />
                  <Bar dataKey="score" radius={[2, 2, 2, 2]} barSize={12}>
                    {signalData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Live Price + Returns */}
        <div className="col-span-12 md:col-span-4 space-y-4">
          <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-5">
            <div className="flex items-center justify-between mb-1">
              <h2 className="text-xs text-slate-400 uppercase tracking-wider font-semibold flex items-center gap-1.5">
                <Zap size={13} /> WTI Crude Oil
                <InfoTip text="West Texas Intermediate — the main US oil price benchmark. This is the price of one barrel of oil on the futures market. When you hear 'oil prices' in the news, they usually mean WTI or Brent." />
              </h2>
              {livePrice && <span className="text-[10px] bg-emerald-500/15 text-emerald-400 px-1.5 py-0.5 rounded">LIVE</span>}
            </div>
            <div className="flex items-baseline gap-3 mt-2">
              <span className="text-4xl font-bold text-white" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                ${typeof price === 'number' ? price.toFixed(2) : price}
              </span>
              {livePrice && csvPrice && (
                <span className="text-[11px] text-slate-500">
                  {d.live_time && `at ${d.live_time}`}
                </span>
              )}
            </div>

            <div className="grid grid-cols-3 gap-3 mt-4">
              <ReturnCard label="Today" value={r1d} tip="Price change in the last trading session" />
              <ReturnCard label="This Week" value={r5d} tip="Price change over the last 5 trading days" />
              <ReturnCard label="This Month" value={r20d} tip="Price change over the last 20 trading days (~1 month)" />
            </div>
          </div>

          {/* Technicals compact */}
          <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-4">
            <h2 className="text-xs text-slate-400 uppercase tracking-wider font-semibold mb-3 flex items-center gap-1.5">
              <BarChart3 size={13} /> Technical Indicators
              <InfoTip text="These are mathematical patterns calculated from historical prices. Traders use them to guess where prices might go next. No indicator is perfect — they work best when several agree." />
            </h2>
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-[12px]">
              <TechItem label="Trend" value={trend === 'UP' ? '↑ Uptrend' : trend === 'DOWN' ? '↓ Downtrend' : '--'}
                color={trend === 'UP' ? 'text-emerald-400' : 'text-rose-400'}
                tip="50-day vs 200-day moving average. When short-term is above long-term, the trend is up (Golden Cross). Below = down (Death Cross)." />
              <TechItem label="RSI" value={rsi ?? '--'}
                color={rsi > 70 ? 'text-rose-400' : rsi < 30 ? 'text-emerald-400' : 'text-slate-300'}
                tip="Relative Strength Index (0-100). Think of it as a speedometer: above 70 = going too fast, might slow down. Below 30 = oversold, might bounce. 30-70 = normal." />
              <TechItem label="VIX" value={vix ? `${vix}` : '--'}
                color={vix > 30 ? 'text-rose-400' : vix > 20 ? 'text-amber-400' : 'text-emerald-400'}
                tip="The 'Fear Index'. Measures how nervous the stock market is. Below 20 = calm. 20-30 = worried. Above 30 = panicking. High VIX usually means oil gets volatile too." />
              <TechItem label="MACD" value={macd != null ? (macd > 0 ? '↑ Bullish' : '↓ Bearish') : '--'}
                color={macd > 0 ? 'text-emerald-400' : 'text-rose-400'}
                tip="Moving Average Convergence Divergence. A trend-following indicator. When it's positive, momentum is upward. Negative = downward momentum." />
              <TechItem label="Volatility" value={vol ? `${vol}%` : '--'}
                color={vol > 40 ? 'text-rose-400' : vol > 25 ? 'text-amber-400' : 'text-emerald-400'}
                tip="How wild the price swings are, annualized. Below 20% = calm. 20-35% = normal. Above 40% = very choppy, expect big daily moves." />
              <TechItem label="Brent-WTI" value={spread != null ? `$${spread}` : '--'}
                color="text-slate-300"
                tip="The gap between international oil (Brent) and US oil (WTI). A wide spread means global supply is tighter than US supply." />
            </div>
          </div>
        </div>

        {/* Forecast */}
        <div className="col-span-12 md:col-span-4 bg-white/[0.03] border border-white/5 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs text-slate-400 uppercase tracking-wider font-semibold flex items-center gap-1.5">
              <TrendingUp size={13} /> 5-Day Price Forecast
              <InfoTip text="Three models predict where oil will be in 5 trading days: ARIMA (trend patterns), XGBoost (machine learning on 80+ indicators), and a Trend Baseline. The ensemble averages all three." />
            </h2>
            <button
              onClick={async () => {
                setPredicting(true); addLog('SYSTEM', 'Running prediction models...');
                try { await fetch(`${API_URL}/predict`, { method: 'POST' }); setTimeout(fetchData, 12000); }
                catch (e) { addLog('ERROR', e.message); }
                finally { setTimeout(() => setPredicting(false), 15000); }
              }}
              className="text-[10px] bg-blue-500/20 text-blue-400 px-2.5 py-1 rounded-md hover:bg-blue-500/30 transition font-medium"
              disabled={predicting}
            >
              {predicting ? '⏳ Running...' : '▶ Run Models'}
            </button>
          </div>

          {predictions ? (
            <>
              {/* Direction call */}
              <div className={`text-center p-3 rounded-xl mb-4 ${
                predictions.ensemble.direction === 'UP' ? 'bg-emerald-500/10 border border-emerald-500/15' :
                predictions.ensemble.direction === 'DOWN' ? 'bg-rose-500/10 border border-rose-500/15' :
                'bg-slate-800/50 border border-slate-700/50'
              }`}>
                <div className="flex items-center justify-center gap-2">
                  {predictions.ensemble.direction === 'UP' ? <ArrowUp className="text-emerald-400" size={20} /> :
                   predictions.ensemble.direction === 'DOWN' ? <ArrowDown className="text-rose-400" size={20} /> :
                   <Minus className="text-slate-400" size={20} />}
                  <span className={`text-2xl font-bold ${
                    predictions.ensemble.direction === 'UP' ? 'text-emerald-400' :
                    predictions.ensemble.direction === 'DOWN' ? 'text-rose-400' : 'text-slate-400'
                  }`} style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                    ${predictions.ensemble.end_price}
                  </span>
                  <span className={`text-sm ${predictions.ensemble.change_pct > 0 ? 'text-emerald-400' : predictions.ensemble.change_pct < 0 ? 'text-rose-400' : 'text-slate-400'}`}>
                    {predictions.ensemble.change_pct > 0 ? '+' : ''}{predictions.ensemble.change_pct}%
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 mt-1">{predictions.ensemble.confidence}</p>
              </div>

              {/* Forecast mini chart */}
              {forecastChartData.length > 0 && (
                <ResponsiveContainer width="100%" height={100}>
                  <AreaChart data={forecastChartData} margin={{ top: 5, right: 5, bottom: 0, left: 5 }}>
                    <defs>
                      <linearGradient id="fcGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={predictions.ensemble.change_pct >= 0 ? '#10b981' : '#ef4444'} stopOpacity={0.3} />
                        <stop offset="100%" stopColor={predictions.ensemble.change_pct >= 0 ? '#10b981' : '#ef4444'} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="date" tick={{ fontSize: 9, fill: '#64748b' }} axisLine={false} tickLine={false} />
                    <YAxis domain={['dataMin - 1', 'dataMax + 1']} hide />
                    <Tooltip content={({ payload }) => payload?.[0] ? (
                      <div className="bg-slate-800 border border-slate-700 px-2 py-1 rounded text-[11px] text-white">
                        ${payload[0].value?.toFixed(2)}
                      </div>
                    ) : null} />
                    <Area type="monotone" dataKey="price" stroke={predictions.ensemble.change_pct >= 0 ? '#10b981' : '#ef4444'} fill="url(#fcGrad)" strokeWidth={2} dot={{ r: 3, fill: '#0a0e1a', strokeWidth: 2 }} />
                  </AreaChart>
                </ResponsiveContainer>
              )}

              {/* Model breakdown */}
              <div className="mt-3 space-y-1.5">
                <p className="text-[10px] text-slate-600 uppercase">Individual Models</p>
                {predictions.models?.filter(m => m.status === 'ok').map((m, i) => (
                  <div key={i} className="flex items-center justify-between text-[11px] py-1 border-b border-white/3">
                    <span className="text-slate-400">{m.model}</span>
                    <span className="text-white font-medium" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      ${m.forecast?.[m.forecast.length - 1]?.toFixed(2)}
                    </span>
                    {m.metrics?.direction_accuracy != null && (
                      <span className="text-[10px] text-slate-600">{m.metrics.direction_accuracy}% accuracy</span>
                    )}
                  </div>
                ))}
              </div>

              {/* Top factors */}
              {predictions.models?.find(m => m.model === 'XGBoost')?.feature_importance && (
                <div className="mt-3">
                  <p className="text-[10px] text-slate-600 uppercase mb-1.5">
                    Top Price Drivers
                    <InfoTip text="These are the factors that XGBoost found most important for predicting tomorrow's oil price movement. The wider the bar, the more influence that factor has." />
                  </p>
                  {predictions.models.find(m => m.model === 'XGBoost').feature_importance.slice(0, 5).map((f, i) => (
                    <div key={i} className="flex items-center gap-2 mb-1">
                      <div className="flex-1 bg-slate-800/50 rounded-full h-1.5 overflow-hidden">
                        <div className="bg-blue-500/70 h-full rounded-full transition-all" style={{ width: `${Math.min(f.importance * 300, 100)}%` }} />
                      </div>
                      <span className="text-[10px] text-slate-500 w-28 text-right truncate">{f.feature.replace(/_/g, ' ')}</span>
                    </div>
                  ))}
                </div>
              )}

              <p className="text-[9px] text-slate-700 mt-3 text-center">
                Last run: {predictions.timestamp?.slice(11, 19)}
              </p>
            </>
          ) : (
            <div className="text-center py-10 text-slate-600 text-xs">
              <TrendingUp size={28} className="mx-auto mb-2 opacity-20" />
              Click "Run Models" to generate a 5-day forecast
              <p className="text-[10px] text-slate-700 mt-1">Uses ARIMA + XGBoost + Trend analysis</p>
            </div>
          )}
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════
          ROW 2: News Feed + Sentiment Chart + System Log
          ═══════════════════════════════════════════════════ */}
      <div className="grid grid-cols-12 gap-4">

        {/* News Feed */}
        <div className="col-span-12 md:col-span-6 bg-white/[0.03] border border-white/5 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs text-slate-400 uppercase tracking-wider font-semibold flex items-center gap-1.5">
              <Newspaper size={13} /> Live News Feed
              <InfoTip text="Headlines scraped from Google News, Reuters, and OilPrice.com every 10 minutes. Each headline is scored from -1 (very bearish) to +1 (very bullish) using 3 different classification methods." />
            </h2>
            <span className="text-[10px] text-slate-600">{allHeadlines.length} headlines</span>
          </div>

          {/* Filter tabs */}
          <div className="flex gap-1 mb-3">
            {[
              { key: 'all', label: 'All', color: 'text-slate-400' },
              { key: 'bullish', label: `🟢 Bull (${allHeadlines.filter(h => h.label === 'bullish').length})`, color: 'text-emerald-400' },
              { key: 'bearish', label: `🔴 Bear (${allHeadlines.filter(h => h.label === 'bearish').length})`, color: 'text-rose-400' },
              { key: 'neutral', label: `Neutral`, color: 'text-slate-500' },
            ].map(f => (
              <button key={f.key} onClick={() => setNewsFilter(f.key)}
                className={`text-[10px] px-2 py-1 rounded-md transition ${newsFilter === f.key ? 'bg-white/10 text-white' : 'text-slate-500 hover:text-slate-300'}`}>
                {f.label}
              </button>
            ))}
          </div>

          {/* Headlines */}
          <div className="max-h-[420px] overflow-y-auto space-y-1.5 pr-1" style={{ scrollbarWidth: 'thin', scrollbarColor: '#1e293b transparent' }}>
            {filteredHeadlines.length > 0 ? filteredHeadlines.map((h, i) => (
              <div key={i} className="flex items-start gap-2 py-2 px-2 rounded-lg hover:bg-white/[0.03] transition group">
                <span className={`mt-1 w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                  h.label === 'bullish' ? 'bg-emerald-500' : h.label === 'bearish' ? 'bg-rose-500' : 'bg-slate-600'
                }`} />
                <div className="flex-1 min-w-0">
                  <p className="text-[12px] text-slate-300 leading-snug">{h.headline}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[10px] text-slate-600">{h.source}</span>
                    {h.datetime && <span className="text-[10px] text-slate-700">{h.datetime?.slice(0, 10)}</span>}
                    <span className={`text-[10px] font-mono ${h.score > 0.05 ? 'text-emerald-500' : h.score < -0.05 ? 'text-rose-500' : 'text-slate-600'}`}>
                      {h.score > 0 ? '+' : ''}{h.score?.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            )) : (
              <div className="text-center py-8 text-slate-600 text-xs">
                {allHeadlines.length === 0 ? 'Waiting for first news cycle...' : 'No headlines match this filter'}
              </div>
            )}
          </div>
        </div>

        {/* Sentiment + Log */}
        <div className="col-span-12 md:col-span-6 space-y-4">

          {/* Sentiment Overview */}
          <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-5">
            <h2 className="text-xs text-slate-400 uppercase tracking-wider font-semibold mb-3 flex items-center gap-1.5">
              <Globe size={13} /> News Sentiment
              <InfoTip text="This shows the overall mood of oil news. Bullish = news suggests prices will rise (supply cuts, geopolitical tensions). Bearish = news suggests prices will fall (oversupply, weak demand). The score averages all headline classifications." />
            </h2>

            <div className="flex items-center gap-6">
              {/* Pie chart */}
              <div className="w-24 h-24 flex-shrink-0">
                {sentimentPie.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={sentimentPie} cx="50%" cy="50%" innerRadius={25} outerRadius={40} dataKey="value" strokeWidth={0}>
                        {sentimentPie.map((s, i) => <Cell key={i} fill={s.fill} />)}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                ) : <div className="w-full h-full bg-slate-800/30 rounded-full" />}
              </div>

              <div className="flex-1">
                {newsScore != null && (
                  <div className="mb-2">
                    <span className={`text-xl font-bold ${newsScore > 0.05 ? 'text-emerald-400' : newsScore < -0.05 ? 'text-rose-400' : 'text-slate-400'}`}
                      style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {newsScore > 0 ? '+' : ''}{newsScore.toFixed(3)}
                    </span>
                    <span className="text-[11px] text-slate-500 ml-2">sentiment score</span>
                  </div>
                )}
                <div className="space-y-1 text-[11px]">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    <span className="text-slate-400">Bullish</span>
                    <span className="text-white ml-auto font-medium">{(bull * 100).toFixed(0)}%</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-slate-600" />
                    <span className="text-slate-400">Neutral</span>
                    <span className="text-white ml-auto font-medium">{(neut * 100).toFixed(0)}%</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-rose-500" />
                    <span className="text-slate-400">Bearish</span>
                    <span className="text-white ml-auto font-medium">{(bear * 100).toFixed(0)}%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Market Regime */}
          <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xs text-slate-400 uppercase tracking-wider font-semibold flex items-center gap-1.5">
                <Activity size={13} /> Market Regime
                <InfoTip text="The oil market has different 'states': bull (prices rising steadily), bear (prices declining), and crisis (extreme volatility, crashes). The key insight is that the TOP risk factors are DIFFERENT in each state. What drives oil in calm markets is NOT the same as what drives it during a crisis." />
              </h2>
              <button
                onClick={async () => {
                  setRegimeRunning(true);
                  addLog('SYSTEM', 'Running regime detection...');
                  try {
                    await fetch(`${API_URL}/regime/run`, { method: 'POST' });
                    setTimeout(fetchData, 15000);
                  } catch (e) { addLog('ERROR', e.message); }
                  finally { setTimeout(() => setRegimeRunning(false), 20000); }
                }}
                className="text-[10px] bg-purple-500/20 text-purple-400 px-2.5 py-1 rounded-md hover:bg-purple-500/30 transition font-medium"
                disabled={regimeRunning}
              >
                {regimeRunning ? '⏳ Running...' : '▶ Detect Regimes'}
              </button>
            </div>

            {regime ? (
              <div>
                {/* Current regime badge */}
                <div className={`text-center p-3 rounded-xl mb-3 ${
                  regime.current_regime === 'bull' ? 'bg-emerald-500/10 border border-emerald-500/15' :
                  regime.current_regime === 'crisis' ? 'bg-rose-500/10 border border-rose-500/15' :
                  'bg-amber-500/10 border border-amber-500/15'
                }`}>
                  <span className={`text-lg font-bold ${
                    regime.current_regime === 'bull' ? 'text-emerald-400' :
                    regime.current_regime === 'crisis' ? 'text-rose-400' : 'text-amber-400'
                  }`}>
                    {regime.current_regime === 'bull' ? '📈' : regime.current_regime === 'crisis' ? '🚨' : '📉'}
                    {' '}{regime.current_regime?.toUpperCase()} MARKET
                  </span>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Detected using {regime.method} • {regime.timestamp?.slice(0, 10)}
                  </p>
                </div>

                {/* Regime distribution */}
                {regime.regime_counts && (
                  <div className="space-y-1.5 mb-3">
                    <p className="text-[10px] text-slate-600 uppercase">Historical Distribution</p>
                    {Object.entries(regime.regime_counts).map(([name, count]) => {
                      const total = Object.values(regime.regime_counts).reduce((a, b) => a + b, 0);
                      const pct = (count / total * 100).toFixed(0);
                      const color = name === 'bull' ? 'bg-emerald-500' : name === 'crisis' ? 'bg-rose-500' : 'bg-amber-500';
                      return (
                        <div key={name} className="flex items-center gap-2 text-[11px]">
                          <span className="text-slate-400 w-12">{name}</span>
                          <div className="flex-1 bg-slate-800/50 rounded-full h-2 overflow-hidden">
                            <div className={`${color} h-full rounded-full`} style={{ width: `${pct}%` }} />
                          </div>
                          <span className="text-slate-500 w-14 text-right">{pct}% ({count}d)</span>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Top factors per regime */}
                {regime.top_factors_by_regime && Object.keys(regime.top_factors_by_regime).length > 0 && (
                  <div>
                    <p className="text-[10px] text-slate-600 uppercase mb-2">
                      Top Factors Change by Regime
                      <InfoTip text="This is the key competition insight. XGBoost was trained separately for bull and bear markets. The #1 factor in a bull market is NOT the same as in a bear market. This shows the risk factors are dynamic, not static." />
                    </p>
                    {Object.entries(regime.top_factors_by_regime).map(([regimeName, factors]) => (
                      <div key={regimeName} className="mb-2">
                        <p className={`text-[10px] font-semibold mb-1 ${
                          regimeName === 'bull' ? 'text-emerald-400' :
                          regimeName === 'crisis' ? 'text-rose-400' : 'text-amber-400'
                        }`}>
                          {regimeName.toUpperCase()}:
                        </p>
                        <div className="space-y-0.5">
                          {factors.slice(0, 3).map((f, i) => (
                            <div key={i} className="flex items-center gap-1.5 text-[10px]">
                              <span className="text-slate-500 w-4">#{i+1}</span>
                              <div className="flex-1 bg-slate-800/50 rounded-full h-1">
                                <div className={`h-full rounded-full ${
                                  regimeName === 'bull' ? 'bg-emerald-500/60' :
                                  regimeName === 'crisis' ? 'bg-rose-500/60' : 'bg-amber-500/60'
                                }`} style={{ width: `${Math.min(f.importance * 400, 100)}%` }} />
                              </div>
                              <span className="text-slate-500 truncate" style={{ maxWidth: '100px' }}>
                                {f.feature.replace(/_/g, ' ')}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-6 text-slate-600 text-xs">
                <Activity size={24} className="mx-auto mb-2 opacity-20" />
                Click "Detect Regimes" to analyze bull/bear/crisis periods
                <p className="text-[10px] text-slate-700 mt-1">Uses K-Means clustering + XGBoost importance</p>
              </div>
            )}
          </div>

          {/* System Log */}
          <div className="bg-black/40 border border-white/5 rounded-2xl p-4 h-[280px] overflow-hidden relative" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            <div className="flex items-center gap-2 mb-2 pb-2 border-b border-white/5">
              <Terminal size={11} className="text-slate-600" />
              <span className="text-[10px] text-slate-600 uppercase">System Log</span>
            </div>
            <div className="space-y-0.5 text-[10px] overflow-y-auto h-[220px]" style={{ scrollbarWidth: 'thin', scrollbarColor: '#1e293b transparent' }}>
              {logs.map((log, i) => (
                <p key={i} className={
                  log.level === 'SYSTEM' ? 'text-blue-400' :
                  log.level === 'ERROR' ? 'text-rose-400' :
                  log.level === 'PREDICT' ? 'text-purple-400' :
                  log.level === 'DATA' ? 'text-emerald-400' : 'text-slate-500'
                }>
                  <span className="text-slate-700">{log.time}</span> [{log.level}] {log.message}
                </p>
              ))}
              <p className="text-slate-700 animate-pulse">▊</p>
            </div>
            <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-black/80 to-transparent pointer-events-none rounded-b-2xl" />
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="mt-4 pt-3 border-t border-white/5 flex justify-between text-[10px] text-slate-700">
        <span>Auto-refreshes every {POLL_INTERVAL/1000}s • News polls every 10 min</span>
        <span>Citibank Oil Price Risk Factor Challenge • Arturo</span>
      </footer>
    </div>
  );
};

// ── Small Components ──

const ReturnCard = ({ label, value, tip }) => (
  <div className="bg-black/20 rounded-lg p-2 text-center">
    <p className="text-[10px] text-slate-500">{label}<InfoTip text={tip} /></p>
    <p className={`text-sm font-bold mt-0.5 ${value > 0 ? 'text-emerald-400' : value < 0 ? 'text-rose-400' : 'text-slate-400'}`}
       style={{ fontFamily: "'JetBrains Mono', monospace" }}>
      {value > 0 ? '+' : ''}{value?.toFixed(2) ?? '--'}%
    </p>
  </div>
);

const TechItem = ({ label, value, color, tip }) => (
  <div className="flex justify-between items-center py-1 border-b border-white/3">
    <span className="text-[11px] text-slate-500">{label}<InfoTip text={tip} /></span>
    <span className={`text-[11px] font-medium ${color}`}>{value}</span>
  </div>
);

export default Panel;