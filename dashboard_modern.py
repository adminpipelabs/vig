"""
Modern Mobile-Responsive Dashboard for Vig Bot
Uses Tailwind CSS for mobile-friendly UI
"""
import os
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vig.dashboard")

app = FastAPI(title="Vig Dashboard")

DB_PATH = os.getenv("DB_PATH", "vig.db")
DATABASE_URL = os.getenv("DATABASE_URL")
GAMMA_URL = "https://gamma-api.polymarket.com"

# WebSocket connections for real-time updates
active_connections: list[WebSocket] = []


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


# ─── API Endpoints (Keep existing ones) ──────────────────────────

@app.get("/api/wallet/balance")
def api_wallet_balance():
    """Get wallet balance"""
    conn = get_db()
    c = conn.cursor()
    
    if is_postgres(conn):
        from psycopg2.extras import RealDictCursor
        c = conn.cursor(cursor_factory=RealDictCursor)
    
    c.execute("SELECT COALESCE(SUM(amount), 0) as locked_funds FROM bets WHERE result = 'pending'")
    locked = dict(c.fetchone())['locked_funds'] if c.fetchone() else 0
    
    # Get available balance (would need to fetch from CLOB API)
    # For now, return placeholder
    conn.close()
    return {
        "available": 0,  # TODO: Fetch from CLOB
        "locked": locked,
        "total": locked
    }


@app.get("/api/bot-status")
def api_bot_status():
    """Get bot status"""
    from db import Database
    db = Database(DB_PATH, database_url=DATABASE_URL)
    status = db.get_bot_status("main")
    db.close()
    
    if status:
        return {
            "status": status.get("status", "unknown"),
            "current_window": status.get("current_window"),
            "error_message": status.get("error_message"),
            "last_heartbeat": status.get("last_heartbeat").isoformat() if status.get("last_heartbeat") else None
        }
    return {"status": "unknown"}


@app.get("/api/bets")
def api_bets(limit: int = 100):
    """Get recent bets"""
    conn = get_db()
    c = conn.cursor()
    
    if is_postgres(conn):
        from psycopg2.extras import RealDictCursor
        c = conn.cursor(cursor_factory=RealDictCursor)
    
    c.execute("SELECT * FROM bets ORDER BY placed_at DESC LIMIT ?", (limit,))
    bets = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"bets": bets}


@app.get("/api/stats")
def api_stats():
    """Get bot statistics"""
    conn = get_db()
    c = conn.cursor()
    
    if is_postgres(conn):
        from psycopg2.extras import RealDictCursor
        c = conn.cursor(cursor_factory=RealDictCursor)
    
    c.execute("""
        SELECT 
            COUNT(*) as total_bets,
            SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'lost' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN result = 'pending' THEN 1 ELSE 0 END) as pending,
            COALESCE(SUM(profit), 0) as total_profit
        FROM bets
    """)
    stats = dict(c.fetchone())
    conn.close()
    
    total_resolved = (stats.get('wins') or 0) + (stats.get('losses') or 0)
    win_rate = ((stats.get('wins') or 0) / total_resolved * 100) if total_resolved > 0 else 0
    
    return {
        **stats,
        "win_rate": win_rate,
        "total_resolved": total_resolved
    }


# ─── WebSocket for Real-Time Updates ────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            # Send updates every 5 seconds
            await asyncio.sleep(5)
            
            # Get latest status
            status = api_bot_status()
            stats = api_stats()
            balance = api_wallet_balance()
            
            await websocket.send_json({
                "type": "update",
                "data": {
                    "status": status,
                    "stats": stats,
                    "balance": balance
                }
            })
    except WebSocketDisconnect:
        active_connections.remove(websocket)


# ─── Modern HTML Dashboard ─────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Modern mobile-responsive dashboard"""
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vig Bot Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        'green': '#10b981',
                        'red': '#ef4444',
                        'blue': '#3b82f6',
                    }
                }
            }
        }
    </script>
