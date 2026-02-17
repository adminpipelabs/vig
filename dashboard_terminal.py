"""
Vig Trading Terminal — Real-time trading interface
Shows live markets, positions, orders, and P&L updates
"""
import os
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging

logger = logging.getLogger("vig.terminal")

app = FastAPI(title="Vig Trading Terminal")

# CORS for live updates
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.getenv("DB_PATH", "vig.db")
DATABASE_URL = os.getenv("DATABASE_URL")


def get_db():
    """Get database connection"""
    if DATABASE_URL:
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
            conn.set_session(autocommit=False)
            conn.cursor_factory = RealDictCursor
            return conn
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def is_postgres(conn):
    return hasattr(conn, 'server_version')


# ─── API Endpoints ─────────────────────────────────────────────

@app.get("/api/live/markets")
def api_live_markets(limit: int = 500):
    """Get live markets being scanned/traded"""
    conn = get_db()
    try:
        if is_postgres(conn):
            from psycopg2.extras import RealDictCursor
            c = conn.cursor(cursor_factory=RealDictCursor)
            c.execute("""
                SELECT b.*, 
                    CASE WHEN b.result='pending' THEN 'OPEN' 
                         WHEN b.result='won' THEN 'WON'
                         WHEN b.result='lost' THEN 'LOST'
                         ELSE 'UNKNOWN' END as status,
                    b.placed_at as timestamp
                FROM bets b
                ORDER BY b.placed_at DESC
                LIMIT %s
            """, (limit,))
        else:
            c = conn.cursor()
            c.execute("""
                SELECT b.*, 
                    CASE WHEN b.result='pending' THEN 'OPEN' 
                         WHEN b.result='won' THEN 'WON'
                         WHEN b.result='lost' THEN 'LOST'
                         ELSE 'UNKNOWN' END as status,
                    b.placed_at as timestamp
                FROM bets b
                ORDER BY b.placed_at DESC
                LIMIT ?
            """, (limit,))
        
        rows = [dict(r) for r in c.fetchall()]
        return {"markets": rows, "count": len(rows)}
    except Exception as e:
        logger.error(f"Error fetching markets: {e}")
        return {"markets": [], "count": 0, "error": str(e)}
    finally:
        conn.close()


@app.get("/api/live/positions")
def api_live_positions():
    """Get all open positions with live P&L"""
    conn = get_db()
    try:
        if is_postgres(conn):
            from psycopg2.extras import RealDictCursor
            c = conn.cursor(cursor_factory=RealDictCursor)
            c.execute("""
                SELECT b.*, 
                    b.amount as invested,
                    CASE WHEN b.result='won' THEN b.payout ELSE 0 END as current_value,
                    CASE WHEN b.result='won' THEN (b.payout - b.amount)
                         WHEN b.result='lost' THEN -b.amount
                         ELSE 0 END as unrealized_pnl,
                    b.placed_at as opened_at
                FROM bets b
                WHERE b.result='pending'
                ORDER BY b.placed_at DESC
            """)
        else:
            c = conn.cursor()
            c.execute("""
                SELECT b.*, 
                    b.amount as invested,
                    CASE WHEN b.result='won' THEN b.payout ELSE 0 END as current_value,
                    CASE WHEN b.result='won' THEN (b.payout - b.amount)
                         WHEN b.result='lost' THEN -b.amount
                         ELSE 0 END as unrealized_pnl,
                    b.placed_at as opened_at
                FROM bets b
                WHERE b.result='pending'
                ORDER BY b.placed_at DESC
            """)
        
        positions = [dict(r) for r in c.fetchall()]
        
        # Calculate totals
        total_invested = sum(float(p.get('invested', 0) or 0) for p in positions)
        total_value = sum(float(p.get('current_value', 0) or 0) for p in positions)
        total_pnl = total_value - total_invested
        
        return {
            "positions": positions,
            "summary": {
                "count": len(positions),
                "total_invested": total_invested,
                "total_value": total_value,
                "total_pnl": total_pnl,
                "pnl_pct": (total_pnl / total_invested * 100) if total_invested > 0 else 0
            }
        }
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        return {"positions": [], "summary": {}, "error": str(e)}
    finally:
        conn.close()


