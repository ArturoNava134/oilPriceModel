const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const app = express();
app.use(cors());
app.use(express.json());

//db
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const mysql = require('mysql2/promise');
require('dotenv').config();


const JWT_SECRET = process.env.JWT_SECRET || 'oil-risk-terminal-secret-2026';

const db = mysql.createPool({
  host:     process.env.DB_HOST || 'localhost',
  user:     process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || '',
  database: process.env.DB_NAME || 'oil_risk_terminal',
  waitForConnections: true,
  connectionLimit: 5,
});


(async () => {
  try {
    const conn = await db.getConnection();
    console.log('  ✓ MySQL connected');
    conn.release();
  } catch (e) {
    console.error('  ✗ MySQL connection failed:', e.message);
    console.error('    Check your .env DB_HOST/DB_USER/DB_PASSWORD/DB_NAME');
  }
})();

// ── Paths ────────────────────────────────────────────
// Everything is relative to backend/
const PYTHON_DIR = path.join(__dirname, 'python');
const DATA_DIR   = path.join(__dirname, 'data');
const ENV_FILE   = path.join(__dirname, '.env');

const PATHS = {
  monitorState:  path.join(DATA_DIR, 'monitor', 'current_state.json'),
  liveSentiment: path.join(DATA_DIR, 'news_live', 'live_sentiment.json'),
  scoredCSV:     path.join(DATA_DIR, 'news', 'scored_headlines.csv'),
  dailyCSV:      path.join(DATA_DIR, 'news', 'daily_sentiment.csv'),
  priceCSV:      path.join(DATA_DIR, 'price', 'data_yfinance_featured.csv'),
  priceRawCSV:   path.join(DATA_DIR, 'price', 'data_yfinance_raw.csv'),
  fredCSV:       path.join(DATA_DIR, 'price', 'data_fred.csv'),
};

// Ensure data directories exist
const dataDirs = ['price', 'news', 'news/plots', 'news/cache', 'news_live', 'monitor', 'analysis', 'analysis/plots', 'predictions'];
dataDirs.forEach(d => {
  const dir = path.join(DATA_DIR, d);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
});

// ── Python Process Manager ───────────────────────────
let monitorProcess = null;
let monitorLogs = [];
const MAX_LOGS = 100;

function addLog(level, message) {
  monitorLogs.unshift({
    time: new Date().toISOString(),
    level,
    message: message.trim()
  });
  if (monitorLogs.length > MAX_LOGS) monitorLogs.pop();
}

function startMonitor() {
  if (monitorProcess) {
    addLog('WARN', 'Monitor already running');
    return;
  }

  addLog('SYSTEM', 'Starting Python monitor...');

  monitorProcess = spawn('python', [
    path.join(PYTHON_DIR, 'monitor.py'),
    '--interval', '10',
    '--window', '120'
  ], {
    cwd: PYTHON_DIR,
    env: {
      ...process.env,
      // Pass data directory so Python scripts know where to write
      DATA_ROOT: DATA_DIR,
    },
    stdio: ['pipe', 'pipe', 'pipe']
  });

  monitorProcess.stdout.on('data', (data) => {
    const lines = data.toString().split('\n').filter(l => l.trim());
    lines.forEach(line => {
      addLog('INFO', line);
      console.log(`  [monitor] ${line}`);
    });
  });

  monitorProcess.stderr.on('data', (data) => {
    const lines = data.toString().split('\n').filter(l => l.trim());
    lines.forEach(line => {
      addLog('WARN', line);
      console.log(`  [monitor:err] ${line}`);
    });
  });

  monitorProcess.on('close', (code) => {
    addLog('SYSTEM', `Monitor exited with code ${code}`);
    console.log(`  [monitor] Process exited (code ${code})`);
    monitorProcess = null;
  });

  monitorProcess.on('error', (err) => {
    addLog('ERROR', `Failed to start monitor: ${err.message}`);
    console.error(`  [monitor] Error: ${err.message}`);
    monitorProcess = null;
  });
}

function stopMonitor() {
  if (monitorProcess) {
    addLog('SYSTEM', 'Stopping monitor...');
    monitorProcess.kill('SIGINT');
    monitorProcess = null;
  }
}

// ── Helpers ──────────────────────────────────────────

function readJSON(filePath) {
  try {
    if (fs.existsSync(filePath)) {
      return JSON.parse(fs.readFileSync(filePath, 'utf8'));
    }
  } catch (e) {
    console.error(`Error reading ${filePath}:`, e.message);
  }
  return null;
}

