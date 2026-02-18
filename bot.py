"""
Vig - Polymarket Rolling Bet Bot
==================================
Strategy: Always hold up to MAX_BETS active positions.
Each position: YES token on any market priced $0.60-$0.80 expiring within 60 mins.
Claims resolved positions in the background and redeploys capital.
Includes a live dashboard for monitoring and withdrawals.

Setup:
    pip install py-clob-client python-dotenv web3 requests flask

Run:
    python bot.py
"""

import os
import json
import time
import logging
import threading
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from flask import Flask, request as flask_request, jsonify, Response

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.order_builder.constants import BUY
from py_clob_client.constants import POLYGON

from web3 import Web3

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("vig")

# ── Config ────────────────────────────────────────────────────────────────────

PRIVATE_KEY     = os.getenv("PRIVATE_KEY")
RPC_URL         = os.getenv("RPC_URL", "https://polygon-rpc.com")

MAX_BETS        = int(os.getenv("MAX_BETS", "10"))
BET_SIZE        = float(os.getenv("BET_SIZE", "10"))
MIN_PRICE       = float(os.getenv("MIN_PRICE", "0.60"))
MAX_PRICE       = float(os.getenv("MAX_PRICE", "0.80"))
EXPIRY_WINDOW   = int(os.getenv("EXPIRY_WINDOW", "60"))
POLL_SECONDS    = int(os.getenv("POLL_SECONDS", "60"))
PORT            = int(os.getenv("PORT", "8080"))

CLOB_HOST       = "https://clob.polymarket.com"
GAMMA_API       = "https://gamma-api.polymarket.com"

CTF_ADDRESS     = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
USDC_ADDRESS    = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

CTF_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "collateralToken", "type": "address"},
            {"internalType": "bytes32", "name": "parentCollectionId", "type": "bytes32"},
            {"internalType": "bytes32", "name": "conditionId", "type": "bytes32"},
            {"internalType": "uint256[]", "name": "indexSets", "type": "uint256[]"},
        ],
        "name": "redeemPositions",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
]

POSITIONS_FILE = "positions.json"
TRADES_FILE = "trades.json"

# ── Shared State ──────────────────────────────────────────────────────────────

w3_instance = None
account_instance = None
usdc_contract = None

bot_state = {
    "running": False,
    "started_at": None,
    "last_tick": None,
    "wallet": None,
    "positions": [],
    "total_bets": 0,
    "total_claimed": 0,
    "total_spent": 0.0,
}

trade_history = []


# ── Persistence ───────────────────────────────────────────────────────────────

def load_positions() -> list:
    if os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE) as f:
            return json.load(f)
    return []


def save_positions(positions: list):
    with open(POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2)


def load_trades() -> list:
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE) as f:
            return json.load(f)
    return []


def save_trades(trades: list):
    with open(TRADES_FILE, "w") as f:
        json.dump(trades[-500:], f, indent=2)


def add_trade(trade: dict):
    trade_history.append(trade)
    save_trades(trade_history)


# ── Clients ───────────────────────────────────────────────────────────────────

def build_clob_client() -> ClobClient:
    if not PRIVATE_KEY:
        raise ValueError("PRIVATE_KEY not set in .env")
    client = ClobClient(host=CLOB_HOST, key=PRIVATE_KEY, chain_id=POLYGON)
    client.set_api_creds(client.create_or_derive_api_creds())
    log.info("CLOB ready. Address: %s", client.get_address())
    return client


def build_web3() -> tuple:
    global w3_instance, account_instance, usdc_contract
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to RPC: {RPC_URL}")
    account = w3.eth.account.from_key(PRIVATE_KEY)
    ctf = w3.eth.contract(
        address=Web3.to_checksum_address(CTF_ADDRESS),
        abi=CTF_ABI,
    )
    usdc_contract = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_ADDRESS),
        abi=ERC20_ABI,
    )
    w3_instance = w3
    account_instance = account
    log.info("Web3 ready. Wallet: %s", account.address)
    return w3, account, ctf


