"""
Vig v1 Dashboard — Web UI for monitoring bot performance.
Run: python3 dashboard.py
"""
import os
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import logging

# Configure logging first (before any logger usage)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)

# Suppress verbose HTTP/2 and HPACK debug logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)

logger = logging.getLogger("vig.dashboard")

app = FastAPI(title="Vig Dashboard")

# CORS for live updates
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import security modules
from api_security import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    require_api_key,
    get_api_key_from_request,
    validate_limit as validate_input,
    get_client_id
)

# Add security middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)

DB_PATH = os.getenv("DB_PATH", "vig.db")
DATABASE_URL = os.getenv("DATABASE_URL")
GAMMA_URL = "https://gamma-api.polymarket.com"


def get_db():
    """Get database connection - PostgreSQL if DATABASE_URL is set, otherwise SQLite"""
    if DATABASE_URL:
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
            conn.set_session(autocommit=False)
            # Store cursor factory for PostgreSQL to match SQLite Row behavior
            conn.cursor_factory = RealDictCursor
            return conn
        except ImportError:
            logger.warning("DATABASE_URL set but psycopg2 not installed. Falling back to SQLite.")
            logger.warning("Install with: pip install psycopg2-binary")
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            # Use print for critical startup errors (logger might not be ready)
            try:
                logger.error(f"Failed to connect to PostgreSQL: {e}")
                logger.warning("Falling back to SQLite")
            except:
                print(f"Warning: Failed to connect to PostgreSQL: {e}")
                print("Falling back to SQLite")
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def is_postgres(conn):
    """Check if connection is PostgreSQL"""
    return hasattr(conn, 'server_version')

def execute_query(conn, query, params=None):
    """Execute query with appropriate parameter style (%s for PostgreSQL, ? for SQLite)"""
    c = conn.cursor()
    if is_postgres(conn) and params:
        # Convert ? to %s for PostgreSQL
        query = query.replace('?', '%s')
        c.execute(query, params)
    elif params:
        c.execute(query, params)
    else:
        c.execute(query)
    return c


# ─── API Endpoints ─────────────────────────────────────────────

@app.get("/api/wallet/balance")
def api_wallet_balance():
    """Get wallet balance - available funds and locked funds"""
    conn = get_db()
    if is_postgres(conn):
        from psycopg2.extras import RealDictCursor
        c = conn.cursor(cursor_factory=RealDictCursor)
    else:
        c = conn.cursor()
    
    # Calculate locked funds from pending bets
    c.execute("""
        SELECT COALESCE(SUM(amount), 0) as locked_funds
        FROM bets
        WHERE result='pending'
    """)
    row = c.fetchone()
    locked_funds = float(dict(row)["locked_funds"] or 0)
    
    # Get available balance from CLOB
    available_balance = 0.0
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        client = ClobClient('https://clob.polymarket.com', key=os.getenv('POLYGON_PRIVATE_KEY'), chain_id=137)
        client.set_api_creds(client.create_or_derive_api_creds())
        params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=0)
        balance_info = client.get_balance_allowance(params)
        available_balance = float(balance_info.get('balance', 0)) / 1e6
    except Exception as e:
        logger.warning(f"Could not fetch CLOB balance (Cloudflare blocking?): {e}")
        available_balance = None  # Indicate unavailable
    
    total_balance = (available_balance or 0) + locked_funds
    
    conn.close()
    return {
        "available_balance": available_balance,
        "locked_funds": locked_funds,
        "total_balance": total_balance,
        "currency": "USDC",
        "clob_available": available_balance is not None
    }


@app.get("/api/stats")
def api_stats():
    try:
        conn = get_db()
        if is_postgres(conn):
            from psycopg2.extras import RealDictCursor
            c = conn.cursor(cursor_factory=RealDictCursor)
        else:
            c = conn.cursor()
        c.execute("""
            SELECT COUNT(*) as total_bets,
                SUM(CASE WHEN result='won' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result='lost' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN result='pending' THEN 1 ELSE 0 END) as pending,
                COALESCE(SUM(profit), 0) as total_profit,
                COALESCE(SUM(payout), 0) as total_payout,
                COALESCE(SUM(amount), 0) as total_deployed,
                COALESCE(SUM(CASE WHEN result='pending' THEN amount ELSE 0 END), 0) as pending_locked
            FROM bets
        """)
        row = c.fetchone()
        stats = dict(row) if row else {}
        wins = stats.get("wins") or 0
        losses = stats.get("losses") or 0
        resolved = wins + losses
        stats["win_rate"] = (wins / resolved * 100) if resolved > 0 else 0

        c.execute("SELECT * FROM windows ORDER BY id DESC LIMIT 1")
        last_win_row = c.fetchone()
        last_win = dict(last_win_row) if last_win_row else None
        stats["current_clip"] = last_win.get("clip_size", 10.0) if last_win else 10.0
        stats["current_phase"] = last_win.get("phase", "growth") if last_win else "growth"
        stats["last_window_at"] = last_win.get("started_at") if last_win else None

        c.execute("SELECT COUNT(*) as cnt FROM windows")
        cnt_row = c.fetchone()
        stats["total_windows"] = dict(cnt_row).get("cnt", 0) if cnt_row else 0

        c.execute("SELECT COALESCE(SUM(pocketed), 0) as total_pocketed FROM windows")
        pocketed_row = c.fetchone()
        stats["total_pocketed"] = float(dict(pocketed_row).get("total_pocketed", 0) or 0) if pocketed_row else 0.0

        c.execute("SELECT result FROM bets WHERE result!='pending' ORDER BY id DESC")
        streak = 0
        for row in c.fetchall():
            row_dict = dict(row)
            if row_dict.get("result") == "lost":
                streak += 1
            else:
                break
        stats["consecutive_losses"] = streak
        
        conn.close()
        return stats
    except Exception as e:
        logger.error(f"Error in api_stats: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "total_bets": 0,
            "wins": 0,
            "losses": 0,
            "pending": 0,
            "total_profit": 0,
            "win_rate": 0,
            "current_clip": 10.0,
            "current_phase": "growth",
            "error": str(e)
        }

    c.execute("SELECT paper FROM bets ORDER BY id DESC LIMIT 1")
    last_bet_row = c.fetchone()
    last_bet = dict(last_bet_row) if last_bet_row else None
    stats["mode"] = "paper" if (not last_bet or last_bet["paper"]) else "live"
    
    # Calculate position value from pending bets
    # Position value = SUM(shares × current_market_price)
    # shares = size (already calculated as amount/price when bet was placed)
    c.execute("""
        SELECT token_id, size, price
        FROM bets 
        WHERE result='pending'
    """)
    pending_bets_rows = c.fetchall()
    pending_bets = [dict(r) for r in pending_bets_rows]
    
    position_value = 0.0
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        clob_client = ClobClient('https://clob.polymarket.com', key=os.getenv('POLYGON_PRIVATE_KEY'), chain_id=137)
        clob_client.set_api_creds(clob_client.create_or_derive_api_creds())
        
        for bet in pending_bets:
            token_id = bet["token_id"]
            shares = bet["size"]  # shares owned
            
            # Try to get current price from CLOB orderbook
            try:
                orderbook = clob_client.get_order_book(token_id)
                if orderbook and 'bids' in orderbook and len(orderbook['bids']) > 0:
                    # Use best bid price (what we could sell for)
                    current_price = float(orderbook['bids'][0][0])
                elif orderbook and 'asks' in orderbook and len(orderbook['asks']) > 0:
                    # Fallback to ask price if no bids
                    current_price = float(orderbook['asks'][0][0])
                else:
                    # Fallback to entry price
                    current_price = bet["price"]
            except:
                # Fallback to entry price if can't fetch
                current_price = bet["price"]
            
            # Position value = shares × current_price
            position_value += shares * current_price
    except Exception as e:
        # Fallback: use size × entry price if CLOB unavailable
        c.execute("SELECT COALESCE(SUM(size * price), 0) as position_value FROM bets WHERE result='pending'")
        position_row = c.fetchone()
        position_dict = dict(position_row) if position_row else {}
        position_value = float(position_dict.get("position_value", 0) or 0)
    
    stats["position_value"] = position_value
    
    # Starting balance
    starting_balance = 90.0
    stats["starting_balance"] = starting_balance
    
    # Try to get CLOB balance first (source of truth for Polymarket internal accounting)
    # Polymarket uses internal accounting, so CLOB balance reflects redemptions
    clob_cash = None
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        client = ClobClient('https://clob.polymarket.com', key=os.getenv('POLYGON_PRIVATE_KEY'), chain_id=137)
        client.set_api_creds(client.create_or_derive_api_creds())
        params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=0)
        balance_info = client.get_balance_allowance(params)
        clob_cash = float(balance_info.get('balance', 0)) / 1e6
        
        # Use CLOB balance directly (it should reflect redemptions after API updates)
        # If CLOB API hasn't updated yet, the balance will be lower temporarily
        # Redemptions are tracked via blockchain transactions, so balance will catch up
        stats["current_cash"] = clob_cash
        stats["clob_cash_raw"] = clob_cash  # Store CLOB balance for reference
        logger.info(f"CLOB balance: ${clob_cash:.2f}")
    except Exception as e:
        # Cloudflare blocking or other CLOB API errors - calculate from database
        logger.warning(f"Could not fetch CLOB balance (Cloudflare blocking?): {e}")
        logger.info("Falling back to database calculation")
        
        # Calculate from database: Starting + Payouts - Deployed (settled bets)
        c.execute("""
            SELECT 
                COALESCE(SUM(payout), 0) as total_payouts,
                COALESCE(SUM(amount), 0) as total_deployed_settled
            FROM bets 
            WHERE result != 'pending'
        """)
        settled_row = c.fetchone()
        settled_dict = dict(settled_row) if settled_row else {}
        total_payouts = float(settled_dict.get("total_payouts", 0) or 0)
        total_deployed_settled = float(settled_dict.get("total_deployed_settled", 0) or 0)
        
        # Calculate current cash: Starting + Payouts - Deployed (settled bets)
        current_cash_calculated = starting_balance + total_payouts - total_deployed_settled
        stats["current_cash"] = current_cash_calculated
        logger.debug(f"Using calculated balance: ${current_cash_calculated:.2f}")
    
    stats["clob_cash"] = clob_cash  # Store for reference/debugging
    
    # Calculate total portfolio value
    cash = stats.get("current_cash") or 0.0
    stats["total_portfolio"] = cash + stats["position_value"]
    
    # Net P&L = Total portfolio - Starting balance
    stats["net_pnl"] = stats["total_portfolio"] - starting_balance
    
    conn.close()
    return stats


