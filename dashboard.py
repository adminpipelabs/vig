"""
Vig v1 Production Dashboard
- Wallet status & balance
- Fund allocation (available vs deployed)
- Bot settings (editable)
- Strategy overview
- Live scanner, stats, history
"""
import os
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import httpx

app = FastAPI(title="Vig Dashboard")

DB_PATH = os.getenv("DB_PATH", "vig.db")
GAMMA_URL = "https://gamma-api.polymarket.com"

# Polygon USDC contract
USDC_CONTRACT = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # USDC on Polygon
POLYGON_RPC = "https://polygon-rpc.com"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Settings file (persisted JSON) ───────────────────────────

SETTINGS_PATH = "vig_settings.json"

def load_settings():
    defaults = {
        "clip_size": float(os.getenv("STARTING_CLIP", "10.0")),
        "max_bets_per_window": int(os.getenv("MAX_BETS_PER_WINDOW", "10")),
        "min_price": float(os.getenv("MIN_FAVORITE_PRICE", "0.70")),
        "max_price": float(os.getenv("MAX_FAVORITE_PRICE", "0.90")),
        "min_volume": float(os.getenv("MIN_VOLUME_ABS", "100")),
        "scan_interval": int(os.getenv("SCAN_INTERVAL_SECONDS", "3600")),
        "paper_mode": os.getenv("PAPER_MODE", "true").lower() in ("true", "1", "yes"),
    }
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH) as f:
                saved = json.load(f)
                defaults.update(saved)
        except:
            pass
    return defaults

def save_settings(settings):
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


# ─── Wallet Helpers ───────────────────────────────────────────

def get_wallet_address():
    addr = os.getenv("POLYGON_FUNDER_ADDRESS", "")
    if not addr:
        pk = os.getenv("POLYGON_PRIVATE_KEY", "")
        if pk:
            return "key_configured_no_address"
    return addr

async def get_usdc_balance(address: str) -> float:
    """Query USDC balance on Polygon via RPC."""
    if not address or address == "key_configured_no_address":
        return -1
    try:
        # ERC20 balanceOf(address) call
        padded = address.lower().replace("0x", "").zfill(64)
        data = "0x70a08231" + padded  # balanceOf selector

        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{"to": USDC_CONTRACT, "data": data}, "latest"],
            "id": 1,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(POLYGON_RPC, json=payload, timeout=10)
            result = resp.json().get("result", "0x0")
            balance_raw = int(result, 16)
            return balance_raw / 1e6  # USDC has 6 decimals
    except Exception as e:
        print(f"Balance check error: {e}")
        return -1


# ─── API Endpoints ─────────────────────────────────────────────

@app.get("/api/wallet")
async def api_wallet():
    address = get_wallet_address()
    balance = await get_usdc_balance(address) if address else -1
    paper = os.getenv("PAPER_MODE", "true").lower() in ("true", "1", "yes")

    # Calculate deployed (pending bets)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(amount), 0) as deployed FROM bets WHERE result='pending'")
    deployed = c.fetchone()["deployed"]
    conn.close()

    available = max(0, balance - deployed) if balance >= 0 else -1

    return {
        "connected": bool(address and address != "key_configured_no_address"),
        "address": address if address != "key_configured_no_address" else "",
        "balance": round(balance, 2) if balance >= 0 else None,
        "deployed": round(deployed, 2),
        "available": round(available, 2) if available >= 0 else None,
        "paper_mode": paper,
    }


@app.get("/api/settings")
def api_get_settings():
    return load_settings()


@app.post("/api/settings")
async def api_update_settings(request: Request):
    body = await request.json()
    settings = load_settings()
    allowed = ["clip_size", "max_bets_per_window", "min_price", "max_price", "min_volume", "scan_interval"]
    for key in allowed:
        if key in body:
            settings[key] = body[key]
    save_settings(settings)
    return {"ok": True, "settings": settings}