# ── Balance Queries ───────────────────────────────────────────────────────────

def get_usdc_balance() -> float:
    if not usdc_contract or not account_instance:
        return 0.0
    try:
        raw = usdc_contract.functions.balanceOf(account_instance.address).call()
        return raw / 1e6
    except Exception as e:
        log.error("Balance query failed: %s", e)
        return 0.0


def get_matic_balance() -> float:
    if not w3_instance or not account_instance:
        return 0.0
    try:
        raw = w3_instance.eth.get_balance(account_instance.address)
        return raw / 1e18
    except Exception:
        return 0.0


# ── Market Scanner ────────────────────────────────────────────────────────────

def scan_markets(active_token_ids: set) -> list:
    qualifying = []
    now = datetime.now(timezone.utc)
    end_max = now + timedelta(minutes=EXPIRY_WINDOW)

    try:
        resp = requests.get(
            f"{GAMMA_API}/markets",
            params={
                "closed": "false",
                "limit": 100,
                "order": "endDate",
                "ascending": "true",
                "end_date_min": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_date_max": end_max.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            timeout=10,
        )
        resp.raise_for_status()
        markets = resp.json()

        for market in markets:
            try:
                end_str = market.get("endDateIso") or market.get("end_date_iso")
                if not end_str:
                    continue
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                mins_to_expiry = (end_dt - now).total_seconds() / 60

                if mins_to_expiry <= 0:
                    continue

                tokens = market.get("clobTokenIds")
                outcome_prices = market.get("outcomePrices")
                outcomes = market.get("outcomes")

                if not tokens or not outcome_prices or not outcomes:
                    continue

                try:
                    token_list = json.loads(tokens) if isinstance(tokens, str) else tokens
                    price_list = json.loads(outcome_prices) if isinstance(outcome_prices, str) else outcome_prices
                    outcome_list = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
                except (json.JSONDecodeError, TypeError):
                    continue

                best_idx = None
                best_price = 0.0
                for i in range(min(len(token_list), len(price_list), len(outcome_list))):
                    p = float(price_list[i])
                    if MIN_PRICE <= p <= MAX_PRICE and p > best_price:
                        best_price = p
                        best_idx = i

                if best_idx is None:
                    continue

                token_id = token_list[best_idx]
                outcome_name = str(outcome_list[best_idx])
                price = best_price

                if token_id in active_token_ids:
                    continue

                question = market.get("question", "Unknown")
                label = f"{question} → {outcome_name}"

                qualifying.append({
                    "market_id": market.get("id"),
                    "question": label,
                    "token_id": token_id,
                    "condition_id": market.get("conditionId"),
                    "price": price,
                    "mins_to_expiry": round(mins_to_expiry, 1),
                    "end_date": end_str,
                })

            except Exception as e:
                log.debug("Skipped market: %s", e)
                continue

        log.info("Scan complete — %d qualifying markets found", len(qualifying))

    except Exception as e:
        log.error("Scan failed: %s", e)

    qualifying.sort(key=lambda m: m["price"], reverse=True)
    return qualifying


# ── Bet Placement ─────────────────────────────────────────────────────────────

def place_bet(client: ClobClient, market: dict) -> dict | None:
    token_id = market["token_id"]
    price = market["price"]

    log.info(
        "Placing bet: %s | price=%.2f | expiry=%.0fmin",
        market["question"][:60],
        price,
        market["mins_to_expiry"],
    )

    try:
        args = OrderArgs(
            token_id=token_id,
            price=round(price, 4),
            size=BET_SIZE,
            side=BUY,
        )
        result = client.create_and_post_order(args)
        order_id = result.get("orderID", "?")
        log.info("Bet placed. Order ID: %s", order_id)

        cost = round(price * BET_SIZE, 2)
        position = {
            "order_id": order_id,
            "market_id": market["market_id"],
            "question": market["question"],
            "token_id": token_id,
            "condition_id": market["condition_id"],
            "price": price,
            "size": BET_SIZE,
            "cost": cost,
            "end_date": market["end_date"],
            "placed_at": datetime.now(timezone.utc).isoformat(),
            "claimed": False,
        }

        bot_state["total_bets"] += 1
        bot_state["total_spent"] += cost
        add_trade({
            "type": "BET",
            "question": market["question"][:80],
            "price": price,
            "size": BET_SIZE,
            "cost": cost,
            "time": datetime.now(timezone.utc).isoformat(),
        })

        return position

    except Exception as e:
        log.error("Failed to place bet: %s", e)
        return None


# ── Claim / Settlement ────────────────────────────────────────────────────────

def check_market_resolved(position: dict) -> bool:
    try:
        resp = requests.get(
            f"{GAMMA_API}/markets/{position['market_id']}",
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("closed", False) or data.get("resolved", False)
    except Exception:
        pass
    return False


def try_claim(w3: Web3, account, ctf, position: dict) -> bool:
    condition_id = position.get("condition_id")
    if not condition_id:
        log.warning("No condition_id for position %s — cannot claim", position.get("order_id"))
        return False

    try:
        log.info("Claiming: %s", position["question"][:60])

        tx = ctf.functions.redeemPositions(
            Web3.to_checksum_address(USDC_ADDRESS),
            b"\x00" * 32,
            bytes.fromhex(condition_id.replace("0x", "")),
            [1, 2],
        ).build_transaction({
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gas": 200_000,
            "gasPrice": w3.eth.gas_price,
        })

        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if receipt.status == 1:
            log.info("Claim successful. TX: %s", tx_hash.hex())
            bot_state["total_claimed"] += 1
            add_trade({
                "type": "CLAIM",
                "question": position["question"][:80],
                "tx": tx_hash.hex(),
                "time": datetime.now(timezone.utc).isoformat(),
            })
            return True
        else:
            log.warning("Claim tx reverted. TX: %s", tx_hash.hex())
            return False

    except Exception as e:
        err = str(e)
        if "revert" in err.lower():
            log.debug("Market not yet redeemable: %s", position["question"][:40])
        else:
            log.error("Claim error: %s", e)
        return False


# ── Dashboard ─────────────────────────────────────────────────────────────────

flask_app = Flask(__name__)
flask_app.logger.setLevel(logging.WARNING)
werkzeug_log = logging.getLogger("werkzeug")
werkzeug_log.setLevel(logging.WARNING)

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vig Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;background:#0a0a0f;color:#e0e0e0;min-height:100vh;padding:20px}
.c{max-width:820px;margin:0 auto}
h1{font-size:1.5rem;color:#fff;margin-bottom:4px;display:flex;align-items:center;gap:8px}
.sub{color:#666;font-size:0.82rem;margin-bottom:24px}
.wallet{font-family:monospace;font-size:0.75rem;color:#555;margin-bottom:20px;word-break:break-all}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:24px}
.card{background:#141420;border:1px solid #1e1e30;border-radius:12px;padding:16px}
.card .l{font-size:0.7rem;color:#888;text-transform:uppercase;letter-spacing:.5px}
.card .v{font-size:1.6rem;font-weight:700;margin-top:4px;color:#fff}
.card .v.g{color:#22c55e}
.card .v.r{color:#ef4444}
.card .v.b{color:#3b82f6}
.sec{background:#141420;border:1px solid #1e1e30;border-radius:12px;padding:16px;margin-bottom:16px}
.sec h2{font-size:0.85rem;color:#aaa;margin-bottom:12px;text-transform:uppercase;letter-spacing:.5px}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:0.68rem;color:#555;text-transform:uppercase;padding:6px 8px;border-bottom:1px solid #1e1e30}
td{padding:8px;font-size:0.82rem;border-bottom:1px solid #0e0e18}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.68rem;font-weight:600}
.badge.bet{background:#1e3a5f;color:#60a5fa}
.badge.claim{background:#1a3f2a;color:#22c55e}
.badge.withdraw{background:#3f2a1a;color:#f59e0b}
.wf{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
input,button{font-family:inherit;font-size:0.85rem;padding:8px 12px;border-radius:8px;border:1px solid #1e1e30;background:#0a0a0f;color:#e0e0e0}
input{flex:1;min-width:120px}
input:focus{outline:none;border-color:#3b82f6}
button{background:#3b82f6;border:none;color:white;font-weight:600;cursor:pointer;white-space:nowrap}
button:hover{background:#2563eb}
button:disabled{opacity:.5;cursor:not-allowed}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%}
.dot.on{background:#22c55e;box-shadow:0 0 6px #22c55e}
.dot.off{background:#ef4444}
.msg{margin-top:8px;font-size:0.8rem;padding:8px;border-radius:6px}
.msg.ok{background:#1a3f2a;color:#22c55e}
.msg.err{background:#3f1a1a;color:#ef4444}
.empty{color:#444;font-style:italic;padding:12px 0;font-size:0.85rem}
.trunc{max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
@media(max-width:600px){.cards{grid-template-columns:1fr 1fr}.trunc{max-width:140px}}
</style>
</head>
<body>
<div class="c">
  <h1><span class="dot" id="dot"></span> Vig</h1>
  <div class="sub" id="sub">Connecting...</div>
  <div class="wallet" id="wallet"></div>

  <div class="cards">
    <div class="card"><div class="l">USDC Balance</div><div class="v g" id="bal">--</div></div>
    <div class="card"><div class="l">Active Bets</div><div class="v b" id="active">--</div></div>
    <div class="card"><div class="l">Total Bets</div><div class="v" id="tbets">--</div></div>
    <div class="card"><div class="l">Claimed</div><div class="v g" id="tclaim">--</div></div>
    <div class="card"><div class="l">Total Spent</div><div class="v" id="tspent">--</div></div>
    <div class="card"><div class="l">Gas (POL)</div><div class="v" id="gas">--</div></div>
  </div>

  <div class="sec">
    <h2>Active Positions</h2>
    <div id="pos"><div class="empty">No active positions</div></div>
  </div>

  <div class="sec">
    <h2>Recent Trades</h2>
    <div id="trades"><div class="empty">No trades yet</div></div>
  </div>

  <div class="sec">
    <h2>Withdraw USDC</h2>
    <div class="wf">
      <input type="text" id="wAddr" placeholder="0x... recipient address" />
      <input type="number" id="wAmt" placeholder="Amount" step="0.01" style="max-width:120px" />
      <button onclick="doWithdraw()" id="wBtn">Send</button>
    </div>
    <div id="wMsg"></div>
  </div>
</div>

<script>
async function refresh(){
  try{
    const r=await fetch('/api/status');
    const d=await r.json();

    document.getElementById('dot').className='dot '+(d.running?'on':'off');
    const tick=d.last_tick?new Date(d.last_tick).toLocaleTimeString():'--';
    document.getElementById('sub').textContent=d.running
      ?'Running · Last tick '+tick+' · Poll '+d.config.poll_seconds+'s'
      :'Offline';
    document.getElementById('wallet').textContent=d.wallet||'';
    document.getElementById('bal').textContent='$'+d.usdc_balance.toFixed(2);
    document.getElementById('active').textContent=d.active_positions+'/'+d.max_bets;
    document.getElementById('tbets').textContent=d.total_bets;
    document.getElementById('tclaim').textContent=d.total_claimed;
    document.getElementById('tspent').textContent='$'+d.total_spent.toFixed(2);
    document.getElementById('gas').textContent=d.gas_balance.toFixed(4);

    const pe=document.getElementById('pos');
    if(!d.positions.length){pe.innerHTML='<div class="empty">No active positions</div>'}
    else{
      let h='<table><tr><th>Market</th><th>Price</th><th>Cost</th><th>Expires</th></tr>';
      d.positions.forEach(p=>{
        const exp=new Date(p.end_date).toLocaleTimeString();
        const cost=p.cost?'$'+p.cost.toFixed(2):'--';
        h+=`<tr><td class="trunc">${p.question}</td><td>$${p.price.toFixed(2)}</td><td>${cost}</td><td>${exp}</td></tr>`;
      });
      pe.innerHTML=h+'</table>';
    }

    const te=document.getElementById('trades');
    if(!d.trades.length){te.innerHTML='<div class="empty">No trades yet</div>'}
    else{
      let h='<table><tr><th>Type</th><th>Market</th><th>Details</th><th>Time</th></tr>';
      d.trades.slice().reverse().forEach(t=>{
        const cls=t.type.toLowerCase();
        const det=t.type==='BET'?'$'+(t.cost||0).toFixed(2)+' @ '+(t.price||0).toFixed(2)
                  :t.type==='CLAIM'?'Redeemed'
                  :t.type==='WITHDRAW'?'Sent':'--';
        const tm=new Date(t.time).toLocaleTimeString();
        h+=`<tr><td><span class="badge ${cls}">${t.type}</span></td><td class="trunc">${t.question||''}</td><td>${det}</td><td>${tm}</td></tr>`;
      });
      te.innerHTML=h+'</table>';
    }
  }catch(e){
    document.getElementById('dot').className='dot off';
    document.getElementById('sub').textContent='Connection error';
  }
}

async function doWithdraw(){
  const addr=document.getElementById('wAddr').value.trim();
  const amt=document.getElementById('wAmt').value.trim();
  const msg=document.getElementById('wMsg');
  const btn=document.getElementById('wBtn');
  if(!addr||!amt){msg.innerHTML='<div class="msg err">Enter address and amount</div>';return}
  btn.disabled=true;btn.textContent='Sending...';msg.innerHTML='';
  try{
    const r=await fetch('/api/withdraw',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({to:addr,amount:parseFloat(amt)})});
    const d=await r.json();
    if(d.success){
      msg.innerHTML=`<div class="msg ok">Sent! TX: ${d.tx_hash.slice(0,20)}...</div>`;
      document.getElementById('wAmt').value='';
      setTimeout(refresh,3000);
    }else{msg.innerHTML=`<div class="msg err">${d.error}</div>`}
  }catch(e){msg.innerHTML='<div class="msg err">Request failed</div>'}
  btn.disabled=false;btn.textContent='Send';
}

refresh();
setInterval(refresh,10000);
</script>
</body>
</html>"""


@flask_app.route("/")
def dashboard():
    return Response(DASHBOARD_HTML, content_type="text/html")


@flask_app.route("/api/status")
def api_status():
    return jsonify({
        "running": bot_state["running"],
        "started_at": bot_state["started_at"],
        "last_tick": bot_state["last_tick"],
        "wallet": bot_state["wallet"],
        "usdc_balance": get_usdc_balance(),
        "gas_balance": get_matic_balance(),
        "active_positions": len(bot_state["positions"]),
        "max_bets": MAX_BETS,
        "positions": bot_state["positions"],
        "total_bets": bot_state["total_bets"],
        "total_claimed": bot_state["total_claimed"],
        "total_spent": bot_state["total_spent"],
        "trades": trade_history[-30:],
        "config": {
            "bet_size": BET_SIZE,
            "min_price": MIN_PRICE,
            "max_price": MAX_PRICE,
            "expiry_window": EXPIRY_WINDOW,
            "poll_seconds": POLL_SECONDS,
        },
    })


@flask_app.route("/api/withdraw", methods=["POST"])
def api_withdraw():
    if not w3_instance or not account_instance or not usdc_contract:
        return jsonify({"success": False, "error": "Bot not initialized"})

    data = flask_request.get_json()
    to_addr = data.get("to", "").strip()
    amount = data.get("amount", 0)

    if not to_addr or not Web3.is_address(to_addr):
        return jsonify({"success": False, "error": "Invalid address"})
    if amount <= 0:
        return jsonify({"success": False, "error": "Invalid amount"})

    try:
        raw_amount = int(amount * 1e6)
        tx = usdc_contract.functions.transfer(
            Web3.to_checksum_address(to_addr),
            raw_amount,
        ).build_transaction({
            "from": account_instance.address,
            "nonce": w3_instance.eth.get_transaction_count(account_instance.address),
            "gas": 100_000,
            "gasPrice": w3_instance.eth.gas_price,
        })

        signed = account_instance.sign_transaction(tx)
        tx_hash = w3_instance.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if receipt.status == 1:
            log.info("Withdraw %s USDC to %s. TX: %s", amount, to_addr, tx_hash.hex())
            add_trade({
                "type": "WITHDRAW",
                "question": f"${amount} USDC to {to_addr[:10]}...",
                "time": datetime.now(timezone.utc).isoformat(),
            })
            return jsonify({"success": True, "tx_hash": tx_hash.hex()})
        else:
            return jsonify({"success": False, "error": "Transaction reverted"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def start_dashboard():
    log.info("Dashboard on port %d", PORT)
    flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)


# ── Main Loop ─────────────────────────────────────────────────────────────────

def run():
    if not PRIVATE_KEY:
        raise ValueError("PRIVATE_KEY not set in .env")

    log.info("Starting Vig rolling bet bot")
    log.info("Max bets     : %d", MAX_BETS)
    log.info("Bet size     : $%.0f USDC", BET_SIZE)
    log.info("Price range  : $%.2f - $%.2f", MIN_PRICE, MAX_PRICE)
    log.info("Expiry window: %d mins", EXPIRY_WINDOW)
    log.info("Poll interval: %ds", POLL_SECONDS)

    clob = build_clob_client()
    w3, account, ctf = build_web3()

    global trade_history
    positions = load_positions()
    trade_history = load_trades()

    bot_state["running"] = True
    bot_state["started_at"] = datetime.now(timezone.utc).isoformat()
    bot_state["wallet"] = account.address
    bot_state["positions"] = positions

    threading.Thread(target=start_dashboard, daemon=True).start()

    while True:
        try:
            bot_state["last_tick"] = datetime.now(timezone.utc).isoformat()
            log.info("── Tick ──────────────────────────────────────────")
            log.info("Active positions: %d / %d", len(positions), MAX_BETS)

            for pos in [p for p in positions if not p.get("claimed")]:
                if check_market_resolved(pos):
                    success = try_claim(w3, account, ctf, pos)
                    if success:
                        pos["claimed"] = True
                        pos["claimed_at"] = datetime.now(timezone.utc).isoformat()

            positions = [p for p in positions if not p.get("claimed")]
            save_positions(positions)
            bot_state["positions"] = positions

            slots_available = MAX_BETS - len(positions)
            log.info("Slots available: %d", slots_available)

            if slots_available > 0:
                active_token_ids = {p["token_id"] for p in positions}
                candidates = scan_markets(active_token_ids)

                for market in candidates[:slots_available]:
                    position = place_bet(clob, market)
                    if position:
                        positions.append(position)
                        save_positions(positions)
                        bot_state["positions"] = positions
                        time.sleep(1)
            else:
                log.info("Portfolio full — skipping scan")

        except KeyboardInterrupt:
            log.info("Shutting down.")
            save_positions(positions)
            break
        except Exception as e:
            log.error("Unexpected error in main loop: %s", e)

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run()