@app.get("/api/live/pnl")
def api_live_pnl():
    """Get live P&L updates"""
    conn = get_db()
    try:
        if is_postgres(conn):
            from psycopg2.extras import RealDictCursor
            c = conn.cursor(cursor_factory=RealDictCursor)
            c.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE result='won') as wins,
                    COUNT(*) FILTER (WHERE result='lost') as losses,
                    COUNT(*) FILTER (WHERE result='pending') as open,
                    COALESCE(SUM(CASE WHEN result != 'pending' THEN profit ELSE 0 END), 0) as realized_pnl,
                    COALESCE(SUM(CASE WHEN result='pending' THEN amount ELSE 0 END), 0) as open_invested,
                    COALESCE(SUM(profit), 0) as total_pnl
                FROM bets
            """)
        else:
            c = conn.cursor()
            c.execute("""
                SELECT 
                    SUM(CASE WHEN result='won' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN result='lost' THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN result='pending' THEN 1 ELSE 0 END) as open,
                    COALESCE(SUM(CASE WHEN result != 'pending' THEN profit ELSE 0 END), 0) as realized_pnl,
                    COALESCE(SUM(CASE WHEN result='pending' THEN amount ELSE 0 END), 0) as open_invested,
                    COALESCE(SUM(profit), 0) as total_pnl
                FROM bets
            """)
        
        row = dict(c.fetchone())
        return {
            "wins": int(row.get('wins', 0) or 0),
            "losses": int(row.get('losses', 0) or 0),
            "open": int(row.get('open', 0) or 0),
            "realized_pnl": float(row.get('realized_pnl', 0) or 0),
            "open_invested": float(row.get('open_invested', 0) or 0),
            "total_pnl": float(row.get('total_pnl', 0) or 0),
            "win_rate": (int(row.get('wins', 0) or 0) / (int(row.get('wins', 0) or 0) + int(row.get('losses', 0) or 0)) * 100) if (int(row.get('wins', 0) or 0) + int(row.get('losses', 0) or 0)) > 0 else 0
        }
    except Exception as e:
        logger.error(f"Error fetching P&L: {e}")
        return {"error": str(e)}
    finally:
        conn.close()


@app.get("/api/live/activity")
def api_live_activity(limit: int = 100):
    """Get recent trading activity (orders, settlements)"""
    conn = get_db()
    try:
        if is_postgres(conn):
            from psycopg2.extras import RealDictCursor
            c = conn.cursor(cursor_factory=RealDictCursor)
            c.execute("""
                SELECT 
                    id, market_question, side, price, amount, result, profit, payout,
                    placed_at, resolved_at,
                    CASE WHEN result='pending' THEN 'BUY'
                         WHEN result='won' THEN 'SELL'
                         WHEN result='lost' THEN 'CLOSE'
                         ELSE 'UNKNOWN' END as action
                FROM bets
                ORDER BY COALESCE(resolved_at, placed_at) DESC
                LIMIT %s
            """, (limit,))
        else:
            c = conn.cursor()
            c.execute("""
                SELECT 
                    id, market_question, side, price, amount, result, profit, payout,
                    placed_at, resolved_at,
                    CASE WHEN result='pending' THEN 'BUY'
                         WHEN result='won' THEN 'SELL'
                         WHEN result='lost' THEN 'CLOSE'
                         ELSE 'UNKNOWN' END as action
                FROM bets
                ORDER BY COALESCE(resolved_at, placed_at) DESC
                LIMIT ?
            """, (limit,))
        
        activities = [dict(r) for r in c.fetchall()]
        return {"activities": activities, "count": len(activities)}
    except Exception as e:
        logger.error(f"Error fetching activity: {e}")
        return {"activities": [], "count": 0, "error": str(e)}
    finally:
        conn.close()


@app.get("/api/live/stats")
def api_live_stats():
    """Get live bot stats"""
    from db import Database
    import os
    
    try:
        database_url = os.getenv("DATABASE_URL")
        db_path = os.getenv("DB_PATH", "vig.db")
        db = Database(db_path, database_url=database_url)
        
        bot_status = db.get_bot_status("main")
        db.close()
        
        return {
            "status": bot_status.get("status", "unknown") if bot_status else "unknown",
            "current_window": bot_status.get("current_window", "N/A") if bot_status else "N/A",
            "last_heartbeat": bot_status.get("last_heartbeat") if bot_status else None,
            "scan_count": bot_status.get("scan_count", 0) if bot_status else 0
        }
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return {"status": "error", "error": str(e)}


@app.get("/", response_class=HTMLResponse)
def terminal_root():
    """Trading Terminal UI"""
    return TERMINAL_HTML


# ─── Trading Terminal HTML ─────────────────────────────────────────────

TERMINAL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Vig Trading Terminal</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
      background: #0a0e27;
      color: #e0e0e0;
      overflow-x: hidden;
    }
    .terminal-header {
      background: #151932;
      border-bottom: 1px solid #2a2f4a;
      padding: 12px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .logo { font-size: 18px; font-weight: bold; color: #00ffff; }
    .status-indicator {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
    }
    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #00ff00;
      animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }
    .status-dot.error { background: #ff0000; }
    .status-dot.warning { background: #ffaa00; }
    
    .stats-bar {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      padding: 16px 20px;
      background: #151932;
      border-bottom: 1px solid #2a2f4a;
    }
    .stat-box {
      background: #1a1f3a;
      padding: 12px;
      border-radius: 4px;
      border-left: 3px solid #00ffff;
    }
    .stat-label {
      font-size: 10px;
      color: #888;
      text-transform: uppercase;
      margin-bottom: 4px;
    }
    .stat-value {
      font-size: 18px;
      font-weight: bold;
      color: #00ffff;
    }
    .stat-value.positive { color: #00ff88; }
    .stat-value.negative { color: #ff4444; }
    
    .main-grid {
      display: grid;
      grid-template-columns: 1fr 400px;
      gap: 12px;
      padding: 12px 20px;
      height: calc(100vh - 140px);
    }
    
    .markets-panel {
      background: #151932;
      border-radius: 4px;
      border: 1px solid #2a2f4a;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .panel-header {
      padding: 12px 16px;
      border-bottom: 1px solid #2a2f4a;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: #1a1f3a;
    }
    .panel-title {
      font-size: 14px;
      font-weight: bold;
      color: #00ffff;
    }
    .panel-content {
      flex: 1;
      overflow-y: auto;
      overflow-x: hidden;
    }
    
    .market-row {
      padding: 10px 16px;
      border-bottom: 1px solid #1a1f3a;
      display: grid;
      grid-template-columns: 2fr 80px 60px 80px 80px 100px 80px;
      gap: 12px;
      align-items: center;
      font-size: 11px;
      transition: background 0.2s;
    }
    .market-row:hover {
      background: #1a1f3a;
    }
    .market-row.new {
      animation: highlight 2s;
    }
    @keyframes highlight {
      0% { background: #00ffff33; }
      100% { background: transparent; }
    }
    .market-name {
      color: #e0e0e0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .market-price {
      text-align: right;
      font-weight: bold;
    }
    .market-price.buy { color: #00ff88; }
    .market-price.sell { color: #ff4444; }
    .market-status {
      padding: 2px 6px;
      border-radius: 3px;
      font-size: 10px;
      text-align: center;
    }
    .status-open { background: #00ffff22; color: #00ffff; }
    .status-won { background: #00ff8822; color: #00ff88; }
    .status-lost { background: #ff444422; color: #ff4444; }
    
    .sidebar {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    
    .positions-panel, .activity-panel {
      background: #151932;
      border-radius: 4px;
      border: 1px solid #2a2f4a;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      max-height: 50%;
    }
    
    .position-item, .activity-item {
      padding: 8px 12px;
      border-bottom: 1px solid #1a1f3a;
      font-size: 11px;
    }
    .position-item:last-child, .activity-item:last-child {
      border-bottom: none;
    }
    
    .scrollable {
      flex: 1;
      overflow-y: auto;
      overflow-x: hidden;
    }
    
    ::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }
    ::-webkit-scrollbar-track {
      background: #0a0e27;
    }
    ::-webkit-scrollbar-thumb {
      background: #2a2f4a;
      border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: #3a3f5a;
    }
    
    .loading {
      padding: 20px;
      text-align: center;
      color: #888;
    }
    
    @media (max-width: 1200px) {
      .main-grid {
        grid-template-columns: 1fr;
      }
      .market-row {
        grid-template-columns: 2fr 60px 50px 70px 70px 80px 70px;
        font-size: 10px;
      }
    }
  </style>
</head>
<body>
  <div class="terminal-header">
    <div class="logo">VIG TRADING TERMINAL</div>
    <div class="status-indicator">
      <div class="status-dot" id="statusDot"></div>
      <span id="statusText">Connecting...</span>
    </div>
  </div>
  
  <div class="stats-bar">
    <div class="stat-box">
      <div class="stat-label">Total P&L</div>
      <div class="stat-value" id="totalPnl">$0.00</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">Win Rate</div>
      <div class="stat-value" id="winRate">0%</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">Open Positions</div>
      <div class="stat-value" id="openPositions">0</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">Realized P&L</div>
      <div class="stat-value" id="realizedPnl">$0.00</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">Bot Status</div>
      <div class="stat-value" id="botStatus" style="font-size: 12px;">--</div>
    </div>
  </div>
  
  <div class="main-grid">
    <div class="markets-panel">
      <div class="panel-header">
        <div class="panel-title">Live Markets & Orders</div>
        <div style="font-size: 10px; color: #888;" id="marketCount">0 markets</div>
      </div>
      <div class="panel-content" id="marketsList">
        <div class="loading">Loading markets...</div>
      </div>
    </div>
    
    <div class="sidebar">
      <div class="positions-panel">
        <div class="panel-header">
          <div class="panel-title">Open Positions</div>
          <div style="font-size: 10px; color: #888;" id="positionCount">0</div>
        </div>
        <div class="panel-content scrollable" id="positionsList">
          <div class="loading">Loading positions...</div>
        </div>
      </div>
      
      <div class="activity-panel">
        <div class="panel-header">
          <div class="panel-title">Recent Activity</div>
        </div>
        <div class="panel-content scrollable" id="activityList">
          <div class="loading">Loading activity...</div>
        </div>
      </div>
    </div>
  </div>
  
  <script>
    let lastUpdate = {};
    
    async function fetchData(endpoint) {
      try {
        const res = await fetch(endpoint);
        if (!res.ok) return null;
        return await res.json();
      } catch (e) {
        console.error(`Error fetching ${endpoint}:`, e);
        return null;
      }
    }
    
    function formatCurrency(n) {
      if (n == null) return '--';
      const sign = n >= 0 ? '+' : '';
      return sign + '$' + Math.abs(n).toFixed(2);
    }
    
    function formatTime(iso) {
      if (!iso) return '--';
      const d = new Date(iso);
      const now = Date.now();
      const diff = now - d.getTime();
      if (diff < 60000) return Math.floor(diff / 1000) + 's ago';
      if (diff < 3600000) return Math.floor(diff / 60000) + 'm ago';
      return d.toLocaleTimeString();
    }
    
    async function updateMarkets() {
      const data = await fetchData('/api/live/markets?limit=500');
      if (!data || !data.markets) return;
      
      const container = document.getElementById('marketsList');
      document.getElementById('marketCount').textContent = `${data.count} markets`;
      
      if (data.markets.length === 0) {
        container.innerHTML = '<div class="loading">No markets found</div>';
        return;
      }
      
      let html = '<div style="padding: 8px 16px; background: #1a1f3a; border-bottom: 1px solid #2a2f4a; display: grid; grid-template-columns: 2fr 80px 60px 80px 80px 100px 80px; gap: 12px; font-size: 10px; color: #888; font-weight: bold;">';
      html += '<div>Market</div><div style="text-align:right">Price</div><div>Side</div><div style="text-align:right">Amount</div><div style="text-align:right">P&L</div><div>Status</div><div>Time</div></div>';
      
      data.markets.forEach(m => {
        const isNew = !lastUpdate.markets || !lastUpdate.markets.find(old => old.id === m.id);
        const pnl = m.profit || 0;
        const statusClass = m.status === 'OPEN' ? 'status-open' : m.status === 'WON' ? 'status-won' : 'status-lost';
        
        html += `<div class="market-row ${isNew ? 'new' : ''}">`;
        html += `<div class="market-name" title="${m.market_question || ''}">${(m.market_question || '').substring(0, 50)}${(m.market_question || '').length > 50 ? '...' : ''}</div>`;
        html += `<div class="market-price ${m.side === 'YES' ? 'buy' : 'sell'}">$${(m.price || 0).toFixed(2)}</div>`;
        html += `<div>${m.side || '--'}</div>`;
        html += `<div style="text-align:right">${formatCurrency(m.amount)}</div>`;
        html += `<div style="text-align:right" class="${pnl >= 0 ? 'stat-value positive' : 'stat-value negative'}">${formatCurrency(pnl)}</div>`;
        html += `<div><span class="market-status ${statusClass}">${m.status}</span></div>`;
        html += `<div style="font-size: 10px; color: #888;">${formatTime(m.timestamp || m.placed_at)}</div>`;
        html += '</div>';
      });
      
      container.innerHTML = html;
      lastUpdate.markets = data.markets;
    }
    
    async function updatePositions() {
      const data = await fetchData('/api/live/positions');
      if (!data || !data.positions) return;
      
      const container = document.getElementById('positionsList');
      document.getElementById('positionCount').textContent = `${data.summary.count || 0}`;
      
      if (data.positions.length === 0) {
        container.innerHTML = '<div class="loading">No open positions</div>';
        return;
      }
      
      let html = '';
      data.positions.forEach(p => {
        const pnl = p.unrealized_pnl || 0;
        html += '<div class="position-item">';
        html += `<div style="font-weight: bold; margin-bottom: 4px;">${(p.market_question || '').substring(0, 40)}...</div>`;
        html += `<div style="display: flex; justify-content: space-between; font-size: 10px;">`;
        html += `<span>Invested: ${formatCurrency(p.invested)}</span>`;
        html += `<span class="${pnl >= 0 ? 'stat-value positive' : 'stat-value negative'}" style="font-size: 11px;">${formatCurrency(pnl)}</span>`;
        html += '</div></div>';
      });
      
      container.innerHTML = html;
    }
    
    async function updateActivity() {
      const data = await fetchData('/api/live/activity?limit=50');
      if (!data || !data.activities) return;
      
      const container = document.getElementById('activityList');
      
      if (data.activities.length === 0) {
        container.innerHTML = '<div class="loading">No activity</div>';
        return;
      }
      
      let html = '';
      data.activities.slice(0, 20).forEach(a => {
        const action = a.action || 'UNKNOWN';
        const color = action === 'BUY' ? '#00ff88' : action === 'SELL' ? '#00ffff' : '#ff4444';
        html += '<div class="activity-item">';
        html += `<div style="display: flex; justify-content: space-between; margin-bottom: 4px;">`;
        html += `<span style="color: ${color}; font-weight: bold;">${action}</span>`;
        html += `<span style="font-size: 10px; color: #888;">${formatTime(a.resolved_at || a.placed_at)}</span>`;
        html += '</div>';
        html += `<div style="font-size: 10px; color: #aaa;">${(a.market_question || '').substring(0, 35)}...</div>`;
        if (a.profit != null) {
          html += `<div style="text-align: right; margin-top: 4px;" class="${a.profit >= 0 ? 'stat-value positive' : 'stat-value negative'}" style="font-size: 11px;">${formatCurrency(a.profit)}</div>`;
        }
        html += '</div>';
      });
      
      container.innerHTML = html;
    }
    
    async function updateStats() {
      const pnlData = await fetchData('/api/live/pnl');
      const botData = await fetchData('/api/live/stats');
      
      if (pnlData) {
        document.getElementById('totalPnl').textContent = formatCurrency(pnlData.total_pnl);
        document.getElementById('totalPnl').className = 'stat-value ' + (pnlData.total_pnl >= 0 ? 'positive' : 'negative');
        document.getElementById('winRate').textContent = pnlData.win_rate.toFixed(1) + '%';
        document.getElementById('openPositions').textContent = pnlData.open || 0;
        document.getElementById('realizedPnl').textContent = formatCurrency(pnlData.realized_pnl);
        document.getElementById('realizedPnl').className = 'stat-value ' + (pnlData.realized_pnl >= 0 ? 'positive' : 'negative');
      }
      
      if (botData) {
        const status = botData.status || 'unknown';
        document.getElementById('botStatus').textContent = status.toUpperCase();
        const dot = document.getElementById('statusDot');
        const text = document.getElementById('statusText');
        if (status === 'running') {
          dot.className = 'status-dot';
          text.textContent = 'LIVE';
        } else if (status === 'error') {
          dot.className = 'status-dot error';
          text.textContent = 'ERROR';
        } else {
          dot.className = 'status-dot warning';
          text.textContent = status.toUpperCase();
        }
      }
    }
    
    async function refreshAll() {
      await Promise.all([
        updateMarkets(),
        updatePositions(),
        updateActivity(),
        updateStats()
      ]);
    }
    
    // Initial load
    refreshAll();
    
    // Auto-refresh every 2 seconds
    setInterval(refreshAll, 2000);
  </script>
</body>
</html>
"""
