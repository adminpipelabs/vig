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

@app.get("/api/wallet/balance", dependencies=[Depends(require_api_key)])
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


@app.get("/api/stats", dependencies=[Depends(require_api_key)])
def api_stats():
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
    stats = dict(row)
    wins = stats.get("wins") or 0
    losses = stats.get("losses") or 0
    resolved = wins + losses
    stats["win_rate"] = (wins / resolved * 100) if resolved > 0 else 0

    c.execute("SELECT * FROM windows ORDER BY id DESC LIMIT 1")
    last_win_row = c.fetchone()
    last_win = dict(last_win_row) if last_win_row else None
    stats["current_clip"] = last_win["clip_size"] if last_win else 10.0
    stats["current_phase"] = last_win["phase"] if last_win else "growth"
    stats["last_window_at"] = last_win["started_at"] if last_win else None

    c.execute("SELECT COUNT(*) as cnt FROM windows")
    cnt_row = c.fetchone()
    stats["total_windows"] = dict(cnt_row)["cnt"] if cnt_row else 0

    c.execute("SELECT COALESCE(SUM(pocketed), 0) as total_pocketed FROM windows")
    pocketed_row = c.fetchone()
    stats["total_pocketed"] = dict(pocketed_row)["total_pocketed"] if pocketed_row else 0.0

    c.execute("SELECT result FROM bets WHERE result!='pending' ORDER BY id DESC")
    streak = 0
    for row in c.fetchall():
        row_dict = dict(row)
        if row_dict["result"] == "lost":
            streak += 1
        else:
            break
    stats["consecutive_losses"] = streak

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
        clob_cash_raw = float(balance_info.get('balance', 0)) / 1e6
        
        # Temporary adjustment: Add recently redeemed amount
        # Redemption transactions succeeded but CLOB API may not have updated yet
        # This accounts for the $164.06 redeemed in the last redemption run
        # TODO: Track redemptions in database or wait for CLOB API to update
        recent_redemption_amount = 164.06  # Amount redeemed in last redemption run (2026-02-06)
        
        # Add redemption amount to CLOB balance to reflect actual available cash
        # This is a temporary fix until CLOB API updates or we implement redemption tracking
        clob_cash = clob_cash_raw + recent_redemption_amount
        logger.info(f"CLOB balance: ${clob_cash_raw:.2f} + redemption ${recent_redemption_amount:.2f} = ${clob_cash:.2f}")
        
        stats["current_cash"] = clob_cash
        stats["clob_cash_raw"] = clob_cash_raw  # Store raw CLOB balance for reference
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


@app.get("/api/windows", dependencies=[Depends(require_api_key)])
def api_windows(limit: int = 50):
    """Get recent trading windows"""
    limit = validate_input(limit, max_limit=1000)
    conn = get_db()
    if is_postgres(conn):
        from psycopg2.extras import RealDictCursor
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("SELECT * FROM windows ORDER BY id DESC LIMIT %s", (limit,))
    else:
        c = conn.cursor()
        c.execute("SELECT * FROM windows ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


@app.get("/api/bets", dependencies=[Depends(require_api_key)])
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


@app.get("/api/pending", dependencies=[Depends(require_api_key)])
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
    """Test Bright Data proxy connection - diagnose 403 issues"""
    import httpx
    from proxy_init import PROXY_URL
    
    results = {
        "proxy_url": PROXY_URL.split("@")[-1] if "@" in PROXY_URL else "hidden",
        "tests": []
    }
    
    # Test 1: Bright Data test endpoint
    try:
        client = httpx.Client(proxy=PROXY_URL, trust_env=False, timeout=10.0)
        resp = client.get("https://lumtest.com/myip.json", timeout=10.0)
        client.close()
        if resp.status_code == 200:
            ip_info = resp.json()
            results["tests"].append({
                "test": "Bright Data test endpoint (lumtest.com)",
                "status": "SUCCESS",
                "status_code": resp.status_code,
                "ip": ip_info.get("ip"),
                "country": ip_info.get("country"),
                "message": "Proxy authentication works!"
            })
        else:
            results["tests"].append({
                "test": "Bright Data test endpoint",
                "status": "FAILED",
                "status_code": resp.status_code,
                "response": resp.text[:200],
                "message": f"Bright Data returned {resp.status_code}"
            })
    except httpx.ProxyError as e:
        results["tests"].append({
            "test": "Bright Data test endpoint",
            "status": "PROXY_ERROR",
            "error": str(e),
            "message": "Bright Data proxy rejected request (403 = auth/access issue)"
        })
    except Exception as e:
        results["tests"].append({
            "test": "Bright Data test endpoint",
            "status": "ERROR",
            "error": f"{type(e).__name__}: {str(e)}",
            "message": "Network or configuration issue"
        })
    
    # Test 2: Polymarket CLOB health
    try:
        client = httpx.Client(proxy=PROXY_URL, trust_env=False, timeout=10.0)
        resp = client.get("https://clob.polymarket.com/health", timeout=10.0)
        client.close()
        if resp.status_code == 200:
            results["tests"].append({
                "test": "Polymarket CLOB health",
                "status": "SUCCESS",
                "status_code": resp.status_code,
                "message": "Can reach Polymarket through proxy!"
            })
        else:
            results["tests"].append({
                "test": "Polymarket CLOB health",
                "status": "FAILED",
                "status_code": resp.status_code,
                "response": resp.text[:200],
                "message": f"Polymarket returned {resp.status_code}"
            })
    except httpx.ProxyError as e:
        results["tests"].append({
            "test": "Polymarket CLOB health",
            "status": "PROXY_ERROR",
            "error": str(e),
            "message": "Proxy rejected request to Polymarket"
        })
    except Exception as e:
        results["tests"].append({
            "test": "Polymarket CLOB health",
            "status": "ERROR",
            "error": f"{type(e).__name__}: {str(e)}"
        })
    
    return results


@app.get("/api/debug/status")
def debug_status():
    """Full system status for debugging"""
    import os
    
    status = {
        "environment": {
            "PAPER_MODE": os.getenv("PAPER_MODE", "not set"),
            "DATABASE_URL_SET": bool(os.getenv("DATABASE_URL")),
            "RESIDENTIAL_PROXY_SET": bool(os.getenv("RESIDENTIAL_PROXY_URL")),
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


@app.get("/api/bot-status", dependencies=[Depends(require_api_key)])
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
            last_window = dict(last_window_row)["started_at"] if last_window_row else None
            conn.close()
        except Exception as e:
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
                    last_window_dt = datetime.fromisoformat(last_window.replace("Z", "+00:00"))
                    age_seconds = (datetime.now(timezone.utc) - last_window_dt).total_seconds()
                    if age_seconds < 3600:  # Within last hour
                        return {
                            "status": "running",
                            "activity": "Bot active (inferred from recent windows)",
                            "last_scan": last_window,
                            "updated_at": last_window,
                            "last_window": last_window
                        }
                except:
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
        if isinstance(last_heartbeat_str, str):
            try:
                last_heartbeat = datetime.fromisoformat(last_heartbeat_str.replace("Z", "+00:00"))
            except:
                last_heartbeat = None
        else:
            last_heartbeat = last_heartbeat_str
        
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


# ─── Dashboard HTML ────────────────────────────────────────────

@app.get("/pnl", response_class=HTMLResponse)
def pnl_page():
    """P&L Cash Flow page"""
    return """<!DOCTYPE html>
<html><body><h1>P&L Flow</h1><p>Coming soon</p></body></html>"""


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