@app.get("/api/stats")
def api_stats():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*) as total_bets,
            SUM(CASE WHEN result='won' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result='lost' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN result='pending' THEN 1 ELSE 0 END) as pending,
            COALESCE(SUM(profit), 0) as total_profit,
            COALESCE(SUM(payout), 0) as total_payout,
            COALESCE(SUM(amount), 0) as total_deployed
        FROM bets
    """)
    stats = dict(c.fetchone())
    wins = stats.get("wins") or 0
    losses = stats.get("losses") or 0
    resolved = wins + losses
    stats["win_rate"] = (wins / resolved * 100) if resolved > 0 else 0

    c.execute("SELECT * FROM windows ORDER BY id DESC LIMIT 1")
    last_win = c.fetchone()
    stats["current_clip"] = last_win["clip_size"] if last_win else 10.0
    stats["current_phase"] = last_win["phase"] if last_win else "growth"
    stats["last_window_at"] = last_win["started_at"] if last_win else None

    c.execute("SELECT COUNT(*) as cnt FROM windows")
    stats["total_windows"] = c.fetchone()["cnt"]
    c.execute("SELECT COALESCE(SUM(pocketed), 0) as total_pocketed FROM windows")
    stats["total_pocketed"] = c.fetchone()["total_pocketed"]

    c.execute("SELECT result FROM bets WHERE result!='pending' ORDER BY id DESC")
    streak = 0
    for row in c.fetchall():
        if row["result"] == "lost":
            streak += 1
        else:
            break
    stats["consecutive_losses"] = streak

    c.execute("SELECT paper FROM bets ORDER BY id DESC LIMIT 1")
    last_bet = c.fetchone()
    stats["mode"] = "paper" if (not last_bet or last_bet["paper"]) else "live"
    conn.close()
    return stats


@app.get("/api/windows")
def api_windows(limit: int = 50):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM windows ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


@app.get("/api/bets")
def api_bets(limit: int = 100):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM bets ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


@app.get("/api/pending")
def api_pending():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM bets WHERE result='pending' ORDER BY id DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


@app.get("/api/circuit-breaker")
def api_circuit_breaker():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM circuit_breaker_log ORDER BY id DESC LIMIT 20")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


@app.get("/api/equity-curve")
def api_equity_curve():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, started_at, profit, pocketed, clip_size, phase FROM windows ORDER BY id ASC")
    rows = c.fetchall()
    cumulative = 0
    curve = []
    for r in rows:
        cumulative += r["profit"]
        curve.append({
            "window": r["id"], "date": r["started_at"],
            "profit": r["profit"], "cumulative": round(cumulative, 2),
            "clip": r["clip_size"], "phase": r["phase"],
        })
    conn.close()
    return curve


@app.get("/api/scan")
def api_scan():
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(minutes=60)
    params = {
        "active": "true", "closed": "false",
        "end_date_min": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_date_max": window_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": 100, "order": "volume24hr", "ascending": "false",
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
            fav_side = fav_price = None
            if 0.70 <= yes_p <= 0.90:
                fav_side, fav_price = "YES", yes_p
            elif 0.70 <= no_p <= 0.90:
                fav_side, fav_price = "NO", no_p
            candidates.append({
                "question": question, "category": category,
                "end_date": end_str, "minutes_to_expiry": round(mins, 1),
                "yes_price": round(yes_p, 3), "no_price": round(no_p, 3),
                "fav_side": fav_side, "fav_price": round(fav_price, 3) if fav_price else None,
                "qualifies": fav_side is not None and volume >= 100,
                "volume": round(volume, 0), "volume_24h": round(vol24, 0),
                "slug": m.get("slug", ""),
            })
        except:
            continue
    candidates.sort(key=lambda x: x["volume"], reverse=True)
    return {
        "scanned_at": now.isoformat(), "window_end": window_end.isoformat(),
        "total_raw": len(raw), "total_parsed": len(candidates),
        "qualifying": len([c for c in candidates if c["qualifies"]]),
        "markets": candidates,
    }


@app.get("/api/history/bets")
def api_history_bets(limit: int = 500, result: str = None, offset: int = 0):
    conn = get_db()
    c = conn.cursor()
    if result and result in ("won", "lost", "pending"):
        c.execute("SELECT * FROM bets WHERE result=? ORDER BY id DESC LIMIT ? OFFSET ?", (result, limit, offset))
    else:
        c.execute("SELECT * FROM bets ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
    rows = [dict(r) for r in c.fetchall()]
    c.execute("SELECT COUNT(*) as cnt FROM bets")
    total = c.fetchone()["cnt"]
    conn.close()
    return {"bets": rows, "total": total}


@app.get("/api/history/windows")
def api_history_windows(limit: int = 500, offset: int = 0):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM windows ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
    rows = [dict(r) for r in c.fetchall()]
    c.execute("SELECT COUNT(*) as cnt FROM windows")
    total = c.fetchone()["cnt"]
    conn.close()
    return {"windows": rows, "total": total}


@app.get("/api/history/daily")
def api_history_daily():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT DATE(placed_at) as date, COUNT(*) as total_bets,
            SUM(CASE WHEN result='won' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result='lost' THEN 1 ELSE 0 END) as losses,
            COALESCE(SUM(profit), 0) as profit,
            COALESCE(SUM(amount), 0) as deployed
        FROM bets WHERE result != 'pending'
        GROUP BY DATE(placed_at) ORDER BY DATE(placed_at) DESC
    """)
    rows = [dict(r) for r in c.fetchall()]
    for r in rows:
        resolved = (r["wins"] or 0) + (r["losses"] or 0)
        r["win_rate"] = round((r["wins"] or 0) / resolved * 100, 1) if resolved > 0 else 0
    conn.close()
    return rows


# ─── Dashboard HTML ────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD_HTML


@app.get("/history", response_class=HTMLResponse)
def history_page():
    return HISTORY_HTML


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)


# ─── HTML Templates ───────────────────────────────────────────

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vig</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600;700&family=Instrument+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #09090b; --surface: #111114; --surface2: #19191f;
  --border: #27272a; --border-focus: #3f3f46;
  --text: #fafafa; --text-dim: #71717a; --text-muted: #52525b;
  --green: #22c55e; --green-dim: rgba(34,197,94,0.1); --green-bright: #4ade80;
  --red: #ef4444; --red-dim: rgba(239,68,68,0.1);
  --amber: #f59e0b; --amber-dim: rgba(245,158,11,0.1);
  --blue: #3b82f6; --blue-dim: rgba(59,130,246,0.1);
  --cyan: #06b6d4; --cyan-dim: rgba(6,182,212,0.1);
  --mono: 'IBM Plex Mono', monospace;
  --sans: 'Instrument Sans', sans-serif;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--bg); color:var(--text); font-family:var(--mono); font-size:13px; line-height:1.6; min-height:100vh; }

/* Header */
.header { display:flex; align-items:center; justify-content:space-between; padding:14px 28px; border-bottom:1px solid var(--border); background:var(--surface); position:sticky; top:0; z-index:50; }
.header-left { display:flex; align-items:center; gap:20px; }
.logo { font-family:var(--sans); font-size:24px; font-weight:700; letter-spacing:-1px; color:var(--text); text-decoration:none; }
.logo em { font-style:normal; color:var(--green); }
.nav { display:flex; gap:2px; background:var(--surface2); border-radius:8px; padding:2px; }
.nav a { padding:6px 16px; border-radius:6px; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.8px; color:var(--text-dim); text-decoration:none; transition:all 0.15s; }
.nav a:hover { color:var(--text); }
.nav a.active { color:var(--text); background:var(--bg); }
.header-right { display:flex; align-items:center; gap:16px; }
.countdown { font-size:11px; color:var(--cyan); font-weight:500; letter-spacing:0.3px; }
.mode-tag { display:inline-flex; align-items:center; gap:5px; padding:4px 10px; border-radius:6px; font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:0.8px; }
.mode-tag.paper { background:var(--amber-dim); color:var(--amber); border:1px solid rgba(245,158,11,0.2); }
.mode-tag.live { background:var(--green-dim); color:var(--green); border:1px solid rgba(34,197,94,0.2); }
.mode-dot { width:5px; height:5px; border-radius:50%; background:currentColor; animation:blink 2s ease-in-out infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }

/* Layout */
.container { padding:24px 28px; max-width:1500px; margin:0 auto; }
.grid { display:grid; gap:14px; margin-bottom:14px; }
.g4 { grid-template-columns:repeat(4,1fr); }
.g3 { grid-template-columns:repeat(3,1fr); }
.g2 { grid-template-columns:1fr 1fr; }
.g23 { grid-template-columns:2fr 3fr; }
.g32 { grid-template-columns:3fr 2fr; }