function readCSVTail(filePath, n = 50) {
  try {
    if (!fs.existsSync(filePath)) return [];
    const lines = fs.readFileSync(filePath, 'utf8').trim().split('\n');
    if (lines.length < 2) return [];

    const headers = lines[0].split(',');
    const dataLines = lines.slice(Math.max(1, lines.length - n));

    return dataLines.map(line => {
      const values = [];
      let current = '';
      let inQuotes = false;
      for (const char of line) {
        if (char === '"') { inQuotes = !inQuotes; }
        else if (char === ',' && !inQuotes) { values.push(current.trim()); current = ''; }
        else { current += char; }
      }
      values.push(current.trim());

      const row = {};
      headers.forEach((h, i) => {
        const val = values[i] || '';
        const num = parseFloat(val);
        row[h.trim()] = isNaN(num) || val === '' ? val : num;
      });
      return row;
    });
  } catch (e) {
    return [];
  }
}

function getLatestPrice() {
  try {
    if (!fs.existsSync(PATHS.priceCSV)) return {};
    const lines = fs.readFileSync(PATHS.priceCSV, 'utf8').trim().split('\n');
    if (lines.length < 2) return {};

    const headers = lines[0].split(',');
    const lastLine = lines[lines.length - 1];
    const values = lastLine.split(',');

    const row = {};
    headers.forEach((h, i) => {
      const val = values[i] || '';
      const num = parseFloat(val);
      row[h.trim()] = isNaN(num) || val === '' ? val : num;
    });

    const price = row['WTI_Crude_Close'];
    const result = {};

    if (price) {
      result.price = Math.round(price * 100) / 100;
      // First column is the date index
      const firstKey = headers[0].trim();
      result.price_date = row[firstKey] || 'unknown';
    }
    if (row['Return_1d'] !== undefined) result.return_1d = Math.round(row['Return_1d'] * 10000) / 100;
    if (row['Return_5d'] !== undefined) result.return_5d = Math.round(row['Return_5d'] * 10000) / 100;
    if (row['Return_20d'] !== undefined) result.return_20d = Math.round(row['Return_20d'] * 10000) / 100;
    if (row['RSI_14'] !== undefined) result.rsi = Math.round(row['RSI_14'] * 10) / 10;
    if (row['Volatility_20d'] !== undefined) result.volatility = Math.round(row['Volatility_20d'] * 10000) / 100;
    if (row['MACD_Histogram'] !== undefined) result.macd = Math.round(row['MACD_Histogram'] * 1000) / 1000;
    if (row['VIX_Close'] !== undefined) result.vix = Math.round(row['VIX_Close'] * 10) / 10;
    if (row['MA_50'] !== undefined && row['MA_200'] !== undefined) {
      result.trend = row['MA_50'] > row['MA_200'] ? 'UP' : 'DOWN';
    }
    if (row['Brent_WTI_Spread'] !== undefined) {
      result.brent_wti_spread = Math.round(row['Brent_WTI_Spread'] * 100) / 100;
    }

    return result;
  } catch (e) {
    return {};
  }
}

// ── API Routes ───────────────────────────────────────

// Register
app.post('/api/auth/register', async (req, res) => {
  const { name, email, password } = req.body;
 
  // Validation
  if (!name || !email || !password) {
    return res.status(400).json({ error: 'Name, email, and password are required' });
  }
  if (password.length < 6) {
    return res.status(400).json({ error: 'Password must be at least 6 characters' });
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ error: 'Invalid email format' });
  }
 
  try {
    // Check if email exists
    const [existing] = await db.execute(
      'SELECT id FROM users WHERE email = ?',
      [email.toLowerCase()]
    );
 
    if (existing.length > 0) {
      return res.status(409).json({ error: 'An account with this email already exists' });
    }
 
    // Hash password
    const salt = await bcrypt.genSalt(10);
    const hashedPassword = await bcrypt.hash(password, salt);
 
    // Insert user
    const [result] = await db.execute(
      'INSERT INTO users (name, email, password) VALUES (?, ?, ?)',
      [name, email.toLowerCase(), hashedPassword]
    );
 
    const userId = result.insertId;
 
    // Generate JWT
    const token = jwt.sign(
      { id: userId, email: email.toLowerCase(), name },
      JWT_SECRET,
      { expiresIn: '7d' }
    );
 
    console.log(`  [AUTH] Registered: ${email}`);
 
    res.status(201).json({
      token,
      user: { id: userId, name, email: email.toLowerCase() },
    });
 
  } catch (e) {
    console.error('  [AUTH] Register error:', e.message);
    res.status(500).json({ error: 'Server error during registration' });
  }
});
 
 
// Login
app.post('/api/auth/login', async (req, res) => {
  const { email, password } = req.body;
 
  if (!email || !password) {
    return res.status(400).json({ error: 'Email and password are required' });
  }
 
  try {
    const [rows] = await db.execute(
      'SELECT id, name, email, password FROM users WHERE email = ?',
      [email.toLowerCase()]
    );
 
    if (rows.length === 0) {
      return res.status(401).json({ error: 'Invalid email or password' });
    }
 
    const user = rows[0];
    const isMatch = await bcrypt.compare(password, user.password);
 
    if (!isMatch) {
      return res.status(401).json({ error: 'Invalid email or password' });
    }
 
    const token = jwt.sign(
      { id: user.id, email: user.email, name: user.name },
      JWT_SECRET,
      { expiresIn: '7d' }
    );
 
    console.log(`  [AUTH] Login: ${user.email}`);
 
    res.json({
      token,
      user: { id: user.id, name: user.name, email: user.email },
    });
 
  } catch (e) {
    console.error('  [AUTH] Login error:', e.message);
    res.status(500).json({ error: 'Server error during login' });
  }
});
 
 
function requireAuth(req, res, next) {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  try {
    const token = authHeader.split(' ')[1];
    req.user = jwt.verify(token, JWT_SECRET);
    next();
  } catch (e) {
    res.status(401).json({ error: 'Invalid or expired token' });
  }
}