@app.get("/api/windows")
def api_windows(limit: int = 50):
    """Get recent trading windows"""
    limit = validate_input(limit, max_limit=1000)
    conn = get_db()
    if is_postgres(conn):
        from psycopg2.extras import RealDictCursor
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("SELECT * FROM windows ORDER BY id DESC LIMIT %s", (limit,))
        rows = [dict(r) for r in c.fetchall()]
    else:
        c = conn.cursor()
        c.execute("SELECT * FROM windows ORDER BY id DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


@app.get("/api/bets")
def api_bets(limit: int = 100):
    """Get recent bets"""
    limit = validate_input(limit, max_limit=1000)
    conn = get_db()
    # Use RealDictCursor for PostgreSQL, regular cursor for SQLite
    if is_postgres(conn):
        from psycopg2.extras import RealDictCursor
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("SELECT * FROM bets ORDER BY id DESC LIMIT %s", (limit,))
        rows = [dict(r) for r in c.fetchall()]
    else:
        c = conn.cursor()
        c.execute("SELECT * FROM bets ORDER BY id DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


@app.get("/api/pending")
def api_pending():
    conn = get_db()
    if is_postgres(conn):
        from psycopg2.extras import RealDictCursor
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("SELECT * FROM bets WHERE result='pending' ORDER BY id DESC")
    else:
        c = conn.cursor()
    c.execute("SELECT * FROM bets WHERE result='pending' ORDER BY id DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


@app.get("/api/circuit-breaker", dependencies=[Depends(require_api_key)])
def api_circuit_breaker():
    conn = get_db()
    if is_postgres(conn):
        from psycopg2.extras import RealDictCursor
        c = conn.cursor(cursor_factory=RealDictCursor)
    else:
        c = conn.cursor()
    c.execute("SELECT * FROM circuit_breaker_log ORDER BY id DESC LIMIT 20")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


@app.get("/api/equity-curve", dependencies=[Depends(require_api_key)])
def api_equity_curve():
    conn = get_db()
    if is_postgres(conn):
        from psycopg2.extras import RealDictCursor
        c = conn.cursor(cursor_factory=RealDictCursor)
    else:
        c = conn.cursor()
    c.execute("SELECT id, started_at, profit, pocketed, clip_size, phase FROM windows ORDER BY id ASC")
    rows = c.fetchall()
    cumulative = 0
    curve = []
    for r in rows:
        # Convert to dict if needed (PostgreSQL RealDictCursor already dict-like)
        row_dict = dict(r) if not isinstance(r, dict) else r
        cumulative += row_dict["profit"]
        curve.append({
            "window": row_dict["id"], "date": row_dict["started_at"],
            "profit": row_dict["profit"], "cumulative": round(cumulative, 2),
            "clip": row_dict["clip_size"], "phase": row_dict["phase"],
        })
    conn.close()
    return curve


@app.get("/api/pnl-flow", dependencies=[Depends(require_api_key)])
def api_pnl_flow():
    """Get complete P&L cash flow with running balance"""
    conn = get_db()
    if is_postgres(conn):
        from psycopg2.extras import RealDictCursor
        c = conn.cursor(cursor_factory=RealDictCursor)
    else:
        c = conn.cursor()
    
    # Get all bets ordered by time
    c.execute("""
        SELECT id, placed_at, resolved_at, market_question, side,
               amount, price, size, result, payout, profit, order_id
        FROM bets 
        ORDER BY placed_at ASC
    """)
    bets_rows = c.fetchall()
    bets = [dict(r) for r in bets_rows]
    
    # Calculate cash flow
    starting_balance = 90.0  # TODO: Make this configurable
    flow = []
    running_balance = starting_balance
    total_profit = 0.0
    
    # Add starting balance entry
    flow.append({
        "id": None,
        "date": None,
        "type": "starting_balance",
        "description": "Starting Balance",
        "market": None,
        "side": None,
        "amount": None,
        "payout": None,
        "profit": None,
        "balance": running_balance,
        "result": None
    })
    
    for bet in bets:
        # Bet placed - debit
        running_balance -= bet["amount"]
        flow.append({
            "id": bet["id"],
            "date": bet["placed_at"],
            "type": "bet_placed",
            "description": f"Bet Placed: {bet['market_question'][:50]}",
            "market": bet["market_question"],
            "side": bet["side"],
            "amount": bet["amount"],
            "payout": None,
            "profit": None,
            "balance": running_balance,
            "result": None,
            "order_id": bet["order_id"]
        })
        
        # If resolved, add payout
        if bet["result"] != "pending" and bet["payout"]:
            running_balance += bet["payout"]
            total_profit += bet["profit"] or 0
            flow.append({
                "id": bet["id"],
                "date": bet["resolved_at"],
                "type": "settlement",
                "description": f"Settled: {bet['market_question'][:50]}",
                "market": bet["market_question"],
                "side": bet["side"],
                "amount": None,
                "payout": bet["payout"],
                "profit": bet["profit"],
                "balance": running_balance,
                "result": bet["result"],
                "order_id": bet["order_id"]
            })
    
    # Get actual current balance - match Overview tab calculation
    # Overview shows: total_portfolio = current_cash + position_value
    # Where position_value = locked funds from pending bets
    
    # Get current cash from CLOB (same as Overview)
    current_cash = 0.0
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        client = ClobClient('https://clob.polymarket.com', key=os.getenv('POLYGON_PRIVATE_KEY'), chain_id=137)
        client.set_api_creds(client.create_or_derive_api_creds())
        params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=0)
        balance_info = client.get_balance_allowance(params)
        current_cash = float(balance_info.get('balance', 0)) / 1e6
    except Exception as e:
        # Fallback: calculate from settled transactions
        current_cash = running_balance
    
    # Get locked funds (pending bets) - same as Overview's position_value
    c.execute("SELECT COALESCE(SUM(amount), 0) as pending_amount FROM bets WHERE result = 'pending'")
    pending_row = c.fetchone()
    pending_dict = dict(pending_row) if pending_row else {}
    pending_amount = float(pending_dict.get("pending_amount", 0) or 0)
    
    # Total portfolio = current cash + locked funds (matches Overview)
    actual_current_balance = current_cash + pending_amount
    
    # Calculate net P&L (matches Overview)
    actual_net_pnl = actual_current_balance - starting_balance
    
    # Also calculate settled P&L (for reference)
    c.execute("SELECT COALESCE(SUM(profit), 0) as settled_pnl FROM bets WHERE result != 'pending'")
    settled_pnl_row = c.fetchone()
    settled_pnl_dict = dict(settled_pnl_row) if settled_pnl_row else {}
    settled_pnl = float(settled_pnl_dict.get("settled_pnl", 0) or 0)
    
    conn.close()
    return {
        "starting_balance": starting_balance,
        "current_balance": actual_current_balance,  # Matches Overview's total_portfolio
        "net_pnl": actual_net_pnl,  # Matches Overview's net_pnl
        "settled_pnl": settled_pnl,  # Settled bets P&L only
        "pending_amount": pending_amount,  # Amount locked in pending bets
        "flow": flow
    }


@app.get("/api/daily-stats")
def api_daily_stats(days: int = 7):
    """Get daily performance statistics for the last N days"""
    conn = get_db()
    is_pg = is_postgres(conn)
    if is_pg:
        from psycopg2.extras import RealDictCursor
        c = conn.cursor(cursor_factory=RealDictCursor)
    else:
        c = conn.cursor()
    
    # Get daily stats (SQLite vs PostgreSQL compatible)
    if is_pg:
        c.execute("""
            SELECT 
                DATE(placed_at) as date,
                COUNT(*) as total_bets,
                SUM(CASE WHEN result='won' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result='lost' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN result='pending' THEN 1 ELSE 0 END) as pending,
                COALESCE(SUM(profit), 0) as profit,
                COALESCE(SUM(amount), 0) as deployed
            FROM bets
            WHERE placed_at >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY DATE(placed_at)
            ORDER BY date DESC
        """, (days,))
    else:
        # SQLite version (for local dev only)
        c.execute("""
            SELECT 
                DATE(placed_at) as date,
                COUNT(*) as total_bets,
                SUM(CASE WHEN result='won' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result='lost' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN result='pending' THEN 1 ELSE 0 END) as pending,
                COALESCE(SUM(profit), 0) as profit,
                COALESCE(SUM(amount), 0) as deployed
            FROM bets
            WHERE placed_at >= datetime('now', '-' || ? || ' days')
            GROUP BY DATE(placed_at)
            ORDER BY date DESC
        """, (days,))
    
    daily_rows = c.fetchall()
    daily_stats = []
    for row in daily_rows:
        row_dict = dict(row)
        wins = row_dict.get("wins") or 0
        losses = row_dict.get("losses") or 0
        resolved = wins + losses
        win_rate = (wins / resolved * 100) if resolved > 0 else 0
        
        daily_stats.append({
            "date": str(row_dict["date"]),
            "total_bets": row_dict.get("total_bets") or 0,
            "wins": wins,
            "losses": losses,
            "pending": row_dict.get("pending") or 0,
            "win_rate": round(win_rate, 1),
            "profit": float(row_dict.get("profit") or 0),
            "deployed": float(row_dict.get("deployed") or 0)
        })
    
    return {"daily_stats": daily_stats, "days": days}


@app.get("/api/historical-summary")
def api_historical_summary():
    """Get summary statistics for different time periods"""
    conn = get_db()
    if is_postgres(conn):
        from psycopg2.extras import RealDictCursor
        c = conn.cursor(cursor_factory=RealDictCursor)
    else:
        c = conn.cursor()
    
    summary = {}
    
    is_pg = is_postgres(conn)
    
    # Last 24 hours
    if is_pg:
        c.execute("""
            SELECT 
                COUNT(*) as total_bets,
                SUM(CASE WHEN result='won' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result='lost' THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(profit), 0) as profit
            FROM bets
            WHERE placed_at >= NOW() - INTERVAL '24 hours'
        """)
    else:
        c.execute("""
            SELECT 
                COUNT(*) as total_bets,
                SUM(CASE WHEN result='won' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result='lost' THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(profit), 0) as profit
            FROM bets
            WHERE placed_at >= datetime('now', '-24 hours')
        """)
    row = c.fetchone()
    if row:
        d = dict(row)
        wins = d.get("wins") or 0
        losses = d.get("losses") or 0
        resolved = wins + losses
        summary["last_24h"] = {
            "total_bets": d.get("total_bets") or 0,
            "wins": wins,
            "losses": losses,
            "win_rate": round((wins / resolved * 100) if resolved > 0 else 0, 1),
            "profit": float(d.get("profit") or 0)
        }
    
    # Last 7 days
    if is_pg:
        c.execute("""
            SELECT 
                COUNT(*) as total_bets,
                SUM(CASE WHEN result='won' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result='lost' THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(profit), 0) as profit
            FROM bets
            WHERE placed_at >= NOW() - INTERVAL '7 days'
        """)
    else:
        c.execute("""
            SELECT 
                COUNT(*) as total_bets,
                SUM(CASE WHEN result='won' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result='lost' THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(profit), 0) as profit
            FROM bets
            WHERE placed_at >= datetime('now', '-7 days')
        """)
    row = c.fetchone()
    if row:
        d = dict(row)
        wins = d.get("wins") or 0
        losses = d.get("losses") or 0
        resolved = wins + losses
        summary["last_7d"] = {
            "total_bets": d.get("total_bets") or 0,
            "wins": wins,
            "losses": losses,
            "win_rate": round((wins / resolved * 100) if resolved > 0 else 0, 1),
            "profit": float(d.get("profit") or 0)
        }
    
    # Last 30 days
    if is_pg:
        c.execute("""
            SELECT 
                COUNT(*) as total_bets,
                SUM(CASE WHEN result='won' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result='lost' THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(profit), 0) as profit
            FROM bets
            WHERE placed_at >= NOW() - INTERVAL '30 days'
        """)
    else:
        c.execute("""
            SELECT 
                COUNT(*) as total_bets,
                SUM(CASE WHEN result='won' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result='lost' THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(profit), 0) as profit
            FROM bets
            WHERE placed_at >= datetime('now', '-30 days')
        """)
    row = c.fetchone()
    if row:
        d = dict(row)
        wins = d.get("wins") or 0
        losses = d.get("losses") or 0
        resolved = wins + losses
        summary["last_30d"] = {
            "total_bets": d.get("total_bets") or 0,
            "wins": wins,
            "losses": losses,
            "win_rate": round((wins / resolved * 100) if resolved > 0 else 0, 1),
            "profit": float(d.get("profit") or 0)
        }
    
    # All time
    c.execute("""
        SELECT 
            COUNT(*) as total_bets,
            SUM(CASE WHEN result='won' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result='lost' THEN 1 ELSE 0 END) as losses,
            COALESCE(SUM(profit), 0) as profit
        FROM bets
    """)
    row = c.fetchone()
    if row:
        d = dict(row)
        wins = d.get("wins") or 0
        losses = d.get("losses") or 0
        resolved = wins + losses
        summary["all_time"] = {
            "total_bets": d.get("total_bets") or 0,
            "wins": wins,
            "losses": losses,
            "win_rate": round((wins / resolved * 100) if resolved > 0 else 0, 1),
            "profit": float(d.get("profit") or 0)
        }
    
    return summary


@app.get("/api/health")
def api_health():
    """Simple health check endpoint"""
    try:
        conn = get_db()
        # Quick database check
        if is_postgres(conn):
            from psycopg2.extras import RealDictCursor
            c = conn.cursor(cursor_factory=RealDictCursor)
        else:
            c = conn.cursor()
        c.execute("SELECT 1")
        c.fetchone()
        
        # Get row counts
        c.execute("SELECT COUNT(*) as cnt FROM bets")
        bets_count = dict(c.fetchone()).get("cnt", 0) if c.fetchone() else 0
        
        c.execute("SELECT COUNT(*) as cnt FROM windows")
        windows_count = dict(c.fetchone()).get("cnt", 0) if c.fetchone() else 0
        
        conn.close()
        return {
            "status": "healthy",
            "database": "connected",
            "bets_count": bets_count,
            "windows_count": windows_count
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.get("/api/test-proxy")
def api_test_proxy():
    """Proxy test endpoint - no proxy needed"""
    return {
        "status": "NO_PROXY",
        "message": "Bot runs without proxy - no Bright Data needed"
    }


@app.get("/api/debug/status")
def debug_status():
    """Full system status for debugging"""
    import os
    
    status = {
        "environment": {
            "PAPER_MODE": os.getenv("PAPER_MODE", "not set"),
            "DATABASE_URL_SET": bool(os.getenv("DATABASE_URL")),
            "PROXY_DISABLED": True,
            "RAILWAY_SERVICE_ID": os.getenv("RAILWAY_SERVICE_ID", "not set"),
            "BOT_SERVICE_ID": os.getenv("BOT_SERVICE_ID", "not set"),
            "RAILWAY_TOKEN_SET": bool(os.getenv("RAILWAY_TOKEN")),
        },
        "database": {},
        "last_window": None,
        "last_bet": None,
    }
    
    # Check database
    try:
        conn = get_db()
        if is_postgres(conn):
            from psycopg2.extras import RealDictCursor
            c = conn.cursor(cursor_factory=RealDictCursor)
        else:
            c = conn.cursor()
        
        # Row counts
        for table in ["bets", "windows"]:
            if is_postgres(conn):
                c.execute(f"SELECT COUNT(*) as cnt FROM {table}")
            else:
                c.execute(f"SELECT COUNT(*) as cnt FROM {table}")
            row = c.fetchone()
            if row:
                row_dict = dict(row) if not isinstance(row, dict) else row
                status["database"][table] = row_dict.get("cnt", 0)
        
        # Last window
        if is_postgres(conn):
            c.execute("SELECT * FROM windows ORDER BY started_at DESC LIMIT 1")
        else:
            c.execute("SELECT * FROM windows ORDER BY started_at DESC LIMIT 1")
        row = c.fetchone()
        if row:
            status["last_window"] = dict(row) if not isinstance(row, dict) else dict(row)
        
        # Last bet
        if is_postgres(conn):
            c.execute("SELECT * FROM bets ORDER BY placed_at DESC LIMIT 1")
        else:
            c.execute("SELECT * FROM bets ORDER BY placed_at DESC LIMIT 1")
        row = c.fetchone()
        if row:
            status["last_bet"] = dict(row) if not isinstance(row, dict) else dict(row)
            
        status["database"]["status"] = "connected"
        conn.close()
    except Exception as e:
        status["database"]["status"] = f"error: {str(e)}"
        import traceback
        status["database"]["traceback"] = traceback.format_exc()
    
    return status


@app.get("/api/bot-status")
def api_bot_status():
    """Get bot status and activity from database heartbeat"""
    from db import Database
    import os
    
    try:
        # Get database connection
        database_url = os.getenv("DATABASE_URL")
        db_path = os.getenv("DB_PATH", "vig.db")
        db = Database(db_path, database_url=database_url)
        
        # Read bot status from database
        bot_status = db.get_bot_status("main")
        
        # If no bot status found, return default
        if not bot_status:
            return {
                "status": "unknown",
                "current_window": "No data",
                "last_heartbeat": None,
                "error_message": None,
                "scan_count": 0
            }
        
        # Get last window time for fallback
        last_window = None
        try:
            conn = get_db()
            if is_postgres(conn):
                from psycopg2.extras import RealDictCursor
                c = conn.cursor(cursor_factory=RealDictCursor)
            else:
                c = conn.cursor()
            
            c.execute("SELECT started_at FROM windows ORDER BY id DESC LIMIT 1")
            last_window_row = c.fetchone()
            last_window = dict(last_window_row).get("started_at") if last_window_row else None
            conn.close()
        except Exception as e:
            logger.error(f"Error getting last window: {e}")
            last_window = None
            logger.warning(f"Could not get last window: {e}")
            if 'conn' in locals() and conn:
                try:
                    conn.close()
                except:
                    pass
        
        if not bot_status:
            # Bot never started or no heartbeat yet - use window fallback
            if last_window:
                try:
                    # Handle both string and datetime objects
                    if isinstance(last_window, str):
                        last_window_str = last_window.replace("Z", "+00:00") if "Z" in last_window else last_window
                        if "+" not in last_window_str and "-" not in last_window_str[-6:]:
                            last_window_str = last_window_str + "+00:00"
                        last_window_dt = datetime.fromisoformat(last_window_str)
                    else:
                        # Already a datetime object
                        last_window_dt = last_window
                    
                    # Ensure timezone-aware
                    if last_window_dt.tzinfo is None:
                        last_window_dt = last_window_dt.replace(tzinfo=timezone.utc)
                    
                    age_seconds = (datetime.now(timezone.utc) - last_window_dt).total_seconds()
                    if age_seconds < 3600:  # Within last hour
                        return {
                            "status": "running",
                            "activity": "Bot active (inferred from recent windows)",
                            "last_scan": str(last_window),
                            "updated_at": str(last_window),
                            "last_window": str(last_window)
                        }
                except Exception as e:
                    logger.error(f"[BOT-STATUS] Error parsing last_window: {e}", exc_info=True)
                    pass
            
            db.close()
            return {
                "status": "unknown",
                "activity": "No heartbeat recorded yet",
                "last_scan": None,
                "updated_at": None,
                "last_window": last_window
            }
        
        # Parse last_heartbeat timestamp
        last_heartbeat_str = bot_status.get("last_heartbeat")
        last_heartbeat = None
        if last_heartbeat_str:
            try:
                if isinstance(last_heartbeat_str, str):
                    heartbeat_str = last_heartbeat_str.replace("Z", "+00:00") if "Z" in last_heartbeat_str else last_heartbeat_str
                    if "+" not in heartbeat_str and "-" not in heartbeat_str[-6:]:
                        heartbeat_str = heartbeat_str + "+00:00"
                    last_heartbeat = datetime.fromisoformat(heartbeat_str)
                else:
                    # Already a datetime object
                    last_heartbeat = last_heartbeat_str
                
                # Ensure timezone-aware
                if last_heartbeat.tzinfo is None:
                    last_heartbeat = last_heartbeat.replace(tzinfo=timezone.utc)
            except Exception as e:
                logger.error(f"[BOT-STATUS] Error parsing last_heartbeat: {e}", exc_info=True)
                last_heartbeat = None
        
        # Determine if bot is online (heartbeat within last 2 minutes)
        status = bot_status.get("status", "unknown")
        if last_heartbeat:
            age_seconds = (datetime.now(timezone.utc) - last_heartbeat).total_seconds()
            if age_seconds > 120:  # No heartbeat in 2 minutes
                status = "offline"
        
        # Format activity message
        current_window = bot_status.get("current_window", "")
        error_message = bot_status.get("error_message")
        
        if error_message:
            activity = f"Error: {error_message[:50]}"
        elif current_window:
            activity = current_window
        else:
            activity = status.capitalize()
        
        db.close()
        
        return {
            "status": status,
            "activity": activity,
            "last_scan": last_heartbeat_str if last_heartbeat else None,
            "updated_at": last_heartbeat_str if last_heartbeat else None,
            "current_window": current_window,
            "error_message": error_message,
            "last_window": last_window
        }
    except Exception as e:
        logger.error(f"Error in bot-status endpoint: {e}", exc_info=True)
        # Return safe fallback response
        return {
            "status": "unknown",
            "activity": f"Error: {str(e)[:50]}",
            "last_scan": None,
            "updated_at": None,
            "current_window": None,
            "error_message": str(e),
            "last_window": None
        }


# Rate limiting for restart (prevent spam)
_last_restart_time = {}
RESTART_COOLDOWN_SECONDS = 60  # Minimum 60 seconds between restarts

async def get_latest_deployment_id(railway_token: str, service_id: str):
    """Get the latest deployment ID for this service."""
    graphql_url = "https://backboard.railway.app/graphql/v2"
    headers = {
        "Authorization": f"Bearer {railway_token}",
        "Content-Type": "application/json"
    }
    
    query = """
    query($serviceId: String!) {
      deployments(first: 1, input: { serviceId: $serviceId }) {
        edges {
          node {
            id
            status
          }
        }
      }
    }
    """
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                graphql_url,
                json={"query": query, "variables": {"serviceId": service_id}},
                headers=headers,
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                edges = data.get("data", {}).get("deployments", {}).get("edges", [])
                if edges:
                    return edges[0]["node"]["id"]
    except Exception as e:
        logger.error(f"Error getting deployment ID: {e}")
    return None


async def restart_deployment(railway_token: str, service_id: str) -> dict:
    """Restart the current Railway deployment."""
    deployment_id = await get_latest_deployment_id(railway_token, service_id)
    if not deployment_id:
        return {"success": False, "error": "Could not find deployment"}
    
    graphql_url = "https://backboard.railway.app/graphql/v2"
    headers = {
        "Authorization": f"Bearer {railway_token}",
        "Content-Type": "application/json"
    }
    
    mutation = """
    mutation($id: String!) {
      deploymentRestart(id: $id)
    }
    """
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                graphql_url,
                json={"query": mutation, "variables": {"id": deployment_id}},
                headers=headers,
                timeout=10
            )
            if resp.status_code == 200:
                return {"success": True, "deployment_id": deployment_id}
            else:
                return {"success": False, "error": f"Railway API returned {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/bot-control", dependencies=[Depends(require_api_key)])
async def api_bot_control(action: str):
    """Control bot (start/stop/restart) using Railway API"""
    import time
    
    result = {
        "status": "success",
        "message": "",
        "action": action
    }
    
    try:
        if action == "restart":
            # Rate limiting - prevent spam restarts
            import time
            current_time = time.time()
            if action in _last_restart_time:
                time_since_last = current_time - _last_restart_time[action]
                if time_since_last < RESTART_COOLDOWN_SECONDS:
                    remaining = int(RESTART_COOLDOWN_SECONDS - time_since_last)
                    result["status"] = "error"
                    result["message"] = f"⏳ Please wait {remaining} seconds before restarting again (rate limit)"
                    return result
            
            # Railway auto-injects RAILWAY_SERVICE_ID for the current service
            # For bot restart, we need BOT_SERVICE_ID (bot service) or fallback to RAILWAY_SERVICE_ID
            railway_token = os.getenv("RAILWAY_TOKEN", "")
            # Prefer BOT_SERVICE_ID if set (for split services), otherwise use current service ID
            service_id = os.getenv("BOT_SERVICE_ID") or os.getenv("RAILWAY_SERVICE_ID", "")
            
            if not railway_token:
                result["status"] = "info"
                result["message"] = "⚠️ Railway API not configured.\n\nTo enable restart:\n1. Go to https://railway.app/account → Tokens → Create Token\n2. Use a project-scoped token (not account-wide)\n3. Set RAILWAY_TOKEN environment variable in Railway\n4. Set BOT_SERVICE_ID to bot service ID (if services are split)\n5. Restart Railway service once to load the variable"
                return result
            
            if not service_id:
                result["status"] = "error"
                result["message"] = "⚠️ Service ID not found.\n\nIf services are split:\n- Set BOT_SERVICE_ID to bot service ID\n- Or set RAILWAY_SERVICE_ID (auto-injected if bot and dashboard are same service)"
                return result
            
            # Log restart attempt (mask token for security)
            token_display = railway_token[:10] + "..." if len(railway_token) > 10 else "***"
            logger.info(f"Bot restart triggered from dashboard (token: {token_display})")
            
            # Restart deployment
            restart_result = await restart_deployment(railway_token, service_id)
            
            if restart_result.get("success"):
                _last_restart_time[action] = current_time
                deployment_id = restart_result.get("deployment_id", "unknown")
                result["message"] = f"✅ Bot restart initiated via Railway API.\n\nDeployment ID: {deployment_id[:20]}...\nThis may take 30-60 seconds."
            else:
                error = restart_result.get("error", "Unknown error")
                result["status"] = "error"
                result["message"] = f"❌ Failed to restart: {error}\n\nPlease restart manually via Railway dashboard → Service → Restart"
        
        elif action == "stop":
            result["status"] = "info"
            result["message"] = "To stop the bot:\n1. Go to Railway dashboard → Service → Settings → Stop\n2. Or set PAPER_MODE=true environment variable to pause trading"
        
        elif action == "start":
            result["status"] = "info"
            result["message"] = "To start the bot:\n1. Go to Railway dashboard → Service → Settings → Start\n2. The bot starts automatically on deployment"
        
        else:
            result["status"] = "error"
            result["message"] = f"Unknown action: {action}"
    
    except Exception as e:
        logger.error(f"Error in bot control: {e}")
        result["status"] = "error"
        result["message"] = f"Error: {str(e)}"
    
    return result


@app.get("/api/scan", dependencies=[Depends(require_api_key)])
def api_scan():
    """Live scan — hit Polymarket Gamma API right now and return qualifying markets."""
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(minutes=60)

    params = {
        "active": "true",
        "closed": "false",
        "end_date_min": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_date_max": window_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": 100,
        "order": "volume24hr",
        "ascending": "false",
    }

    try:
        resp = httpx.get(f"{GAMMA_URL}/markets", params=params, timeout=15)
        resp.raise_for_status()
        raw = resp.json() if isinstance(resp.json(), list) else []
    except Exception as e:
        return {"error": str(e), "markets": [], "total_raw": 0}

    candidates = []
    for m in raw:
        try:
            question = m.get("question", "")
            end_str = m.get("endDate") or m.get("endDateIso", "")
            if not end_str or not question:
                continue

            # Parse end date
            end_date = None
            for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"]:
                try:
                    end_date = datetime.strptime(end_str, fmt).replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    continue
            if not end_date:
                continue

            mins = (end_date - now).total_seconds() / 60
            if mins <= 0:
                continue

            # Parse prices
            prices_str = m.get("outcomePrices", "")
            try:
                if prices_str.startswith("["):
                    prices = [float(p) for p in json.loads(prices_str)]
                else:
                    prices = [float(p.strip().strip('"')) for p in prices_str.split(",")]
            except:
                continue
            if len(prices) < 2:
                continue

            yes_p, no_p = prices[0], prices[1]
            volume = float(m.get("volume", 0) or 0)
            vol24 = float(m.get("volume24hr", 0) or 0)
            category = m.get("category", "")

            # Check favorite qualification
            fav_side = fav_price = None
            if 0.70 <= yes_p <= 0.90:
                fav_side, fav_price = "YES", yes_p
            elif 0.70 <= no_p <= 0.90:
                fav_side, fav_price = "NO", no_p

            candidates.append({
                "question": question,
                "category": category,
                "end_date": end_str,
                "minutes_to_expiry": round(mins, 1),
                "yes_price": round(yes_p, 3),
                "no_price": round(no_p, 3),
                "fav_side": fav_side,
                "fav_price": round(fav_price, 3) if fav_price else None,
                "qualifies": fav_side is not None and volume >= 5000,
                "volume": round(volume, 0),
                "volume_24h": round(vol24, 0),
                "slug": m.get("slug", ""),
            })
        except Exception:
            continue

    candidates.sort(key=lambda x: x["volume"], reverse=True)

    return {
        "scanned_at": now.isoformat(),
        "window_end": window_end.isoformat(),
        "total_raw": len(raw),
        "total_parsed": len(candidates),
        "qualifying": len([c for c in candidates if c["qualifies"]]),
        "markets": candidates,
    }


# ─── Live Terminal API Endpoints ────────────────────────────────────────────

@app.get("/api/live/markets")
async def api_live_markets():
    """Get live markets being scanned/traded"""
    try:
        conn = get_db()
        # Get recent bets (last 30 minutes) to show which markets are being traded
        # Note: placed_at is stored as TEXT (ISO format), so we compare as strings or convert
        # For simplicity, get last 50 bets and filter in Python (more reliable)
        try:
            query = """
                SELECT DISTINCT market_question, side, price, market_id, placed_at
                FROM bets
                ORDER BY placed_at DESC
                LIMIT 50
            """
            c = conn.cursor()
            c.execute(query)
            rows = c.fetchall()
        except Exception as db_error:
            logger.warning(f"Database query failed (table might not exist yet): {db_error}")
            rows = []
        finally:
            try:
                conn.close()
            except:
                pass
        
        # Filter to last 30 minutes
        from datetime import datetime, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        
        markets = []
        for row in rows:
            # Handle both dict-like (PostgreSQL RealDictRow) and tuple-like (SQLite Row)
            if isinstance(row, dict):
                market_question = row.get("market_question", "")
                side = row.get("side", "")
                price = float(row.get("price", 0))
                market_id = row.get("market_id", "")
                placed_at_str = row.get("placed_at", "")
            else:
                market_question = row[0] if len(row) > 0 else ""
                side = row[1] if len(row) > 1 else ""
                price = float(row[2]) if len(row) > 2 else 0.0
                market_id = row[3] if len(row) > 3 else ""
                placed_at_str = row[4] if len(row) > 4 else ""
            
            # Parse placed_at and filter by time
            try:
                if placed_at_str:
                    placed_at_dt = datetime.fromisoformat(placed_at_str.replace('Z', '+00:00'))
                    if placed_at_dt < cutoff:
                        continue
            except:
                pass  # Include if we can't parse
            
            markets.append({
                "market_question": market_question,
                "side": side,
                "price": price,
                "market_id": market_id,
                "placed_at": placed_at_str,
            })
        
        return {"markets": markets, "count": len(markets)}
    except Exception as e:
        logger.error(f"Error fetching live markets: {e}")
        return {"markets": [], "count": 0, "error": str(e)}


@app.get("/api/live/positions")
async def api_live_positions():
    """Get open positions with live P&L"""
    try:
        conn = get_db()
        # Get pending bets (open positions)
        try:
            query = """
                SELECT market_question, side, price, amount, placed_at, market_id, result
                FROM bets
                WHERE result = 'pending'
                ORDER BY placed_at DESC
            """
            c = conn.cursor()
            c.execute(query)
            rows = c.fetchall()
        except Exception as db_error:
            logger.warning(f"Database query failed (table might not exist yet): {db_error}")
            rows = []
        finally:
            try:
                conn.close()
            except:
                pass
        
        positions = []
        for row in rows:
            # Handle both dict-like (PostgreSQL RealDictRow) and tuple-like (SQLite Row)
            if isinstance(row, dict):
                market_question = row.get("market_question", "")
                side = row.get("side", "")
                price = float(row.get("price", 0))
                amount = float(row.get("amount", 0))
                placed_at = row.get("placed_at", "")
            else:
                market_question = row[0] if len(row) > 0 else ""
                side = row[1] if len(row) > 1 else ""
                price = float(row[2]) if len(row) > 2 else 0.0
                amount = float(row[3]) if len(row) > 3 else 0.0
                placed_at = row[4] if len(row) > 4 else ""
            
            # Calculate unrealized P&L (simplified - assume current price = entry price for now)
            # In production, you'd fetch current market price
            positions.append({
                "market_question": market_question,
                "market": market_question,
                "side": side,
                "entry_price": price,
                "price": price,
                "amount": amount,
                "pnl": 0.0,  # Would calculate from current market price
                "profit": 0.0,
                "status": "open",
                "placed_at": placed_at,
            })
        
        return {"positions": positions, "count": len(positions)}
    except Exception as e:
        logger.error(f"Error fetching live positions: {e}")
        return {"positions": [], "count": 0, "error": str(e)}


@app.get("/api/live/activity")
async def api_live_activity():
    """Get recent trading activity"""
    try:
        conn = get_db()
        # Get recent bets (last 50)
        try:
            query = """
                SELECT market_question, side, price, amount, placed_at, result, profit, market_id
                FROM bets
                ORDER BY placed_at DESC
                LIMIT 50
            """
            c = conn.cursor()
            c.execute(query)
            rows = c.fetchall()
        except Exception as db_error:
            logger.warning(f"Database query failed (table might not exist yet): {db_error}")
            rows = []
        finally:
            try:
                conn.close()
            except:
                pass
        
        activity = []
        for row in rows:
            # Handle both dict-like (PostgreSQL RealDictRow) and tuple-like (SQLite Row)
            if isinstance(row, dict):
                market_question = row.get("market_question", "")
                side = row.get("side", "")
                price = float(row.get("price", 0))
                amount = float(row.get("amount", 0))
                placed_at = row.get("placed_at", "")
                result = row.get("result", "pending")
                profit = float(row.get("profit", 0))
            else:
                market_question = row[0] if len(row) > 0 else ""
                side = row[1] if len(row) > 1 else ""
                price = float(row[2]) if len(row) > 2 else 0.0
                amount = float(row[3]) if len(row) > 3 else 0.0
                placed_at = row[4] if len(row) > 4 else ""
                result = row[5] if len(row) > 5 else "pending"
                profit = float(row[6]) if len(row) > 6 else 0.0
            
            activity.append({
                "market_question": market_question,
                "market": market_question,
                "side": side,
                "type": "buy" if result == "pending" else ("sell" if result == "won" else "settle"),
                "price": price,
                "amount": amount,
                "pnl": profit,
                "result": result,
                "placed_at": placed_at,
                "timestamp": placed_at,
            })
        
        return {"activity": activity, "count": len(activity)}
    except Exception as e:
        logger.error(f"Error fetching live activity: {e}")
        return {"activity": [], "count": 0, "error": str(e)}


@app.get("/api/live/stats")
async def api_live_stats():
    """Get live stats (P&L, win rate, etc.)"""
    try:
        # Reuse existing stats endpoint logic
        conn = get_db()
        
        # Get basic stats
        if is_postgres(conn):
            total_bets_query = "SELECT COUNT(*) as cnt FROM bets"
            total_profit_query = "SELECT COALESCE(SUM(profit), 0) as total FROM bets WHERE result IN ('won', 'lost')"
            wins_query = "SELECT COUNT(*) as cnt FROM bets WHERE result = 'won'"
            losses_query = "SELECT COUNT(*) as cnt FROM bets WHERE result = 'lost'"
            pending_query = "SELECT COUNT(*) as cnt FROM bets WHERE result = 'pending'"
            cash_query = "SELECT COALESCE(SUM(amount), 0) as total FROM bets WHERE result = 'pending'"
        else:
            total_bets_query = "SELECT COUNT(*) as cnt FROM bets"
            total_profit_query = "SELECT COALESCE(SUM(profit), 0) as total FROM bets WHERE result IN ('won', 'lost')"
            wins_query = "SELECT COUNT(*) as cnt FROM bets WHERE result = 'won'"
            losses_query = "SELECT COUNT(*) as cnt FROM bets WHERE result = 'lost'"
            pending_query = "SELECT COUNT(*) as cnt FROM bets WHERE result = 'pending'"
            cash_query = "SELECT COALESCE(SUM(amount), 0) as total FROM bets WHERE result = 'pending'"
        
        c = conn.cursor()
        
        try:
            c.execute(total_bets_query)
            total_bets_row = c.fetchone()
            total_bets = total_bets_row[0] if total_bets_row else 0
            if isinstance(total_bets_row, dict):
                total_bets = total_bets_row.get("cnt", 0)
            
            c.execute(total_profit_query)
            total_profit_row = c.fetchone()
            total_profit = float(total_profit_row[0] if total_profit_row else 0)
            if isinstance(total_profit_row, dict):
                total_profit = float(total_profit_row.get("total", 0))
            
            c.execute(wins_query)
            wins_row = c.fetchone()
            wins = wins_row[0] if wins_row else 0
            if isinstance(wins_row, dict):
                wins = wins_row.get("cnt", 0)
            
            c.execute(losses_query)
            losses_row = c.fetchone()
            losses = losses_row[0] if losses_row else 0
            if isinstance(losses_row, dict):
                losses = losses_row.get("cnt", 0)
            
            c.execute(pending_query)
            pending_row = c.fetchone()
            open_positions = pending_row[0] if pending_row else 0
            if isinstance(pending_row, dict):
                open_positions = pending_row.get("cnt", 0)
            
            c.execute(cash_query)
            cash_row = c.fetchone()
            locked_cash = float(cash_row[0] if cash_row else 0)
            if isinstance(cash_row, dict):
                locked_cash = float(cash_row.get("total", 0))
        except Exception as db_error:
            logger.warning(f"Database query failed (table might not exist yet): {db_error}")
            total_bets = 0
            total_profit = 0.0
            wins = 0
            losses = 0
            open_positions = 0
            locked_cash = 0.0
        
        # Get bot status
        bot_status = "unknown"
        try:
            if is_postgres(conn):
                status_query = "SELECT status FROM bot_status ORDER BY updated_at DESC LIMIT 1"
            else:
                status_query = "SELECT status FROM bot_status ORDER BY updated_at DESC LIMIT 1"
            c.execute(status_query)
            status_row = c.fetchone()
            if status_row:
                bot_status = status_row[0] if isinstance(status_row, dict) else status_row.get("status", "unknown")
        except:
            pass
        
        try:
            conn.close()
        except:
            pass
        
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        
        return {
            "total_pnl": total_profit,
            "net_pnl": total_profit,
            "win_rate": win_rate,
            "open_positions": open_positions,
            "current_cash": 100.0 - locked_cash,  # Simplified - would get from actual balance
            "cash_balance": 100.0 - locked_cash,
            "status": bot_status,
            "bot_status": bot_status,
            "wins": wins,
            "losses": losses,
            "total_bets": total_bets,
        }
    except Exception as e:
        logger.error(f"Error fetching live stats: {e}")
        return {
            "total_pnl": 0,
            "net_pnl": 0,
            "win_rate": 0,
            "open_positions": 0,
            "current_cash": 0,
            "cash_balance": 0,
            "status": "error",
            "bot_status": "error",
            "error": str(e),
        }


# ─── Dashboard HTML ────────────────────────────────────────────

@app.get("/pnl", response_class=HTMLResponse)
def pnl_page():
    """P&L Cash Flow page"""
    return """<!DOCTYPE html>
<html><body><h1>P&L Flow</h1><p>Coming soon - will show detailed P&L flow</p></body></html>"""


# ─── Trading Terminal HTML ────────────────────────────────────────────

TERMINAL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vig Trading Terminal</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #0a0b0e; --surface: #12131a; --surface2: #1a1c25;
  --border: #252833; --text: #e4e6ed; --text-dim: #6b7084;
  --green: #00e676; --green-dim: rgba(0,230,118,0.12);
  --red: #ff5252; --red-dim: rgba(255,82,82,0.12);
  --blue: #448aff; --blue-dim: rgba(68,138,255,0.12);
  --cyan: #18ffff; --cyan-dim: rgba(24,255,255,0.12);
  --font-mono: 'JetBrains Mono', monospace;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--bg); color:var(--text); font-family:var(--font-mono); font-size:12px; line-height:1.5; overflow:hidden; }