</head>
<body class="bg-gray-50 min-h-screen">
    <div class="container mx-auto px-4 py-6 max-w-7xl">
        <!-- Header -->
        <div class="bg-white rounded-lg shadow-md p-6 mb-6">
            <div class="flex flex-col md:flex-row md:items-center md:justify-between">
                <div>
                    <h1 class="text-3xl font-bold text-gray-900">Vig Bot Dashboard</h1>
                    <p class="text-gray-600 mt-1" id="status-text">Loading...</p>
                </div>
                <div class="mt-4 md:mt-0 flex gap-2">
                    <button onclick="controlBot('start')" class="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded-lg font-semibold">
                        Start
                    </button>
                    <button onclick="controlBot('stop')" class="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-lg font-semibold">
                        Stop
                    </button>
                    <button onclick="controlBot('restart')" class="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg font-semibold">
                        Restart
                    </button>
                </div>
            </div>
        </div>

        <!-- Stats Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <div class="bg-white rounded-lg shadow-md p-6">
                <div class="text-gray-600 text-sm">Total Profit</div>
                <div class="text-2xl font-bold text-gray-900" id="total-profit">$0.00</div>
            </div>
            <div class="bg-white rounded-lg shadow-md p-6">
                <div class="text-gray-600 text-sm">Win Rate</div>
                <div class="text-2xl font-bold text-gray-900" id="win-rate">0%</div>
            </div>
            <div class="bg-white rounded-lg shadow-md p-6">
                <div class="text-gray-600 text-sm">Available Balance</div>
                <div class="text-2xl font-bold text-green-600" id="available-balance">$0.00</div>
            </div>
            <div class="bg-white rounded-lg shadow-md p-6">
                <div class="text-gray-600 text-sm">Locked Funds</div>
                <div class="text-2xl font-bold text-yellow-600" id="locked-funds">$0.00</div>
            </div>
        </div>

        <!-- Live Bets -->
        <div class="bg-white rounded-lg shadow-md p-6 mb-6">
            <h2 class="text-xl font-bold text-gray-900 mb-4">Live Bets</h2>
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Market</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Side</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Amount</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        </tr>
                    </thead>
                    <tbody id="bets-table" class="bg-white divide-y divide-gray-200">
                        <tr><td colspan="4" class="px-4 py-4 text-center text-gray-500">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        // WebSocket connection
        let ws = null;
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                updateDashboard(data.data);
            };
            
            ws.onerror = () => {
                console.error('WebSocket error');
                setTimeout(connectWebSocket, 5000);
            };
            
            ws.onclose = () => {
                setTimeout(connectWebSocket, 5000);
            };
        }
        
        function updateDashboard(data) {
            // Update status
            const statusText = document.getElementById('status-text');
            statusText.textContent = `Status: ${data.status.status || 'unknown'}`;
            
            // Update stats
            document.getElementById('total-profit').textContent = `$${data.stats.total_profit?.toFixed(2) || '0.00'}`;
            document.getElementById('win-rate').textContent = `${data.stats.win_rate?.toFixed(1) || '0'}%`;
            
            // Update balance
            document.getElementById('available-balance').textContent = `$${data.balance.available?.toFixed(2) || '0.00'}`;
            document.getElementById('locked-funds').textContent = `$${data.balance.locked?.toFixed(2) || '0.00'}`;
        }
        
        async function controlBot(action) {
            try {
                const response = await fetch(`/api/bot-control?action=${action}`, { method: 'POST' });
                const result = await response.json();
                alert(result.message || 'Action completed');
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }
        
        async function loadBets() {
            try {
                const response = await fetch('/api/bets?limit=20');
                const data = await response.json();
                const tbody = document.getElementById('bets-table');
                
                if (data.bets && data.bets.length > 0) {
                    tbody.innerHTML = data.bets.map(bet => `
                        <tr>
                            <td class="px-4 py-3 text-sm text-gray-900">${bet.market_question?.substring(0, 40) || 'N/A'}...</td>
                            <td class="px-4 py-3 text-sm text-gray-900">${bet.side || 'N/A'}</td>
                            <td class="px-4 py-3 text-sm text-gray-900">$${bet.amount?.toFixed(2) || '0.00'}</td>
                            <td class="px-4 py-3 text-sm">
                                <span class="px-2 py-1 rounded ${bet.result === 'won' ? 'bg-green-100 text-green-800' : bet.result === 'lost' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'}">
                                    ${bet.result || 'pending'}
                                </span>
                            </td>
                        </tr>
                    `).join('');
                } else {
                    tbody.innerHTML = '<tr><td colspan="4" class="px-4 py-4 text-center text-gray-500">No bets yet</td></tr>';
                }
            } catch (error) {
                console.error('Error loading bets:', error);
            }
        }
        
        // Initialize
        connectWebSocket();
        loadBets();
        setInterval(loadBets, 10000); // Refresh every 10 seconds
    </script>
</body>
</html>
    """
    return html


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