/* Cards */
.card { background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:18px 22px; position:relative; overflow:hidden; }
.card::before { content:''; position:absolute; top:0; left:0; right:0; height:1px; background:linear-gradient(90deg,transparent,rgba(255,255,255,0.06),transparent); }
.card-head { display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; }
.card-label { font-size:10px; text-transform:uppercase; letter-spacing:1.2px; color:var(--text-muted); font-weight:500; }
.card-val { font-family:var(--sans); font-size:30px; font-weight:700; letter-spacing:-1.5px; line-height:1.1; }
.card-sub { font-size:11px; color:var(--text-dim); margin-top:4px; }
.pos { color:var(--green); }
.neg { color:var(--red); }
.dim { color:var(--text-dim); }

/* Wallet Card */
.wallet-card { border-color:var(--border); }
.wallet-card.connected { border-color:rgba(34,197,94,0.25); }
.wallet-status { display:flex; align-items:center; gap:8px; margin-bottom:14px; }
.wallet-dot { width:8px; height:8px; border-radius:50%; }
.wallet-dot.on { background:var(--green); box-shadow:0 0 8px rgba(34,197,94,0.4); }
.wallet-dot.off { background:var(--red); }
.wallet-addr { font-size:12px; color:var(--text-dim); font-family:var(--mono); }
.wallet-row { display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid var(--border); font-size:12px; }
.wallet-row:last-child { border:none; }
.wallet-row-label { color:var(--text-muted); }
.wallet-row-val { font-weight:600; }

/* Fund bars */
.fund-bar { width:100%; height:6px; background:var(--surface2); border-radius:3px; margin:8px 0; overflow:hidden; }
.fund-bar-fill { height:100%; border-radius:3px; }
.fund-bar-fill.available { background:var(--green); }
.fund-bar-fill.deployed { background:var(--blue); }

/* Settings */
.settings-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.setting-item { display:flex; flex-direction:column; gap:4px; }
.setting-label { font-size:10px; text-transform:uppercase; letter-spacing:0.8px; color:var(--text-muted); }
.setting-input { background:var(--bg); border:1px solid var(--border); border-radius:6px; padding:8px 12px; color:var(--text); font-family:var(--mono); font-size:13px; width:100%; transition:border-color 0.15s; }
.setting-input:focus { outline:none; border-color:var(--cyan); }
.setting-input:disabled { opacity:0.5; }
.btn { display:inline-flex; align-items:center; justify-content:center; gap:6px; padding:8px 18px; border-radius:6px; font-size:11px; font-weight:600; font-family:var(--mono); cursor:pointer; border:1px solid var(--border); background:var(--surface2); color:var(--text); transition:all 0.15s; text-transform:uppercase; letter-spacing:0.5px; }
.btn:hover { background:var(--border); }
.btn:disabled { opacity:0.4; cursor:not-allowed; }
.btn-green { border-color:rgba(34,197,94,0.3); color:var(--green); }
.btn-green:hover { background:var(--green-dim); }
.btn-cyan { border-color:rgba(6,182,212,0.3); color:var(--cyan); }
.btn-cyan:hover { background:var(--cyan-dim); }
.btn-amber { border-color:rgba(245,158,11,0.3); color:var(--amber); }
.btn-amber:hover { background:var(--amber-dim); }
.save-msg { font-size:11px; color:var(--green); margin-left:8px; opacity:0; transition:opacity 0.3s; }
.save-msg.show { opacity:1; }

/* Strategy box */
.strategy-box { font-size:12px; line-height:1.8; color:var(--text-dim); }
.strategy-box h3 { font-family:var(--sans); font-size:14px; font-weight:600; color:var(--text); margin-bottom:8px; }
.strategy-box .hl { color:var(--cyan); font-weight:500; }
.strategy-box .rule { display:flex; gap:8px; margin:4px 0; }
.strategy-box .rule-n { color:var(--text-muted); font-weight:600; min-width:18px; }

/* Snowball */
.snow-track { width:100%; height:6px; background:var(--surface2); border-radius:3px; margin:10px 0 6px; overflow:hidden; }
.snow-fill { height:100%; border-radius:3px; transition:width 0.6s; }
.snow-fill.growth { background:linear-gradient(90deg,var(--blue),var(--green)); }
.snow-fill.harvest { background:linear-gradient(90deg,var(--green),var(--amber)); }
.snow-labels { display:flex; justify-content:space-between; font-size:10px; color:var(--text-muted); }

/* Tables */
.table-wrap { overflow-x:auto; max-height:380px; overflow-y:auto; }
table { width:100%; border-collapse:collapse; font-size:12px; }
th { text-align:left; padding:7px 10px; font-size:9px; text-transform:uppercase; letter-spacing:1px; color:var(--text-muted); font-weight:500; border-bottom:1px solid var(--border); white-space:nowrap; position:sticky; top:0; background:var(--surface); z-index:1; }
td { padding:7px 10px; border-bottom:1px solid rgba(39,39,42,0.5); white-space:nowrap; font-size:11px; }
tr:hover td { background:rgba(255,255,255,0.015); }
.tag { display:inline-block; padding:2px 7px; border-radius:4px; font-size:9px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; }
.tag.won { background:var(--green-dim); color:var(--green); }
.tag.lost { background:var(--red-dim); color:var(--red); }
.tag.pending { background:var(--blue-dim); color:var(--blue); }
.tag.growth { background:var(--blue-dim); color:var(--blue); }
.tag.harvest { background:var(--amber-dim); color:var(--amber); }
.tag.yes { background:var(--green-dim); color:var(--green); }
.tag.no { background:var(--red-dim); color:var(--red); }
.tag.qual { background:var(--green-dim); color:var(--green); }
.tag.skip { background:var(--surface2); color:var(--text-muted); }

/* Chart */
.chart-box { width:100%; height:180px; position:relative; }
canvas { width:100%!important; height:100%!important; }

/* Circuit breaker */
.cb-bar { display:flex; align-items:center; gap:8px; padding:8px 12px; border-radius:6px; font-size:11px; font-weight:500; }
.cb-ok { background:var(--green-dim); color:var(--green); }
.cb-warn { background:var(--amber-dim); color:var(--amber); }
.cb-stop { background:var(--red-dim); color:var(--red); }