.header { display:flex; align-items:center; justify-content:space-between; padding:12px 20px; border-bottom:1px solid var(--border); background:var(--surface); }
.logo { font-size:18px; font-weight:700; }
.logo span { color:var(--green); }
.status-badge { display:inline-flex; align-items:center; gap:6px; padding:4px 10px; border-radius:16px; font-size:10px; font-weight:500; }
.status-badge.live { background:var(--green-dim); color:var(--green); }
.status-badge.offline { background:var(--red-dim); color:var(--red); }
.status-dot { width:6px; height:6px; border-radius:50%; background:currentColor; animation:pulse 2s ease-in-out infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
.container { display:grid; grid-template-columns:1fr 1fr; grid-template-rows:auto 1fr auto; gap:12px; padding:12px; height:calc(100vh - 50px); }
.panel { background:var(--surface); border:1px solid var(--border); border-radius:6px; padding:12px; overflow:hidden; display:flex; flex-direction:column; }
.panel-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; font-size:10px; text-transform:uppercase; letter-spacing:1px; color:var(--text-dim); font-weight:600; }
.panel-content { flex:1; overflow-y:auto; }
.stats-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin-bottom:12px; }
.stat { background:var(--surface2); padding:8px; border-radius:4px; }
.stat-label { font-size:9px; color:var(--text-dim); text-transform:uppercase; margin-bottom:4px; }
.stat-value { font-size:16px; font-weight:600; }
.stat-value.positive { color:var(--green); }
.stat-value.negative { color:var(--red); }
table { width:100%; border-collapse:collapse; font-size:11px; }
th { text-align:left; padding:6px 8px; font-size:9px; text-transform:uppercase; color:var(--text-dim); font-weight:600; border-bottom:1px solid var(--border); position:sticky; top:0; background:var(--surface); }
td { padding:6px 8px; border-bottom:1px solid var(--border); }
tr:hover td { background:rgba(255,255,255,0.02); }
.tag { display:inline-block; padding:2px 6px; border-radius:3px; font-size:9px; font-weight:600; }
.tag.yes { background:var(--green-dim); color:var(--green); }
.tag.no { background:var(--red-dim); color:var(--red); }
.tag.open { background:var(--blue-dim); color:var(--blue); }
.tag.won { background:var(--green-dim); color:var(--green); }
.tag.lost { background:var(--red-dim); color:var(--red); }
.tag.pending { background:var(--surface2); color:var(--text-dim); }
.footer { grid-column:1/-1; padding:8px 20px; border-top:1px solid var(--border); background:var(--surface); font-size:10px; color:var(--text-dim); display:flex; justify-content:space-between; }
.market-name { max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.activity-item { padding:6px 0; border-bottom:1px solid var(--border); font-size:11px; }
.activity-item:last-child { border-bottom:none; }
.time { color:var(--text-dim); font-size:9px; }
</style>
</head>
<body>
<div class="header">
  <div class="logo">V<span>ig</span> Terminal</div>
  <div class="status-badge offline" id="statusBadge"><div class="status-dot"></div><span id="statusText">Loading...</span></div>
</div>
<div class="container">
  <div class="panel" style="grid-column:1/-1;">
    <div class="panel-header">Live Stats</div>
    <div class="stats-grid">
      <div class="stat"><div class="stat-label">Total P&L</div><div class="stat-value" id="totalPnl">--</div></div>
      <div class="stat"><div class="stat-label">Win Rate</div><div class="stat-value" id="winRate">--</div></div>
      <div class="stat"><div class="stat-label">Open Positions</div><div class="stat-value" id="openPositions">--</div></div>
      <div class="stat"><div class="stat-label">Cash Balance</div><div class="stat-value" id="cashBalance">--</div></div>
    </div>
  </div>
  <div class="panel">
    <div class="panel-header">Live Markets</div>
    <div class="panel-content">
      <table id="marketsTable">
        <thead><tr><th>Market</th><th>Side</th><th>Price</th><th>Expiry</th></tr></thead>
        <tbody><tr><td colspan="4" style="text-align:center;padding:20px;color:var(--text-dim);">Loading markets...</td></tr></tbody>
      </table>
    </div>
  </div>
  <div class="panel">
    <div class="panel-header">Open Positions</div>
    <div class="panel-content">
      <table id="positionsTable">
        <thead><tr><th>Market</th><th>Side</th><th>Entry</th><th>P&L</th><th>Status</th></tr></thead>
        <tbody><tr><td colspan="5" style="text-align:center;padding:20px;color:var(--text-dim);">No open positions</td></tr></tbody>
      </table>
    </div>
  </div>
  <div class="panel" style="grid-column:1/-1;">
    <div class="panel-header">Recent Activity</div>
    <div class="panel-content" id="activityList">
      <div style="text-align:center;padding:20px;color:var(--text-dim);">Loading activity...</div>
    </div>
  </div>
</div>
<div class="footer">
  <span>Last update: <span id="lastUpdate">--</span></span>
  <span>Auto-refresh: <span id="refreshCountdown">2s</span></span>
</div>
<script>
let refreshInterval;
let countdown = 2;

async function fetchJSON(url) {
  try {
    const r = await fetch(url);
    if (!r.ok) return null;
    return await r.json();
  } catch(e) {
    console.error(`Fetch error: ${url}`, e);
    return null;
  }
}

function fmt(n) {
  if (n == null) return '--';
  const sign = n >= 0 ? '+' : '';
  return sign + '$' + Math.abs(n).toFixed(2);
}

function timeAgo(iso) {
  if (!iso) return '--';
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return Math.floor(s) + 's ago';
  if (s < 3600) return Math.floor(s/60) + 'm ago';
  return Math.floor(s/3600) + 'h ago';
}

function updateMarkets(data) {
  const tbody = document.querySelector('#marketsTable tbody');
  if (!data || !data.markets || data.markets.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:20px;color:var(--text-dim);">No markets being scanned</td></tr>';
    return;
  }
  let html = '';
  for (const m of data.markets.slice(0, 20)) {
    const name = (m.question || m.market_question || '').substring(0, 40) + '...';
    html += '<tr>';
    html += '<td class="market-name" title="' + (m.question || m.market_question || '') + '">' + name + '</td>';
    html += '<td><span class="tag ' + (m.side === 'YES' ? 'yes' : 'no') + '">' + (m.side || '--') + '</span></td>';
    html += '<td>$' + (m.price || 0).toFixed(2) + '</td>';
    html += '<td>' + (m.minutes_to_expiry || '--') + 'm</td>';
    html += '</tr>';
  }
  tbody.innerHTML = html;
}

function updatePositions(data) {
  const tbody = document.querySelector('#positionsTable tbody');
  if (!data || !data.positions || data.positions.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--text-dim);">No open positions</td></tr>';
    return;
  }
  let html = '';
  for (const p of data.positions) {
    const name = (p.market_question || p.market || '').substring(0, 30) + '...';
    const pnl = p.pnl || p.profit || 0;
    html += '<tr>';
    html += '<td class="market-name" title="' + (p.market_question || p.market || '') + '">' + name + '</td>';
    html += '<td><span class="tag ' + (p.side === 'YES' ? 'yes' : 'no') + '">' + (p.side || '--') + '</span></td>';
    html += '<td>$' + (p.entry_price || p.price || 0).toFixed(2) + '</td>';
    html += '<td class="stat-value ' + (pnl >= 0 ? 'positive' : 'negative') + '">' + fmt(pnl) + '</td>';
    html += '<td><span class="tag ' + (p.status || 'open') + '">' + (p.status || 'open').toUpperCase() + '</span></td>';
    html += '</tr>';
  }
  tbody.innerHTML = html;
}