// Verify token / get current user
app.get('/api/auth/me', async (req, res) => {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'No token provided' });
  }
 
  try {
    const token = authHeader.split(' ')[1];
    const decoded = jwt.verify(token, JWT_SECRET);
 
    // Optionally verify user still exists in DB
    const [rows] = await db.execute(
      'SELECT id, name, email FROM users WHERE id = ?',
      [decoded.id]
    );
 
    if (rows.length === 0) {
      return res.status(401).json({ error: 'User no longer exists' });
    }
 
    res.json({ user: rows[0] });
  } catch (e) {
    res.status(401).json({ error: 'Invalid or expired token' });
  }
});

// Main endpoint — everything the dashboard needs
app.get('/api/state', (req, res) => {
  const monitor = readJSON(PATHS.monitorState) || {};
  const live = readJSON(PATHS.liveSentiment) || {};
  const priceInfo = getLatestPrice();

  res.json({
    timestamp: new Date().toISOString(),
    risk_score: monitor.risk_score ?? 0,
    risk_label: monitor.risk_label ?? 'Starting up — waiting for first poll cycle...',
    components: monitor.components ?? [],
    ...priceInfo,
    live_price: monitor.live_price ?? null,
    live_time: monitor.live_time ?? null,
    news_score: live.status === 'active' ? live.mean_sentiment : null,
    news_bullish_pct: live.bullish_pct ?? 0,
    news_bearish_pct: live.bearish_pct ?? 0,
    news_neutral_pct: live.neutral_pct ?? 0,
    news_signal: live.signal ?? null,
    news_count: live.headlines_in_window ?? 0,
    news_latest: live.latest_3 ?? [],
    monitor_running: monitorProcess !== null,
    news_live_running: live.status === 'active',
  });
});

// Live news
app.get('/api/news', (req, res) => {
  const data = readJSON(PATHS.liveSentiment);
  if (data) return res.json(data);
  res.json({ status: 'inactive', message: 'Monitor starting up...' });
});

// Scored headlines
app.get('/api/headlines', (req, res) => {
  // First try the live all_headlines.json from the monitor
  const allHeadlinesPath = path.join(DATA_DIR, 'news_live', 'all_headlines.json');
  const liveData = readJSON(allHeadlinesPath);
  if (liveData && liveData.headlines && liveData.headlines.length > 0) {
    return res.json(liveData);
  }
  // Fallback to the one-shot scored CSV
  const rows = readCSVTail(PATHS.scoredCSV, 50);
  res.json({ headlines: rows, count: rows.length });
});

// Daily sentiment history
app.get('/api/daily', (req, res) => {
  const rows = readCSVTail(PATHS.dailyCSV, 90);
  res.json({ daily: rows, count: rows.length });
});

// System logs (for the terminal panel in React)
app.get('/api/logs', (req, res) => {
  res.json({ logs: monitorLogs.slice(0, 30) });
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    monitor_pid: monitorProcess?.pid ?? null,
    monitor_running: monitorProcess !== null,
    files: Object.fromEntries(
      Object.entries(PATHS).map(([k, v]) => [k, fs.existsSync(v)])
    )
  });
});

// Control endpoints
app.post('/api/monitor/start', (req, res) => {
  startMonitor();
  res.json({ status: 'started' });
});