/* Scan */
.scan-summary { display:flex; gap:14px; margin-bottom:10px; flex-wrap:wrap; }
.scan-stat { font-size:11px; }
.scan-stat b { color:var(--cyan); }
.scan-note { font-size:10px; color:var(--text-muted); margin-top:6px; }

.empty { text-align:center; padding:32px; color:var(--text-muted); font-size:12px; }

/* Responsive */
@media (max-width:1000px) { .g4{grid-template-columns:repeat(2,1fr);} .g23,.g32,.g2,.g3{grid-template-columns:1fr;} }
@media (max-width:500px) { .g4{grid-template-columns:1fr;} .container{padding:12px;} .settings-grid{grid-template-columns:1fr;} }
</style>
</head>
<body>
<div class="header">
  <div class="header-left">
    <a href="/" class="logo">V<em>ig</em></a>
    <div class="nav">
      <a href="/" class="active">Dashboard</a>
      <a href="/history">History</a>
    </div>
  </div>
  <div class="header-right">
    <span class="countdown" id="countdown"></span>
    <div class="mode-tag paper" id="modeTag"><div class="mode-dot"></div><span id="modeText">Paper</span></div>
  </div>
</div>

<div class="container">

  <!-- Row 1: Wallet + Stats -->
  <div class="grid g4">
    <div class="card wallet-card" id="walletCard">
      <div class="card-label">Wallet</div>
      <div class="wallet-status">
        <div class="wallet-dot off" id="walletDot"></div>
        <span class="wallet-addr" id="walletAddr">Not connected</span>
      </div>
      <div class="wallet-row"><span class="wallet-row-label">Balance</span><span class="wallet-row-val" id="walletBal">--</span></div>
      <div class="wallet-row"><span class="wallet-row-label">Available</span><span class="wallet-row-val pos" id="walletAvail">--</span></div>
      <div class="wallet-row"><span class="wallet-row-label">In Bets</span><span class="wallet-row-val" id="walletDeployed" style="color:var(--blue)">--</span></div>
      <div class="fund-bar"><div class="fund-bar-fill available" id="fundBar" style="width:100%"></div></div>
    </div>
    <div class="card"><div class="card-label">Total P&L</div><div class="card-val" id="totalPnl">--</div><div class="card-sub" id="totalPnlSub"></div></div>
    <div class="card"><div class="card-label">Win Rate</div><div class="card-val" id="winRate">--</div><div class="card-sub" id="winRateSub"></div></div>
    <div class="card"><div class="card-label">Windows</div><div class="card-val" id="totalWindows">--</div><div class="card-sub" id="windowsSub"></div></div>
  </div>

  <!-- Row 2: Strategy + Settings + Circuit Breaker -->
  <div class="grid g3">
    <div class="card">
      <div class="card-head"><div class="card-label">Strategy</div></div>
      <div class="strategy-box">
        <h3>Favorite-Longshot Bias</h3>
        <p>Vig exploits the tendency for prediction market favorites to be systematically underpriced near expiry.</p>
        <div style="margin-top:10px">
          <div class="rule"><span class="rule-n">1.</span><span>Scan markets expiring within <span class="hl">60 minutes</span></span></div>
          <div class="rule"><span class="rule-n">2.</span><span>Buy favorites priced <span class="hl">$0.70–$0.90</span></span></div>
          <div class="rule"><span class="rule-n">3.</span><span>Fixed <span class="hl" id="stratClip">$10</span> per bet, max <span class="hl" id="stratMax">10</span>/window</span></div>
          <div class="rule"><span class="rule-n">4.</span><span>Collect on resolution, bank profits</span></div>
          <div class="rule"><span class="rule-n">5.</span><span>Circuit breaker stops on <span class="hl">5</span> consecutive losses</span></div>
        </div>
        <p style="margin-top:10px">Edge: ~4-8% per cycle at scale. Requires volume to smooth variance.</p>
      </div>
    </div>
    <div class="card">
      <div class="card-head"><div class="card-label">Bot Settings</div><span class="save-msg" id="saveMsg">Saved ✓</span></div>
      <div class="settings-grid">
        <div class="setting-item"><label class="setting-label">Bet Size ($)</label><input class="setting-input" id="sClip" type="number" step="1" min="1"></div>
        <div class="setting-item"><label class="setting-label">Max Bets / Window</label><input class="setting-input" id="sMaxBets" type="number" step="1" min="1"></div>
        <div class="setting-item"><label class="setting-label">Min Price ($)</label><input class="setting-input" id="sMinPrice" type="number" step="0.01" min="0.50" max="0.95"></div>
        <div class="setting-item"><label class="setting-label">Max Price ($)</label><input class="setting-input" id="sMaxPrice" type="number" step="0.01" min="0.50" max="0.99"></div>
        <div class="setting-item"><label class="setting-label">Min Volume ($)</label><input class="setting-input" id="sMinVol" type="number" step="100" min="0"></div>
        <div class="setting-item"><label class="setting-label">Window (sec)</label><input class="setting-input" id="sScanInt" type="number" step="60" min="60"></div>
      </div>
      <div style="margin-top:14px;display:flex;gap:8px;align-items:center">
        <button class="btn btn-green" onclick="saveSettings()">Save Settings</button>
      </div>
    </div>
    <div class="card">
      <div class="card-head"><div class="card-label">Risk Monitor</div></div>
      <div class="cb-bar cb-ok" id="cbStatus"><span>●</span><span id="cbText">All clear</span></div>
      <div style="margin-top:14px;display:flex;gap:20px;">
        <div><div class="card-label" style="margin-bottom:4px">Consec. Losses</div><div style="font-size:20px;font-weight:600;font-family:var(--sans)" id="consecLosses">0</div><div class="card-sub">limit: 5</div></div>
        <div><div class="card-label" style="margin-bottom:4px">Pocketed</div><div style="font-size:20px;font-weight:600;font-family:var(--sans);color:var(--green)" id="pocketed">$0</div><div class="card-sub" id="pocketedSub">safe</div></div>
      </div>
      <div style="margin-top:14px">
        <div class="card-label" style="margin-bottom:6px">Snowball</div>
        <div style="display:flex;align-items:baseline;gap:8px">
          <span style="font-size:18px;font-weight:600;font-family:var(--sans)" id="clipSize">$10</span>
          <span class="tag" id="phaseBadge">growth</span>
        </div>
        <div class="snow-track"><div class="snow-fill growth" id="snowFill" style="width:3%"></div></div>
        <div class="snow-labels"><span>$10</span><span id="snowPct">0%</span><span>$100</span></div>
      </div>
    </div>
  </div>

  <!-- Row 3: Pending Bets -->
  <div id="pendingCard" class="card" style="margin-bottom:14px" hidden>
    <div class="card-head"><div class="card-label">Pending Bets</div><span class="tag pending" id="pendingCount">0</span></div>
    <div class="table-wrap" id="pendingTable"></div>
  </div>

  <!-- Row 4: Scanner -->
  <div class="card" style="margin-bottom:14px">
    <div class="card-head"><div class="card-label">Live Scanner</div><button class="btn btn-cyan" id="scanBtn" onclick="runScan()">Scan Now</button></div>
    <div id="scanResults"><div class="empty">Hit "Scan Now" to check Polymarket for expiring markets</div></div>
  </div>

  <!-- Row 5: Equity Curve -->
  <div class="card" style="margin-bottom:14px">
    <div class="card-head"><div class="card-label">Equity Curve</div></div>
    <div class="chart-box"><canvas id="equityChart"></canvas></div>
  </div>

  <!-- Row 6: Tables -->
  <div class="grid g2">
    <div class="card"><div class="card-head"><div class="card-label">Recent Windows</div></div><div class="table-wrap" id="windowsTable"><div class="empty">No windows yet</div></div></div>
    <div class="card"><div class="card-head"><div class="card-label">Recent Bets</div></div><div class="table-wrap" id="betsTable"><div class="empty">No bets yet</div></div></div>
  </div>