function updateActivity(data) {
  const el = document.getElementById('activityList');
  if (!data || !data.activity || data.activity.length === 0) {
    el.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-dim);">No recent activity</div>';
    return;
  }
  let html = '';
  for (const a of data.activity.slice(0, 15)) {
    const name = (a.market_question || a.market || '').substring(0, 50) + '...';
    html += '<div class="activity-item">';
    html += '<div style="display:flex;justify-content:space-between;margin-bottom:4px;">';
    html += '<span><span class="tag ' + (a.type === 'buy' ? 'yes' : a.type === 'sell' ? 'no' : 'pending') + '">' + (a.type || 'bet').toUpperCase() + '</span> ' + name + '</span>';
    html += '<span class="stat-value ' + (a.pnl >= 0 ? 'positive' : 'negative') + '">' + fmt(a.pnl || a.amount || 0) + '</span>';
    html += '</div>';
    html += '<div class="time">' + timeAgo(a.timestamp || a.placed_at) + '</div>';
    html += '</div>';
  }
  el.innerHTML = html;
}

function updateStats(data) {
  if (!data) return;
  const pnl = data.total_pnl || data.net_pnl || 0;
  document.getElementById('totalPnl').textContent = fmt(pnl);
  document.getElementById('totalPnl').className = 'stat-value ' + (pnl >= 0 ? 'positive' : 'negative');
  document.getElementById('winRate').textContent = (data.win_rate || 0).toFixed(1) + '%';
  document.getElementById('openPositions').textContent = data.open_positions || 0;
  document.getElementById('cashBalance').textContent = fmt(data.current_cash || data.cash_balance || 0);
  
  const badge = document.getElementById('statusBadge');
  const statusText = document.getElementById('statusText');
  if (data.status === 'running' || data.bot_status === 'running') {
    badge.className = 'status-badge live';
    statusText.textContent = 'Live';
  } else {
    badge.className = 'status-badge offline';
    statusText.textContent = 'Offline';
  }
}

