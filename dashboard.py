"""
Vig v1 Dashboard — Web UI for monitoring bot performance.
Run: python3 dashboard.py
"""
import os
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import httpx

app = FastAPI(title="Vig Dashboard")

DB_PATH = os.getenv("DB_PATH", "vig.db")
GAMMA_URL = "https://gamma-api.polymarket.com"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── API Endpoints ─────────────────────────────────────────────

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

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vig Dashboard</title>
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
.status-badge { display:inline-flex; align-items:center; gap:6px; padding:4px 12px; border-radius:20px; font-size:11px; font-weight:500; text-transform:uppercase; letter-spacing:0.5px; }
.status-badge.paper { background:var(--amber-dim); color:var(--amber); }
.status-badge.live { background:var(--green-dim); color:var(--green); }
.status-badge.offline { background:var(--red-dim); color:var(--red); }
.status-dot { width:6px; height:6px; border-radius:50%; background:currentColor; animation:pulse 2s ease-in-out infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
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
    <div class="logo">V<span>ig</span></div>
    <div class="status-badge offline" id="statusBadge"><div class="status-dot"></div><span id="statusText">Loading...</span></div>
  </div>
  <div class="header-right">
    <span class="countdown" id="countdown"></span>
    <span class="refresh-label" id="lastUpdate"></span>
  </div>
</div>
<div class="container">

  <!-- Stats Row -->
  <div class="grid grid-4">
    <div class="card"><div class="card-title">Total P&L</div><div class="card-value" id="totalPnl">--</div><div class="card-sub" id="totalPnlSub"></div></div>
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

  <!-- Pending Bets -->
  <div class="card" style="margin-bottom:16px" id="pendingCard" hidden>
    <div class="card-header">
      <div class="card-title">Pending Bets</div>
      <span class="tag pending" id="pendingCount">0</span>
    </div>
    <div class="table-wrap" id="pendingTable"></div>
  </div>

  <!-- Live Scanner -->
  <div class="card" style="margin-bottom:16px">
    <div class="card-header">
      <div class="card-title">Live Scanner</div>
      <button class="btn btn-cyan" id="scanBtn" onclick="runScan()">Scan Now</button>
    </div>
    <div id="scanResults">
      <div class="empty"><div class="empty-icon">&#9673;</div><div>Hit "Scan Now" to check Polymarket for expiring markets</div></div>
    </div>
  </div>

  <!-- Equity Curve -->
  <div class="card" style="margin-bottom:16px"><div class="card-header"><div class="card-title">Equity Curve</div></div><div class="chart-container"><canvas id="equityChart"></canvas></div></div>

  <!-- Windows + Bets Tables -->
  <div class="grid grid-2">
    <div class="card"><div class="card-header"><div class="card-title">Recent Windows</div></div><div class="table-wrap" id="windowsTable"><div class="empty"><div class="empty-icon">&#9678;</div><div>No windows yet</div></div></div></div>
    <div class="card"><div class="card-header"><div class="card-title">Recent Bets</div></div><div class="table-wrap" id="betsTable"><div class="empty"><div class="empty-icon">&#9678;</div><div>No bets yet</div></div></div></div>
  </div>

</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>
let equityChart=null;
let lastWindowAt=null;

async function fetchJSON(u){try{const r=await fetch(u);return await r.json()}catch(e){return null}}
function fmt(n){if(n==null)return'--';return(n>=0?'+':'')+'$'+Math.abs(n).toFixed(2)}
function timeAgo(iso){if(!iso)return'--';const d=new Date(iso),s=(Date.now()-d.getTime())/1000;if(s<60)return Math.floor(s)+'s ago';if(s<3600)return Math.floor(s/60)+'m ago';if(s<86400)return Math.floor(s/3600)+'h ago';return Math.floor(s/86400)+'d ago'}

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
    html+='<div class="scan-note">Scanned at '+new Date(data.scanned_at).toLocaleTimeString()+' | Window ends '+new Date(data.window_end).toLocaleTimeString()+'</div>';
  }
  el.innerHTML=html;
}

async function refresh(){
  const[stats,windows,bets,curve,pending]=await Promise.all([
    fetchJSON('/api/stats'),fetchJSON('/api/windows?limit=20'),
    fetchJSON('/api/bets?limit=30'),fetchJSON('/api/equity-curve'),
    fetchJSON('/api/pending'),
  ]);

  // Status
  const b=document.getElementById('statusBadge'),st=document.getElementById('statusText');
  if(!stats||stats.total_bets===0){b.className='status-badge offline';st.textContent='No data'}
  else if(stats.mode==='paper'){b.className='status-badge paper';st.textContent='Paper'}
  else{b.className='status-badge live';st.textContent='Live'}

  // Countdown
  if(stats&&stats.last_window_at) lastWindowAt=stats.last_window_at;

  if(stats){
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
      ph+='<td>'+timeAgo(p.placed_at)+'</td></tr>';
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

refresh();setInterval(refresh,15000);
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