</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>
let equityChart=null,lastWindowAt=null;
const $=id=>document.getElementById(id);
async function fetchJSON(u){try{const r=await fetch(u);return await r.json()}catch(e){return null}}
function fmt(n){if(n==null)return'--';return(n>=0?'+':'')+'$'+Math.abs(n).toFixed(2)}
function timeAgo(iso){if(!iso)return'--';const d=new Date(iso),s=(Date.now()-d.getTime())/1000;if(s<60)return Math.floor(s)+'s ago';if(s<3600)return Math.floor(s/60)+'m ago';if(s<86400)return Math.floor(s/3600)+'h ago';return Math.floor(s/86400)+'d ago'}
function shortAddr(a){return a&&a.length>10?a.slice(0,6)+'...'+a.slice(-4):a||''}

// Countdown
function updateCountdown(){
  const el=$('countdown');
  if(!lastWindowAt){el.textContent='';return}
  const next=new Date(lastWindowAt).getTime()+3600000;
  const diff=next-Date.now();
  if(diff<=0){el.textContent='⏱ Window due';return}
  const m=Math.floor(diff/60000),s=Math.floor((diff%60000)/1000);
  el.textContent='Next: '+m+'m '+s+'s';
}
setInterval(updateCountdown,1000);

// Wallet
async function refreshWallet(){
  const w=await fetchJSON('/api/wallet');
  if(!w)return;
  const card=$('walletCard');
  const dot=$('walletDot');
  const addr=$('walletAddr');
  const mt=$('modeTag'),mx=$('modeText');

  if(w.paper_mode){mt.className='mode-tag paper';mx.textContent='Paper'}
  else{mt.className='mode-tag live';mx.textContent='Live'}

  if(w.connected){
    card.classList.add('connected');
    dot.className='wallet-dot on';
    addr.textContent=shortAddr(w.address);
    $('walletBal').textContent=w.balance!=null?'$'+w.balance.toFixed(2):'--';
    $('walletAvail').textContent=w.available!=null?'$'+w.available.toFixed(2):'--';
    $('walletDeployed').textContent='$'+w.deployed.toFixed(2);
    if(w.balance>0){
      const pct=Math.max(2,((w.available||0)/w.balance)*100);
      $('fundBar').style.width=pct+'%';
    }
  } else {
    card.classList.remove('connected');
    dot.className='wallet-dot off';
    addr.textContent=w.paper_mode?'Paper mode':'Not connected';
    $('walletBal').textContent=w.paper_mode?'∞':'--';
    $('walletAvail').textContent=w.paper_mode?'∞':'--';
    $('walletDeployed').textContent='$'+w.deployed.toFixed(2);
  }
}

// Settings
async function loadSettings(){
  const s=await fetchJSON('/api/settings');
  if(!s)return;
  $('sClip').value=s.clip_size;
  $('sMaxBets').value=s.max_bets_per_window;
  $('sMinPrice').value=s.min_price;
  $('sMaxPrice').value=s.max_price;
  $('sMinVol').value=s.min_volume;
  $('sScanInt').value=s.scan_interval;
  $('stratClip').textContent='$'+s.clip_size;
  $('stratMax').textContent=s.max_bets_per_window;
}
async function saveSettings(){
  const body={
    clip_size:parseFloat($('sClip').value),
    max_bets_per_window:parseInt($('sMaxBets').value),
    min_price:parseFloat($('sMinPrice').value),
    max_price:parseFloat($('sMaxPrice').value),
    min_volume:parseFloat($('sMinVol').value),
    scan_interval:parseInt($('sScanInt').value),
  };
  const r=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(r.ok){
    const m=$('saveMsg');m.classList.add('show');
    $('stratClip').textContent='$'+body.clip_size;
    $('stratMax').textContent=body.max_bets_per_window;
    setTimeout(()=>m.classList.remove('show'),2000);
  }
}