async function refresh() {
  const [markets, positions, activity, stats] = await Promise.all([
    fetchJSON('/api/live/markets'),
    fetchJSON('/api/live/positions'),
    fetchJSON('/api/live/activity'),
    fetchJSON('/api/live/stats')
  ]);
  
  if (markets) updateMarkets(markets);
  if (positions) updatePositions(positions);
  if (activity) updateActivity(activity);
  if (stats) updateStats(stats);
  
  document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
}

function startRefresh() {
  refresh();
  refreshInterval = setInterval(() => {
    countdown--;
    document.getElementById('refreshCountdown').textContent = countdown + 's';
    if (countdown <= 0) {
      countdown = 2;
      refresh();
    }
  }, 1000);
}

startRefresh();
</script>
</body>
</html>"""

@app.get("/terminal", response_class=HTMLResponse)
def terminal():
    """Trading Terminal UI - Live markets and P&L"""
    return TERMINAL_HTML

@app.get("/", response_class=HTMLResponse)
def dashboard():
    # Get wallet address from config
    from config import Config
    config = Config()
    wallet_address = config.funder_address or "0x989B7F2308924eA72109367467B8F8e4d5ea5A1D"
    
    # Load professional template
    try:
        from dashboard_professional_template import PROFESSIONAL_DASHBOARD_HTML
        html_template = PROFESSIONAL_DASHBOARD_HTML.replace("{{WALLET_ADDRESS}}", wallet_address)
        return html_template
    except ImportError:
        # Fallback: return basic message if template not found
        return f"""<!DOCTYPE html><html><body><h1>Dashboard Loading...</h1><p>Template not found. Wallet: {wallet_address}</p><p><a href="/terminal">Go to Trading Terminal</a></p></body></html>"""


@app.get("/pnl", response_class=HTMLResponse)
def pnl_page():
    """P&L Cash Flow Table Page"""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>P&L Cash Flow — Vig Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #0a0b0e; --surface: #12131a; --surface2: #1a1c25;
  --border: #252833; --text: #e4e6ed; --text-dim: #6b7084;
  --green: #00e676; --green-dim: rgba(0,230,118,0.12);
  --red: #ff5252; --red-dim: rgba(255,82,82,0.12);
  --amber: #ffd740; --amber-dim: rgba(255,215,64,0.12);
  --blue: #448aff; --blue-dim: rgba(68,138,255,0.12);
  --cyan: #18ffff; --cyan-dim: rgba(24,255,255,0.12);
  --font-mono: 'JetBrains Mono', monospace;
  --font-display: 'Space Grotesk', sans-serif;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--bg); color:var(--text); font-family:var(--font-mono); font-size:13px; line-height:1.5; min-height:100vh; }
.header { display:flex; align-items:center; justify-content:space-between; padding:16px 24px; border-bottom:1px solid var(--border); background:var(--surface); }
.header-left { display:flex; align-items:center; gap:16px; }
.logo { font-family:var(--font-display); font-size:22px; font-weight:700; letter-spacing:-0.5px; }
.logo span { color:var(--green); }
.logo a { color:inherit; text-decoration:none; }
.nav-link { color:var(--text-dim); text-decoration:none; font-size:12px; padding:4px 12px; border-radius:4px; transition:all 0.2s; }
.nav-link:hover { background:var(--surface2); color:var(--text); }
.tabs { display:flex; gap:8px; margin-bottom:20px; border-bottom:1px solid var(--border); }
.tab { padding:10px 20px; font-size:12px; font-weight:500; color:var(--text-dim); cursor:pointer; border-bottom:2px solid transparent; transition:all 0.2s; text-transform:uppercase; letter-spacing:0.5px; }
.tab:hover { color:var(--text); }
.tab.active { color:var(--cyan); border-bottom-color:var(--cyan); }
.tab-content { display:none; }
.tab-content.active { display:block; }
.status-badge { display:inline-flex; align-items:center; gap:6px; padding:4px 12px; border-radius:20px; font-size:11px; font-weight:500; text-transform:uppercase; letter-spacing:0.5px; }
.status-badge.paper { background:var(--amber-dim); color:var(--amber); }
.status-badge.live { background:var(--green-dim); color:var(--green); }
.status-badge.offline { background:var(--red-dim); color:var(--red); }
.status-badge.error { background:var(--red-dim); color:var(--red); }
.status-dot { width:6px; height:6px; border-radius:50%; background:currentColor; animation:pulse 2s ease-in-out infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
.bot-status-info { padding:12px 0; }
.bot-activity, .bot-last-scan, .bot-last-window { margin-bottom:8px; font-size:12px; }
.bot-activity strong, .bot-last-scan strong, .bot-last-window strong { color:var(--text-dim); margin-right:8px; }
.bot-note { margin-top:12px; padding-top:12px; border-top:1px solid var(--border); font-size:11px; color:var(--text-dim); line-height:1.5; }
.card-actions { display:flex; align-items:center; gap:8px; }
.header-right { display:flex; align-items:center; gap:16px; }
.refresh-label { color:var(--text-dim); font-size:11px; }
.countdown { font-size:12px; color:var(--cyan); font-weight:500; }
.container { padding:20px 24px; max-width:1440px; margin:0 auto; }
.grid { display:grid; gap:16px; margin-bottom:16px; }
.grid-4 { grid-template-columns:repeat(4,1fr); }
.grid-3 { grid-template-columns:repeat(3,1fr); }
.grid-2 { grid-template-columns:1fr 1fr; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:16px 20px; }
.card-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.card-title { font-size:11px; text-transform:uppercase; letter-spacing:1px; color:var(--text-dim); font-weight:500; }
.card-value { font-family:var(--font-display); font-size:28px; font-weight:700; letter-spacing:-1px; }
.card-sub { font-size:11px; color:var(--text-dim); margin-top:4px; }
.positive { color:var(--green); }
.negative { color:var(--red); }
.neutral { color:var(--text-dim); }
.snowball-track { width:100%; height:8px; background:var(--surface2); border-radius:4px; margin:12px 0 8px; overflow:hidden; }
.snowball-fill { height:100%; border-radius:4px; transition:width 0.6s ease; }
.snowball-fill.growth { background:linear-gradient(90deg,var(--blue),var(--green)); }
.snowball-fill.harvest { background:linear-gradient(90deg,var(--green),var(--amber)); }
.snowball-labels { display:flex; justify-content:space-between; font-size:11px; color:var(--text-dim); }
.table-wrap { overflow-x:auto; max-height:400px; overflow-y:auto; }
table { width:100%; border-collapse:collapse; font-size:12px; }
th { text-align:left; padding:8px 12px; font-size:10px; text-transform:uppercase; letter-spacing:0.8px; color:var(--text-dim); font-weight:500; border-bottom:1px solid var(--border); white-space:nowrap; position:sticky; top:0; background:var(--surface); }
td { padding:8px 12px; border-bottom:1px solid var(--border); white-space:nowrap; }
tr:hover td { background:rgba(255,255,255,0.02); }
.tag { display:inline-block; padding:2px 8px; border-radius:4px; font-size:10px; font-weight:600; text-transform:uppercase; }
.tag.won { background:var(--green-dim); color:var(--green); }
.tag.lost { background:var(--red-dim); color:var(--red); }
.tag.pending { background:var(--blue-dim); color:var(--blue); }
.tag.growth { background:var(--blue-dim); color:var(--blue); }
.tag.harvest { background:var(--amber-dim); color:var(--amber); }
.tag.yes { background:var(--green-dim); color:var(--green); }
.tag.no { background:var(--red-dim); color:var(--red); }
.tag.qual { background:var(--green-dim); color:var(--green); }
.tag.skip { background:var(--surface2); color:var(--text-dim); }
.chart-container { width:100%; height:200px; position:relative; }
canvas { width:100%!important; height:100%!important; }
.cb-status { display:flex; align-items:center; gap:8px; padding:10px 14px; border-radius:6px; font-size:12px; font-weight:500; }
.cb-ok { background:var(--green-dim); color:var(--green); }
.cb-warn { background:var(--amber-dim); color:var(--amber); }
.cb-stop { background:var(--red-dim); color:var(--red); }
.empty { text-align:center; padding:40px; color:var(--text-dim); }
.empty-icon { font-size:32px; margin-bottom:8px; opacity:0.4; }
.btn { display:inline-flex; align-items:center; gap:6px; padding:6px 14px; border-radius:6px; font-size:11px; font-weight:600; font-family:var(--font-mono); cursor:pointer; border:1px solid var(--border); background:var(--surface2); color:var(--text); transition:all 0.15s; text-transform:uppercase; letter-spacing:0.5px; }
.btn:hover { background:var(--border); border-color:var(--text-dim); }
.btn.scanning { opacity:0.6; cursor:wait; }
.btn-cyan { border-color:rgba(24,255,255,0.3); color:var(--cyan); }
.btn-cyan:hover { background:var(--cyan-dim); }
.scan-summary { display:flex; gap:16px; margin-bottom:12px; flex-wrap:wrap; }
.scan-stat { font-size:12px; }
.scan-stat b { color:var(--cyan); }
.scan-note { font-size:11px; color:var(--text-dim); margin-top:8px; }
@media (max-width:900px) { .grid-4{grid-template-columns:repeat(2,1fr);} .grid-3{grid-template-columns:1fr;} .grid-2{grid-template-columns:1fr;} .container{padding:12px;} }
@media (max-width:500px) { .grid-4{grid-template-columns:1fr;} }
</style>
</head>
<body>
<div class="header">
  <div class="header-left">
    <div class="logo"><a href="/" style="color:inherit;text-decoration:none;">V<span>ig</span></a></div>
    <div class="status-badge offline" id="statusBadge"><div class="status-dot"></div><span id="statusText">Loading...</span></div>
  </div>
  <div class="header-right">
    <span class="countdown" id="countdown"></span>
    <span class="refresh-label" id="lastUpdate"></span>
  </div>
</div>
<div class="container">

  <!-- Tabs -->
  <div class="tabs">
    <div class="tab active" onclick="switchTab('overview')">Overview</div>
    <div class="tab" onclick="switchTab('pnl')">P&L Flow</div>
  </div>

  <!-- Overview Tab -->
  <div id="overviewTab" class="tab-content active">
  <!-- Balance Overview -->
  <div class="card" style="margin-bottom:16px">
    <div class="card-header"><div class="card-title">Portfolio Balance</div></div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:12px">
      <div><div class="card-sub">Available Cash</div><div class="card-value" id="currentCash">--</div></div>
      <div><div class="card-sub">Locked Funds</div><div class="card-value" id="lockedFunds">--</div></div>
      <div><div class="card-sub">Total Balance</div><div class="card-value" id="totalBalance">--</div></div>
      <div><div class="card-sub">Position Value</div><div class="card-value" id="positionValue">--</div></div>
      <div><div class="card-sub">Total Portfolio</div><div class="card-value" id="totalPortfolio">--</div></div>
      <div><div class="card-sub">Net P&L</div><div class="card-value" id="netPnl">--</div></div>
    </div>
  </div>

  <!-- Stats Row -->
  <div class="grid grid-4">
    <div class="card"><div class="card-title">Realized P&L</div><div class="card-value" id="totalPnl">--</div><div class="card-sub" id="totalPnlSub"></div></div>
    <div class="card"><div class="card-title">Win Rate</div><div class="card-value" id="winRate">--</div><div class="card-sub" id="winRateSub"></div></div>
    <div class="card"><div class="card-title">Total Pocketed</div><div class="card-value positive" id="pocketed">--</div><div class="card-sub" id="pocketedSub"></div></div>
    <div class="card"><div class="card-title">Windows</div><div class="card-value" id="totalWindows">--</div><div class="card-sub" id="windowsSub"></div></div>
  </div>

  <!-- Snowball + Circuit Breaker -->
  <div class="grid grid-2">
    <div class="card">
      <div class="card-header"><div class="card-title">Snowball</div><span class="tag" id="phaseBadge">--</span></div>
      <div class="card-value" id="clipSize">--</div><div class="card-sub">per bet</div>
      <div class="snowball-track"><div class="snowball-fill growth" id="snowballFill" style="width:10%"></div></div>
      <div class="snowball-labels"><span>$10</span><span id="snowballPct">0%</span><span>$100</span></div>
    </div>
    <div class="card">
      <div class="card-header"><div class="card-title">Circuit Breaker</div></div>
      <div class="cb-status cb-ok" id="cbStatus"><span>&#9679;</span><span id="cbText">All clear</span></div>
      <div style="margin-top:12px;display:flex;gap:16px;">
        <div><div class="card-title" style="margin-bottom:4px">Consec. Losses</div><div style="font-size:18px;font-weight:600" id="consecLosses">0</div><div class="card-sub">limit: 5</div></div>
        <div><div class="card-title" style="margin-bottom:4px">Daily Loss</div><div style="font-size:18px;font-weight:600" id="dailyLoss">0%</div><div class="card-sub">limit: 15%</div></div>
      </div>
    </div>
  </div>

  <!-- Active Bets -->
  <div class="card" style="margin-bottom:16px" id="pendingCard" hidden>
    <div class="card-header">
      <div class="card-title">Active Bets</div>
      <span class="tag pending" id="pendingCount">0</span>
    </div>
    <div class="table-wrap" id="pendingTable"></div>
  </div>

  <!-- Bot Control Panel -->
  <div class="card" style="margin-bottom:16px">
    <div class="card-header">
      <div class="card-title">Bot Control</div>
      <div class="card-actions">
        <span class="status-badge" id="botStatusBadge">--</span>
      </div>
    </div>
    <div id="botStatusContent">
      <div class="empty">Loading bot status...</div>
    </div>
    <div id="botControlPanel" style="margin-top:16px;padding-top:16px;border-top:1px solid var(--border);display:none;">
      <div class="bot-description" style="margin-bottom:16px;padding:12px;background:var(--surface2);border-radius:6px;font-size:12px;line-height:1.6;color:var(--text-dim);">
        <strong style="color:var(--text);display:block;margin-bottom:8px;">About This Bot</strong>
        <p style="margin:0 0 8px 0;">This bot automatically scans <strong>Polymarket</strong> every hour for expiring prediction markets. It identifies markets with favorable odds (70-90% favorite) and places bets using a snowball strategy that increases bet size after wins.</p>
        <p style="margin:0;"><strong>Trading Windows:</strong> Every 60 minutes | <strong>Markets:</strong> Polymarket (future: additional exchanges) | <strong>Strategy:</strong> Snowball with circuit breakers</p>
      </div>
      <div class="bot-controls" style="display:flex;gap:8px;flex-wrap:wrap;">
        <button class="btn btn-cyan" id="restartBtn" onclick="confirmRestart()" style="flex:1;min-width:120px;">🔄 Restart</button>
        <button class="btn" id="stopBtn" onclick="controlBot('stop')" style="flex:1;min-width:120px;border-color:var(--red-dim);color:var(--red);">⏹ Stop</button>
        <button class="btn" id="startBtn" onclick="controlBot('start')" style="flex:1;min-width:120px;border-color:var(--green-dim);color:var(--green);">▶ Start</button>
      </div>
      <div id="botControlMessage" style="margin-top:12px;padding:8px 12px;border-radius:6px;font-size:11px;display:none;"></div>
    </div>
  </div>

  <!-- Live Scanner -->
  <div class="card" style="margin-bottom:16px">
    <div class="card-header">
      <div class="card-title">Live Scanner</div>
      <button class="btn btn-cyan" id="scanBtn" onclick="runScan()">Scan Now</button>
    </div>
    <div id="scanResults">
      <div class="empty"><div class="empty-icon">&#9673;</div><div>Hit "Scan Now" to scan Polymarket for expiring markets (future: additional prediction exchanges)</div></div>
    </div>
  </div>

  <!-- Equity Curve -->
  <div class="card" style="margin-bottom:16px"><div class="card-header"><div class="card-title">Equity Curve</div></div><div class="chart-container"><canvas id="equityChart"></canvas></div></div>

  <!-- Windows + Bets Tables -->
  <div class="grid grid-2">
    <div class="card"><div class="card-header"><div class="card-title">Trading Windows</div></div><div class="table-wrap" id="windowsTable"><div class="empty"><div class="empty-icon">&#9678;</div><div>No windows yet</div></div></div></div>
    <div class="card"><div class="card-header"><div class="card-title">All Bets</div></div><div class="table-wrap" id="betsTable"><div class="empty"><div class="empty-icon">&#9678;</div><div>No bets yet</div></div></div></div>
  </div>
  </div>

  <!-- P&L Flow Tab -->
  <div id="pnlTab" class="tab-content">
    <div class="grid grid-3" style="margin-bottom:20px">
      <div class="card"><div class="card-title">Starting Balance</div><div class="card-value" id="pnlStartBalance">--</div></div>
      <div class="card"><div class="card-title">Current Balance</div><div class="card-value" id="pnlCurrentBalance">--</div></div>
      <div class="card"><div class="card-title">Net P&L</div><div class="card-value" id="pnlNetPnl">--</div></div>
    </div>
    <div class="card">
      <div class="card-header"><div class="card-title">Cash Flow</div></div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Type</th>
              <th>Market</th>
              <th>Side</th>
              <th>Amount</th>
              <th>Payout</th>
              <th>Profit</th>
              <th>Balance</th>
            </tr>
          </thead>
          <tbody id="pnlFlowTable">
            <tr><td colspan="8" class="empty">Loading...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>
let equityChart=null;

function switchTab(tabName) {
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById(tabName+'Tab').classList.add('active');
  if(tabName==='pnl') loadPnlFlow();
}

async function loadPnlFlow() {
  try {
    const data=await fetchJSON('/api/pnl-flow');
    if(!data || !data.flow) {
      document.getElementById('pnlFlowTable').innerHTML='<tr><td colspan="8" class="empty">No data available</td></tr>';
      return;
    }
    
    document.getElementById('pnlStartBalance').textContent=fmt(data.starting_balance);
    // Show total portfolio (cash + positions) not just cash balance
    const totalPortfolio=(data.total_portfolio||0)||((data.current_cash||0)+(data.position_value||0));
    document.getElementById('pnlCurrentBalance').textContent=fmt(totalPortfolio);
    // Net P&L = total portfolio - starting balance
    const netPnl=data.net_pnl_total!==undefined?data.net_pnl_total:(totalPortfolio-data.starting_balance);
    const pnlEl=document.getElementById('pnlNetPnl');
    pnlEl.textContent=fmt(netPnl);
    pnlEl.className='card-value '+(netPnl>=0?'positive':'negative');
    
    let html='';
    if(!data.flow || data.flow.length===0) {
      html='<tr><td colspan="8" class="empty">No transactions yet</td></tr>';
    } else {
      for(const f of data.flow) {
      const date=f.date?new Date(f.date).toLocaleString():'--';
      let type='',amount='',payout='',profit='',balance='',side='';
      
      if(f.type==='starting_balance') {
        type='<span class="tag growth">START</span>';
        balance='<span class="positive">'+fmt(f.balance)+'</span>';
      } else if(f.type==='bet_placed') {
        type='<span class="tag pending">BET</span>';
        amount='<span class="negative">-'+fmt(f.amount)+'</span>';
        balance=fmt(f.balance);
        side=f.side||'--';
      } else if(f.type==='settlement') {
        type='<span class="tag '+(f.result==='won'?'won':'lost')+'">SETTLE</span>';
        payout='<span class="positive">+'+fmt(f.payout)+'</span>';
        profit='<span class="'+(f.profit>=0?'positive':'negative')+'">'+fmt(f.profit)+'</span>';
        balance='<span class="'+(f.balance>=0?'positive':'negative')+'">'+fmt(f.balance)+'</span>';
        side=f.side||'--';
      }
      
      const market=(f.market||'').substring(0,35)+((f.market||'').length>35?'...':'');
      html+='<tr>';
      html+='<td>'+date+'</td>';
      html+='<td>'+type+'</td>';
      html+='<td title="'+(f.market||'')+'">'+market+'</td>';
      html+='<td>'+side+'</td>';
      html+='<td>'+amount+'</td>';
      html+='<td>'+payout+'</td>';
      html+='<td>'+profit+'</td>';
      html+='<td>'+balance+'</td>';
      html+='</tr>';
      }
    }
    document.getElementById('pnlFlowTable').innerHTML=html;
  } catch(e) {
    document.getElementById('pnlFlowTable').innerHTML='<tr><td colspan="8" class="empty">Error: '+e.message+'</td></tr>';
  }
}
let lastWindowAt=null;

async function fetchJSON(u){try{const r=await fetch(u);if(!r.ok){console.error(`API error ${r.status}: ${u}`);return null;}return await r.json()}catch(e){console.error(`Fetch error for ${u}:`,e);return null}}
function fmt(n){if(n==null)return'--';const sign=n>=0?'+':'-';return sign+'$'+Math.abs(n).toFixed(2)}
function timeAgo(iso){if(!iso)return'--';const d=new Date(iso),s=(Date.now()-d.getTime())/1000;if(s<60)return Math.floor(s)+'s ago';if(s<3600){const m=Math.floor(s/60);return m+'m ago';}if(s<172800){const h=Math.floor(s/3600),m=Math.floor((s%3600)/60);if(m===0)return h+'h ago';return h+'h '+m+'m ago';}return Math.floor(s/86400)+'d ago'}
function formatDateTime(iso){if(!iso)return'--';const d=new Date(iso);const months=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];const month=months[d.getMonth()];const day=d.getDate();const year=d.getFullYear();let hours=d.getHours();const minutes=d.getMinutes();const ampm=hours>=12?'PM':'AM';hours=hours%12;hours=hours?hours:12;const mins=minutes<10?'0'+minutes:minutes;return month+' '+day+', '+year+', '+hours+':'+mins+' '+ampm}

// Countdown timer
function updateCountdown(){
  const el=document.getElementById('countdown');
  if(!lastWindowAt){el.textContent='';return}
  const next=new Date(lastWindowAt).getTime()+3600000;
  const diff=next-Date.now();
  if(diff<=0){el.textContent='Window due now';return}
  const m=Math.floor(diff/60000);
  const s=Math.floor((diff%60000)/1000);
  el.textContent='Next window: '+m+'m '+s+'s';
}
setInterval(updateCountdown,1000);

// Live scan
async function runScan(){
  const btn=document.getElementById('scanBtn');
  btn.textContent='Scanning...';btn.classList.add('scanning');
  const data=await fetchJSON('/api/scan');
  btn.textContent='Scan Now';btn.classList.remove('scanning');

  const el=document.getElementById('scanResults');
  if(!data||data.error){
    el.innerHTML='<div class="empty">Scan failed: '+(data?.error||'unknown')+'</div>';
    return;
  }

  let html='<div class="scan-summary">';
  html+='<div class="scan-stat">Raw markets: <b>'+data.total_raw+'</b></div>';
  html+='<div class="scan-stat">In price range: <b>'+data.total_parsed+'</b></div>';
  html+='<div class="scan-stat">Qualifying: <b>'+data.qualifying+'</b></div>';
  html+='</div>';

  if(data.markets.length===0){
    html+='<div class="empty">No markets expiring in the next 60 minutes</div>';
  } else {
    html+='<table><tr><th>Market</th><th>Cat</th><th>Exp</th><th>YES</th><th>NO</th><th>Fav</th><th>Vol</th><th>Status</th></tr>';
    for(const m of data.markets){
      const q=m.question.substring(0,45)+(m.question.length>45?'...':'');
      html+='<tr><td title="'+m.question+'">'+q+'</td>';
      html+='<td>'+m.category+'</td>';
      html+='<td>'+m.minutes_to_expiry+'m</td>';
      html+='<td'+(m.fav_side==='YES'?' class="positive"':'')+'>$'+m.yes_price.toFixed(2)+'</td>';
      html+='<td'+(m.fav_side==='NO'?' class="positive"':'')+'>$'+m.no_price.toFixed(2)+'</td>';
      html+='<td>'+(m.fav_side?'<span class="tag '+(m.fav_side==='YES'?'yes':'no')+'">'+m.fav_side+'</span>':'--')+'</td>';
      html+='<td>$'+(m.volume||0).toLocaleString()+'</td>';
      html+='<td><span class="tag '+(m.qualifies?'qual':'skip')+'">'+(m.qualifies?'QUAL':'SKIP')+'</span></td>';
      html+='</tr>';
    }
    html+='</table>';
    html+='<div class="scan-note">Scanned Polymarket at '+new Date(data.scanned_at).toLocaleTimeString()+' | Window ends '+new Date(data.window_end).toLocaleTimeString()+'</div>';
  }
  el.innerHTML=html;
}

async function refresh(){
  try{
    const[stats,windows,bets,curve,pending,botStatus]=await Promise.all([
      fetchJSON('/api/stats').catch(e=>{console.error('Stats error:',e);return null;}),
      fetchJSON('/api/windows?limit=20').catch(e=>{console.error('Windows error:',e);return null;}),
      fetchJSON('/api/bets?limit=30').catch(e=>{console.error('Bets error:',e);return null;}),
      fetchJSON('/api/equity-curve').catch(e=>{console.error('Curve error:',e);return null;}),
      fetchJSON('/api/pending').catch(e=>{console.error('Pending error:',e);return null;}),
      fetchJSON('/api/bot-status').catch(e=>{console.error('Bot status error:',e);return null;}),
    ]);
    
    // Update bot status
    updateBotStatus(botStatus);

  // Status
  const b=document.getElementById('statusBadge'),st=document.getElementById('statusText');
  if(!stats||stats.total_bets===0){b.className='status-badge offline';st.textContent='No data'}
  else if(stats.mode==='paper'){b.className='status-badge paper';st.textContent='Paper'}
  else{b.className='status-badge live';st.textContent='Live'}

  // Countdown
  if(stats&&stats.last_window_at) lastWindowAt=stats.last_window_at;

  if(stats){
  // Portfolio balance
  const currentCash=stats.current_cash||0;
  const lockedFunds=stats.pending_locked||0;
  const positionValue=stats.position_value||0;
  const totalPortfolio=stats.total_portfolio||0;
  const netPnl=stats.net_pnl||0;
  document.getElementById('currentCash').textContent=fmt(currentCash);
  document.getElementById('lockedFunds').textContent=fmt(lockedFunds);
  document.getElementById('positionValue').textContent=fmt(positionValue);
  document.getElementById('totalPortfolio').textContent=fmt(totalPortfolio);
  const netPnlEl=document.getElementById('netPnl');
  netPnlEl.textContent=fmt(netPnl);
  netPnlEl.className='card-value '+(netPnl>=0?'positive':'negative');
  
  // Realized P&L (settled bets only)
    const pnl=stats.total_profit||0;
    document.getElementById('totalPnl').textContent=fmt(pnl);
    document.getElementById('totalPnl').className='card-value '+(pnl>=0?'positive':'negative');
    document.getElementById('totalPnlSub').textContent=(stats.total_bets||0)+' bets | $'+(stats.total_deployed||0).toFixed(0)+' deployed';
    document.getElementById('winRate').textContent=(stats.win_rate||0).toFixed(1)+'%';
    document.getElementById('winRate').className='card-value '+(stats.win_rate>=85?'positive':stats.win_rate>=80?'neutral':'negative');
    document.getElementById('winRateSub').textContent=(stats.wins||0)+'W '+(stats.losses||0)+'L '+(stats.pending||0)+'P';
    document.getElementById('pocketed').textContent='$'+(stats.total_pocketed||0).toFixed(2);
    document.getElementById('pocketedSub').textContent=(stats.current_phase||'growth')+' mode';
    document.getElementById('totalWindows').textContent=stats.total_windows||0;
    document.getElementById('windowsSub').textContent='clip: $'+(stats.current_clip||10).toFixed(2);
    const clip=stats.current_clip||10,pct=Math.min(100,((clip-10)/90)*100);
    document.getElementById('clipSize').textContent='$'+clip.toFixed(2);
    const fill=document.getElementById('snowballFill');
    fill.style.width=Math.max(3,pct)+'%';fill.className='snowball-fill '+(stats.current_phase||'growth');
    document.getElementById('snowballPct').textContent=pct.toFixed(0)+'%';
    const pb=document.getElementById('phaseBadge');pb.textContent=stats.current_phase||'growth';pb.className='tag '+(stats.current_phase||'growth');
    const consec=stats.consecutive_losses||0;document.getElementById('consecLosses').textContent=consec;
    const cb=document.getElementById('cbStatus'),ct=document.getElementById('cbText');
    if(consec>=5){cb.className='cb-status cb-stop';ct.textContent='STOPPED'}
    else if(consec>=3){cb.className='cb-status cb-warn';ct.textContent='Warning'}
    else{cb.className='cb-status cb-ok';ct.textContent='All clear'}
  }

  // Pending bets
  const pendingCard=document.getElementById('pendingCard');
  if(pending&&pending.length>0){
    pendingCard.hidden=false;
    document.getElementById('pendingCount').textContent=pending.length+' active';
    let ph='<table><tr><th>Market</th><th>Side</th><th>Price</th><th>Amount</th><th>Placed</th></tr>';
    for(const p of pending){
      const q=(p.market_question||'').substring(0,45)+((p.market_question||'').length>45?'...':'');
      ph+='<tr><td title="'+(p.market_question||'')+'">'+q+'</td>';
      ph+='<td><span class="tag '+(p.side==='YES'?'yes':'no')+'">'+p.side+'</span></td>';
      ph+='<td>$'+(p.price||0).toFixed(2)+'</td>';
      ph+='<td>$'+(p.amount||0).toFixed(2)+'</td>';
      ph+='<td>'+formatDateTime(p.placed_at)+'</td></tr>';
    }
    ph+='</table>';
    document.getElementById('pendingTable').innerHTML=ph;
  } else {
    pendingCard.hidden=true;
  }

  // Windows table
  if(windows&&windows.length>0){
    let h='<table><tr><th>#</th><th>Time</th><th>Bets</th><th>W/L</th><th>Profit</th><th>Clip</th><th>Phase</th></tr>';
    for(const w of windows){const p=w.profit||0;h+='<tr><td>'+w.id+'</td><td>'+timeAgo(w.started_at)+'</td><td>'+(w.bets_placed||0)+'</td><td>'+(w.bets_won||0)+'W '+(w.bets_lost||0)+'L</td><td class="'+(p>=0?'positive':'negative')+'">'+fmt(p)+'</td><td>$'+(w.clip_size||0).toFixed(2)+'</td><td><span class="tag '+(w.phase||'growth')+'">'+(w.phase||'--')+'</span></td></tr>'}
    h+='</table>';document.getElementById('windowsTable').innerHTML=h}

  // Bets table
  if(bets&&bets.length>0){
    let h='<table><tr><th>Market</th><th>Side</th><th>Price</th><th>Amt</th><th>Result</th><th>P&L</th></tr>';
    for(const b of bets){const q=(b.market_question||'').substring(0,40)+((b.market_question||'').length>40?'...':'');const pr=b.profit||0;h+='<tr><td title="'+(b.market_question||'')+'">'+q+'</td><td>'+(b.side||'--')+'</td><td>$'+(b.price||0).toFixed(2)+'</td><td>$'+(b.amount||0).toFixed(2)+'</td><td><span class="tag '+(b.result||'pending')+'">'+(b.result||'pending')+'</span></td><td class="'+(b.result==='won'?'positive':b.result==='lost'?'negative':'neutral')+'">'+(b.result==='pending'?'--':fmt(pr))+'</td></tr>'}
    h+='</table>';document.getElementById('betsTable').innerHTML=h}

  // Equity chart
  if(curve&&curve.length>0){
    if(equityChart)equityChart.destroy();
    const ctx=document.getElementById('equityChart').getContext('2d');
    const d=curve.map(c=>c.cumulative);
    equityChart=new Chart(ctx,{type:'line',data:{labels:curve.map(c=>'W'+c.window),datasets:[{data:d,borderColor:d[d.length-1]>=0?'#00e676':'#ff5252',backgroundColor:d[d.length-1]>=0?'rgba(0,230,118,0.08)':'rgba(255,82,82,0.08)',fill:true,tension:0.3,pointRadius:2,borderWidth:2}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:'#6b7084',font:{size:10}},grid:{color:'rgba(255,255,255,0.04)'}},y:{ticks:{color:'#6b7084',font:{size:10},callback:v=>'$'+v},grid:{color:'rgba(255,255,255,0.04)'}}},interaction:{intersect:false,mode:'index'}}})
  }
  document.getElementById('lastUpdate').textContent='Updated '+new Date().toLocaleTimeString();
}

function updateBotStatus(status){
  if(!status)return;
  const badge=document.getElementById('botStatusBadge');
  const content=document.getElementById('botStatusContent');
  const panel=document.getElementById('botControlPanel');
  
  const statusMap={
    'running':{class:'status-badge live',text:'Running',icon:'🟢'},
    'stopped':{class:'status-badge offline',text:'Stopped',icon:'🔴'},
    'error':{class:'status-badge error',text:'Error',icon:'🟡'},
    'unknown':{class:'status-badge offline',text:'Unknown',icon:'⚪'}
  };
  
  const s=statusMap[status.status]||statusMap['unknown'];
  badge.className=s.class;
  badge.textContent=s.icon+' '+s.text;
  
  // Show control panel
  panel.style.display='block';
  
  // Update button states
  const restartBtn=document.getElementById('restartBtn');
  const stopBtn=document.getElementById('stopBtn');
  const startBtn=document.getElementById('startBtn');
  
  if(status.status==='running'){
    restartBtn.disabled=false;
    stopBtn.disabled=false;
    startBtn.disabled=true;
    startBtn.style.opacity='0.5';
    stopBtn.style.opacity='1';
  } else {
    restartBtn.disabled=false;
    stopBtn.disabled=true;
    startBtn.disabled=false;
    stopBtn.style.opacity='0.5';
    startBtn.style.opacity='1';
  }
  
  let html='<div class="bot-status-info">';
  html+='<div class="bot-activity"><strong>Activity:</strong> '+(status.activity||'Unknown')+'</div>';
  if(status.last_scan){
    html+='<div class="bot-last-scan"><strong>Last Scan:</strong> '+timeAgo(status.last_scan)+'</div>';
  }
  if(status.last_window){
    html+='<div class="bot-last-window"><strong>Last Window:</strong> '+timeAgo(status.last_window)+'</div>';
  } else {
    html+='<div class="bot-last-window"><strong>Last Window:</strong> <span style="color:var(--text-dim)">No windows recorded yet</span></div>';
  }
  html+='</div>';
  content.innerHTML=html;
}

function confirmRestart(){
  if(confirm('Are you sure you want to restart the bot?\n\nThis will restart the Railway service and may interrupt any active trading windows.')){
    controlBot('restart');
  }
}

async function controlBot(action){
  const btn=event.target;
  const originalText=btn.textContent;
  btn.disabled=true;
  btn.textContent='Processing...';
  
  const messageEl=document.getElementById('botControlMessage');
  messageEl.style.display='none';
  
  try{
    const formData=new FormData();
    formData.append('action',action);
    
    const response=await fetch('/api/bot-control',{
      method:'POST',
      body:formData
    });
    const result=await response.json();
    
    // Format message with line breaks
    const message=result.message||'Action completed';
    messageEl.innerHTML=message.replace(/\n/g,'<br>');
    messageEl.style.display='block';
    messageEl.style.background=result.status==='success'?'var(--green-dim)':result.status==='error'?'var(--red-dim)':'var(--amber-dim)';
    messageEl.style.color=result.status==='success'?'var(--green)':result.status==='error'?'var(--red)':'var(--amber)';
    
    if(action==='restart'&&result.status==='success'){
      // Refresh status after a delay
      setTimeout(()=>{
        location.reload();
      },5000);
    }
  }catch(e){
    messageEl.innerHTML='Error: '+e.message;
    messageEl.style.display='block';
    messageEl.style.background='var(--red-dim)';
    messageEl.style.color='var(--red)';
  }finally{
    btn.disabled=false;
    btn.textContent=originalText;
  }
}

refresh();setInterval(refresh,15000);
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