app.post('/api/monitor/stop', (req, res) => {
  stopMonitor();
  res.json({ status: 'stopped' });
});

// Get regime analysis
app.get('/api/regime', (req, res) => {
  const summaryPath = path.join(DATA_DIR, 'regime', 'regime_summary.json');
  const data = readJSON(summaryPath);
  if (data) return res.json(data);
  res.json({ status: 'not_run', message: 'Run regime detector first' });
});

// Run regime detector
app.post('/api/regime/run', (req, res) => {
  addLog('SYSTEM', 'Running regime detection...');

  const proc = spawn('python', [
    path.join(PYTHON_DIR, 'regime_detector.py')
  ], {
    cwd: PYTHON_DIR,
    env: { ...process.env, DATA_ROOT: DATA_DIR }
  });

  proc.stdout.on('data', (data) => {
    data.toString().split('\n').filter(l => l.trim()).forEach(line => {
      addLog('REGIME', line.trim());
      console.log(`  [regime] ${line.trim()}`);
    });
  });

  proc.on('close', (code) => {
    addLog('SYSTEM', `Regime detection finished (code ${code})`);
  });

  res.json({ status: 'running', message: 'Regime detection started' });
});

// Run one-shot news scrape
app.post('/api/scrape', (req, res) => {
  addLog('SYSTEM', 'Running one-shot news scrape...');

  const proc = spawn('python', [
    path.join(PYTHON_DIR, 'news_scraper.py')
  ], {
    cwd: PYTHON_DIR,
    env: { ...process.env, DATA_ROOT: DATA_DIR }
  });

  proc.on('close', (code) => {
    addLog('SYSTEM', `News scrape finished (code ${code})`);
  });

  res.json({ status: 'scraping', message: 'News scrape started in background' });
});

// Run data collector
app.post('/api/collect', (req, res) => {
  addLog('SYSTEM', 'Running data collector...');

  const proc = spawn('python', [
    path.join(PYTHON_DIR, 'oil_data_collector.py')
  ], {
    cwd: PYTHON_DIR,
    env: { ...process.env, DATA_ROOT: DATA_DIR }
  });

  proc.on('close', (code) => {
    addLog('SYSTEM', `Data collection finished (code ${code})`);
  });

  res.json({ status: 'collecting', message: 'Data collection started in background' });
});

// Get predictions
app.get('/api/predictions', (req, res) => {
  const forecastPath = path.join(DATA_DIR, 'predictions', 'forecast.json');
  const data = readJSON(forecastPath);
  if (data) return res.json(data);
  res.json({ status: 'no_forecast', message: 'Run predictor first' });
});

// Run predictions
app.post('/api/predict', (req, res) => {
  addLog('SYSTEM', 'Running price predictions...');

  const proc = spawn('python', [
    path.join(PYTHON_DIR, 'predictor.py')
  ], {
    cwd: PYTHON_DIR,
    env: { ...process.env, DATA_ROOT: DATA_DIR }
  });

  proc.stdout.on('data', (data) => {
    data.toString().split('\n').filter(l => l.trim()).forEach(line => {
      addLog('PREDICT', line.trim());
      console.log(`  [predict] ${line.trim()}`);
    });
  });

  proc.on('close', (code) => {
    addLog('SYSTEM', `Predictions finished (code ${code})`);
  });

  res.json({ status: 'predicting', message: 'Prediction started in background' });
});

// ── Start Server ─────────────────────────────────────

const PORT = 8081;
app.listen(PORT, () => {
  console.log('='.repeat(55));
  console.log('  OIL PRICE RISK TERMINAL — BACKEND');
  console.log(`  ${new Date().toISOString()}`);
  console.log('='.repeat(55));
  console.log(`\n  API:     http://localhost:${PORT}/api/state`);
  console.log(`  Health:  http://localhost:${PORT}/api/health`);
  console.log(`  Python:  ${PYTHON_DIR}`);
  console.log(`  Data:    ${DATA_DIR}`);
  console.log(`\n  File status:`);
  Object.entries(PATHS).forEach(([key, val]) => {
    const exists = fs.existsSync(val) ? '✓' : '✗';
    console.log(`    ${exists} ${key}`);
  });

  // Auto-start the monitor
  console.log('\n  Starting Python monitor automatically...');
  startMonitor();

  console.log('\n' + '='.repeat(55));
});

// Cleanup on exit
process.on('SIGINT', () => {
  console.log('\nShutting down...');
  stopMonitor();
  process.exit(0);
});

process.on('SIGTERM', () => {
  stopMonitor();
  process.exit(0);
});