// Scanner
async function runScan(){
  const btn=$('scanBtn');btn.textContent='Scanning...';btn.disabled=true;
  const data=await fetchJSON('/api/scan');
  btn.textContent='Scan Now';btn.disabled=false;
  const el=$('scanResults');
  if(!data||data.error){el.innerHTML='<div class="empty">Scan failed: '+(data?.error||'unknown')+'</div>';return}
  let h='<div class="scan-summary"><div class="scan-stat">Raw: <b>'+data.total_raw+'</b></div><div class="scan-stat">Parsed: <b>'+data.total_parsed+'</b></div><div class="scan-stat">Qualifying: <b>'+data.qualifying+'</b></div></div>';
  if(!data.markets.length){h+='<div class="empty">No markets expiring in the next 60 minutes</div>'}
  else{h+='<table><tr><th>Market</th><th>Cat</th><th>Exp</th><th>YES</th><th>NO</th><th>Fav</th><th>Vol</th><th>Status</th></tr>';
    for(const m of data.markets){const q=m.question.substring(0,42)+(m.question.length>42?'…':'');
      h+='<tr><td title="'+m.question+'">'+q+'</td><td>'+m.category+'</td><td>'+m.minutes_to_expiry+'m</td>';
      h+='<td'+(m.fav_side==='YES'?' class="pos"':'')+'>'+m.yes_price.toFixed(2)+'</td>';
      h+='<td'+(m.fav_side==='NO'?' class="pos"':'')+'>'+m.no_price.toFixed(2)+'</td>';
      h+='<td>'+(m.fav_side?'<span class="tag '+(m.fav_side==='YES'?'yes':'no')+'">'+m.fav_side+'</span>':'—')+'</td>';
      h+='<td>$'+(m.volume||0).toLocaleString()+'</td>';
      h+='<td><span class="tag '+(m.qualifies?'qual':'skip')+'">'+(m.qualifies?'QUAL':'SKIP')+'</span></td></tr>'}
    h+='</table><div class="scan-note">Scanned '+new Date(data.scanned_at).toLocaleTimeString()+'</div>'}
  el.innerHTML=h;
}

// Main refresh
async function refresh(){
  const[stats,windows,bets,curve,pending]=await Promise.all([
    fetchJSON('/api/stats'),fetchJSON('/api/windows?limit=20'),
    fetchJSON('/api/bets?limit=30'),fetchJSON('/api/equity-curve'),fetchJSON('/api/pending')]);

  if(stats&&stats.last_window_at)lastWindowAt=stats.last_window_at;

  if(stats){
    const pnl=stats.total_profit||0;
    $('totalPnl').textContent=fmt(pnl);$('totalPnl').className='card-val '+(pnl>=0?'pos':'neg');
    $('totalPnlSub').textContent=(stats.total_bets||0)+' bets | $'+(stats.total_deployed||0).toFixed(0)+' deployed';
    $('winRate').textContent=(stats.win_rate||0).toFixed(1)+'%';
    $('winRate').className='card-val '+(stats.win_rate>=85?'pos':stats.win_rate>=80?'dim':'neg');
    $('winRateSub').textContent=(stats.wins||0)+'W '+(stats.losses||0)+'L '+(stats.pending||0)+'P';
    $('totalWindows').textContent=stats.total_windows||0;
    $('windowsSub').textContent='clip: $'+(stats.current_clip||10).toFixed(2);
    $('pocketed').textContent='$'+(stats.total_pocketed||0).toFixed(2);
    const clip=stats.current_clip||10,pct=Math.min(100,((clip-10)/90)*100);
    $('clipSize').textContent='$'+clip.toFixed(2);
    const fill=$('snowFill');fill.style.width=Math.max(3,pct)+'%';fill.className='snow-fill '+(stats.current_phase||'growth');
    $('snowPct').textContent=pct.toFixed(0)+'%';
    const pb=$('phaseBadge');pb.textContent=stats.current_phase||'growth';pb.className='tag '+(stats.current_phase||'growth');
    const consec=stats.consecutive_losses||0;$('consecLosses').textContent=consec;
    const cb=$('cbStatus'),ct=$('cbText');
    if(consec>=5){cb.className='cb-bar cb-stop';ct.textContent='STOPPED'}
    else if(consec>=3){cb.className='cb-bar cb-warn';ct.textContent='Warning: '+consec+' losses'}
    else{cb.className='cb-bar cb-ok';ct.textContent='All clear'}
  }

  // Pending
  const pc=$('pendingCard');
  if(pending&&pending.length>0){pc.hidden=false;$('pendingCount').textContent=pending.length;
    let ph='<table><tr><th>Market</th><th>Side</th><th>Price</th><th>Amount</th><th>Placed</th></tr>';
    for(const p of pending){const q=(p.market_question||'').substring(0,42)+((p.market_question||'').length>42?'…':'');
      ph+='<tr><td title="'+(p.market_question||'')+'">'+q+'</td><td><span class="tag '+(p.side==='YES'?'yes':'no')+'">'+p.side+'</span></td><td>$'+(p.price||0).toFixed(2)+'</td><td>$'+(p.amount||0).toFixed(2)+'</td><td>'+timeAgo(p.placed_at)+'</td></tr>'}
    ph+='</table>';$('pendingTable').innerHTML=ph}else{pc.hidden=true}

  // Windows
  if(windows&&windows.length>0){let h='<table><tr><th>#</th><th>Time</th><th>Bets</th><th>W/L</th><th>Profit</th><th>Clip</th></tr>';
    for(const w of windows){const p=w.profit||0;h+='<tr><td>'+w.id+'</td><td>'+timeAgo(w.started_at)+'</td><td>'+(w.bets_placed||0)+'</td><td>'+(w.bets_won||0)+'W/'+(w.bets_lost||0)+'L</td><td class="'+(p>=0?'pos':'neg')+'">'+fmt(p)+'</td><td>$'+(w.clip_size||0).toFixed(2)+'</td></tr>'}
    h+='</table>';$('windowsTable').innerHTML=h}

  // Bets
  if(bets&&bets.length>0){let h='<table><tr><th>Market</th><th>Side</th><th>Price</th><th>Amt</th><th>Result</th><th>P&L</th></tr>';
    for(const b of bets){const q=(b.market_question||'').substring(0,38)+((b.market_question||'').length>38?'…':'');const pr=b.profit||0;
      h+='<tr><td title="'+(b.market_question||'')+'">'+q+'</td><td>'+(b.side||'—')+'</td><td>$'+(b.price||0).toFixed(2)+'</td><td>$'+(b.amount||0).toFixed(2)+'</td><td><span class="tag '+(b.result||'pending')+'">'+(b.result||'pending')+'</span></td><td class="'+(b.result==='won'?'pos':b.result==='lost'?'neg':'dim')+'">'+(b.result==='pending'?'—':fmt(pr))+'</td></tr>'}
    h+='</table>';$('betsTable').innerHTML=h}

  // Equity
  if(curve&&curve.length>0){if(equityChart)equityChart.destroy();
    const ctx=$('equityChart').getContext('2d');const d=curve.map(c=>c.cumulative);
    equityChart=new Chart(ctx,{type:'line',data:{labels:curve.map(c=>'W'+c.window),datasets:[{data:d,borderColor:d[d.length-1]>=0?'#22c55e':'#ef4444',backgroundColor:d[d.length-1]>=0?'rgba(34,197,94,0.06)':'rgba(239,68,68,0.06)',fill:true,tension:0.3,pointRadius:1.5,borderWidth:1.5}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:'#52525b',font:{size:9,family:'IBM Plex Mono'}},grid:{color:'rgba(255,255,255,0.03)'}},y:{ticks:{color:'#52525b',font:{size:9,family:'IBM Plex Mono'},callback:v=>'$'+v},grid:{color:'rgba(255,255,255,0.03)'}}},interaction:{intersect:false,mode:'index'}}})}
}

refreshWallet();loadSettings();refresh();runScan();
setInterval(refresh,15000);
setInterval(refreshWallet,30000);
</script>
</body>
</html>"""


HISTORY_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vig — History</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600;700&family=Instrument+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #09090b; --surface: #111114; --surface2: #19191f;
  --border: #27272a; --text: #fafafa; --text-dim: #71717a; --text-muted: #52525b;
  --green: #22c55e; --green-dim: rgba(34,197,94,0.1);
  --red: #ef4444; --red-dim: rgba(239,68,68,0.1);
  --amber: #f59e0b; --amber-dim: rgba(245,158,11,0.1);
  --blue: #3b82f6; --blue-dim: rgba(59,130,246,0.1);
  --cyan: #06b6d4; --cyan-dim: rgba(6,182,212,0.1);
  --mono: 'IBM Plex Mono', monospace;
  --sans: 'Instrument Sans', sans-serif;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--bg); color:var(--text); font-family:var(--mono); font-size:13px; line-height:1.6; }
.header { display:flex; align-items:center; justify-content:space-between; padding:14px 28px; border-bottom:1px solid var(--border); background:var(--surface); position:sticky; top:0; z-index:50; }
.header-left { display:flex; align-items:center; gap:20px; }
.logo { font-family:var(--sans); font-size:24px; font-weight:700; letter-spacing:-1px; color:var(--text); text-decoration:none; }
.logo em { font-style:normal; color:var(--green); }
.nav { display:flex; gap:2px; background:var(--surface2); border-radius:8px; padding:2px; }
.nav a { padding:6px 16px; border-radius:6px; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.8px; color:var(--text-dim); text-decoration:none; transition:all 0.15s; }
.nav a:hover { color:var(--text); }
.nav a.active { color:var(--text); background:var(--bg); }
.container { padding:24px 28px; max-width:1500px; margin:0 auto; }
.tabs { display:flex; gap:2px; margin-bottom:16px; background:var(--surface); border-radius:8px; padding:2px; width:fit-content; border:1px solid var(--border); }
.tab { padding:8px 20px; border-radius:6px; font-size:11px; font-weight:600; cursor:pointer; color:var(--text-dim); transition:all 0.15s; text-transform:uppercase; letter-spacing:0.5px; }
.tab:hover { color:var(--text); }
.tab.active { color:var(--text); background:var(--surface2); }
.filters { display:flex; gap:4px; margin-bottom:14px; }
.fbtn { padding:5px 14px; border-radius:6px; font-size:10px; font-weight:600; cursor:pointer; border:1px solid var(--border); background:transparent; color:var(--text-dim); font-family:var(--mono); transition:all 0.15s; text-transform:uppercase; }
.fbtn:hover { color:var(--text); border-color:var(--text-dim); }
.fbtn.active { color:var(--cyan); border-color:rgba(6,182,212,0.3); background:var(--cyan-dim); }
.card { background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:18px 22px; }
.summary { display:flex; gap:20px; margin-bottom:14px; flex-wrap:wrap; }
.summary b { font-family:var(--sans); font-size:16px; }
.table-wrap { overflow-x:auto; max-height:calc(100vh - 260px); overflow-y:auto; }
table { width:100%; border-collapse:collapse; font-size:12px; }
th { text-align:left; padding:7px 10px; font-size:9px; text-transform:uppercase; letter-spacing:1px; color:var(--text-muted); font-weight:500; border-bottom:1px solid var(--border); white-space:nowrap; position:sticky; top:0; background:var(--surface); z-index:1; }
td { padding:7px 10px; border-bottom:1px solid rgba(39,39,42,0.5); white-space:nowrap; font-size:11px; }
tr:hover td { background:rgba(255,255,255,0.015); }
.tag { display:inline-block; padding:2px 7px; border-radius:4px; font-size:9px; font-weight:600; text-transform:uppercase; }
.tag.won { background:var(--green-dim); color:var(--green); }
.tag.lost { background:var(--red-dim); color:var(--red); }
.tag.pending { background:var(--blue-dim); color:var(--blue); }
.tag.growth { background:var(--blue-dim); color:var(--blue); }
.tag.harvest { background:var(--amber-dim); color:var(--amber); }
.pos { color:var(--green); }
.neg { color:var(--red); }
.dim { color:var(--text-dim); }
.empty { text-align:center; padding:32px; color:var(--text-muted); }
@media (max-width:600px) { .container{padding:12px;} .summary{gap:10px;} }
</style>
</head>
<body>
<div class="header">
  <div class="header-left">
    <a href="/" class="logo">V<em>ig</em></a>
    <div class="nav"><a href="/">Dashboard</a><a href="/history" class="active">History</a></div>
  </div>
</div>
<div class="container">
  <div class="tabs">
    <div class="tab active" onclick="switchTab('bets',this)">Bets</div>
    <div class="tab" onclick="switchTab('windows',this)">Windows</div>
    <div class="tab" onclick="switchTab('daily',this)">Daily</div>
  </div>
  <div id="betsView">
    <div class="filters">
      <div class="fbtn active" onclick="filterBets('all',this)">All</div>
      <div class="fbtn" onclick="filterBets('won',this)">Won</div>
      <div class="fbtn" onclick="filterBets('lost',this)">Lost</div>
      <div class="fbtn" onclick="filterBets('pending',this)">Pending</div>
    </div>
    <div class="summary" id="betsSummary"></div>
    <div class="card"><div class="table-wrap" id="betsTable"><div class="empty">Loading...</div></div></div>
  </div>
  <div id="windowsView" hidden>
    <div class="summary" id="windowsSummary"></div>
    <div class="card"><div class="table-wrap" id="windowsTable"><div class="empty">Loading...</div></div></div>
  </div>
  <div id="dailyView" hidden>
    <div class="card"><div class="table-wrap" id="dailyTable"><div class="empty">Loading...</div></div></div>
  </div>
</div>
<script>
let curTab='bets',curFilter='all';
async function fetchJSON(u){try{const r=await fetch(u);return await r.json()}catch(e){return null}}
function fmt(n){if(n==null)return'--';return(n>=0?'+':'')+'$'+Math.abs(n).toFixed(2)}
function fmtD(iso){if(!iso)return'--';try{const d=new Date(iso);return d.toLocaleDateString('en-US',{month:'short',day:'numeric'})+' '+d.toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit'})}catch(e){return iso}}
function switchTab(t,el){curTab=t;document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));el.classList.add('active');
  document.getElementById('betsView').hidden=t!=='bets';document.getElementById('windowsView').hidden=t!=='windows';document.getElementById('dailyView').hidden=t!=='daily';load()}
function filterBets(f,el){curFilter=f;document.querySelectorAll('.fbtn').forEach(x=>x.classList.remove('active'));el.classList.add('active');load()}
async function load(){
  if(curTab==='bets'){const url=curFilter==='all'?'/api/history/bets?limit=500':'/api/history/bets?limit=500&result='+curFilter;
    const d=await fetchJSON(url);if(!d||!d.bets||!d.bets.length){document.getElementById('betsTable').innerHTML='<div class="empty">No bets</div>';document.getElementById('betsSummary').innerHTML='';return}
    const b=d.bets,w=b.filter(x=>x.result==='won').length,l=b.filter(x=>x.result==='lost').length,tp=b.reduce((s,x)=>s+(x.profit||0),0),td=b.reduce((s,x)=>s+(x.amount||0),0);
    document.getElementById('betsSummary').innerHTML='<div>Total: <b>'+d.total+'</b></div><div>Wins: <b class="pos">'+w+'</b></div><div>Losses: <b class="neg">'+l+'</b></div><div>Profit: <b class="'+(tp>=0?'pos':'neg')+'">'+fmt(tp)+'</b></div><div>Deployed: <b>$'+td.toFixed(0)+'</b></div>';
    let h='<table><tr><th>#</th><th>Date</th><th>Market</th><th>Side</th><th>Price</th><th>Amt</th><th>Result</th><th>P&L</th><th>Win</th></tr>';
    for(const x of b){const q=(x.market_question||'').substring(0,45)+((x.market_question||'').length>45?'…':'');
      h+='<tr><td>'+x.id+'</td><td>'+fmtD(x.placed_at)+'</td><td title="'+(x.market_question||'')+'">'+q+'</td><td>'+(x.side||'—')+'</td><td>$'+(x.price||0).toFixed(2)+'</td><td>$'+(x.amount||0).toFixed(2)+'</td><td><span class="tag '+(x.result||'pending')+'">'+(x.result||'pending')+'</span></td><td class="'+(x.result==='won'?'pos':x.result==='lost'?'neg':'dim')+'">'+(x.result==='pending'?'—':fmt(x.profit))+'</td><td>W'+(x.window_id||'—')+'</td></tr>'}
    h+='</table>';document.getElementById('betsTable').innerHTML=h}
  if(curTab==='windows'){const d=await fetchJSON('/api/history/windows?limit=500');if(!d||!d.windows||!d.windows.length){document.getElementById('windowsTable').innerHTML='<div class="empty">No windows</div>';return}
    const w=d.windows,tp=w.reduce((s,x)=>s+(x.profit||0),0),tb=w.reduce((s,x)=>s+(x.bets_placed||0),0),tpk=w.reduce((s,x)=>s+(x.pocketed||0),0);
    document.getElementById('windowsSummary').innerHTML='<div>Windows: <b>'+d.total+'</b></div><div>Bets: <b>'+tb+'</b></div><div>Profit: <b class="'+(tp>=0?'pos':'neg')+'">'+fmt(tp)+'</b></div><div>Pocketed: <b class="pos">$'+tpk.toFixed(2)+'</b></div>';
    let h='<table><tr><th>#</th><th>Date</th><th>Bets</th><th>W</th><th>L</th><th>Deployed</th><th>Profit</th><th>Pocketed</th><th>Clip</th><th>Phase</th></tr>';
    for(const x of w){const p=x.profit||0;h+='<tr><td>'+x.id+'</td><td>'+fmtD(x.started_at)+'</td><td>'+(x.bets_placed||0)+'</td><td class="pos">'+(x.bets_won||0)+'</td><td class="neg">'+(x.bets_lost||0)+'</td><td>$'+(x.deployed||0).toFixed(2)+'</td><td class="'+(p>=0?'pos':'neg')+'">'+fmt(p)+'</td><td>$'+(x.pocketed||0).toFixed(2)+'</td><td>$'+(x.clip_size||0).toFixed(2)+'</td><td><span class="tag '+(x.phase||'growth')+'">'+(x.phase||'—')+'</span></td></tr>'}
    h+='</table>';document.getElementById('windowsTable').innerHTML=h}
  if(curTab==='daily'){const d=await fetchJSON('/api/history/daily');if(!d||!d.length){document.getElementById('dailyTable').innerHTML='<div class="empty">No data</div>';return}
    let h='<table><tr><th>Date</th><th>Bets</th><th>Won</th><th>Lost</th><th>Win Rate</th><th>Deployed</th><th>Profit</th></tr>';
    for(const x of d){const p=x.profit||0;h+='<tr><td>'+x.date+'</td><td>'+x.total_bets+'</td><td class="pos">'+(x.wins||0)+'</td><td class="neg">'+(x.losses||0)+'</td><td class="'+(x.win_rate>=85?'pos':x.win_rate>=80?'dim':'neg')+'">'+(x.win_rate||0)+'%</td><td>$'+(x.deployed||0).toFixed(0)+'</td><td class="'+(p>=0?'pos':'neg')+'">'+fmt(p)+'</td></tr>'}
    h+='</table>';document.getElementById('dailyTable').innerHTML=h}
}
load();
</script>
</body>
</html>"""
