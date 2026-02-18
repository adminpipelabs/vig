"""
Vig - Polymarket Swing Trading Bot
====================================
Strategy: Buy cheap outcomes, sell at 2x.
- Scan high-volume markets for outcomes priced BUY_BELOW
- Place BUY limit order
- Place SELL limit order at SELL_AT target
- Dashboard for monitoring + withdrawals

Run:
    python bot.py
"""

import os
import json
import time
import logging
import threading
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from flask import Flask, request as flask_request, jsonify, Response

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, CreateOrderOptions
from py_clob_client.order_builder.constants import BUY, SELL
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
BET_SIZE        = float(os.getenv("BET_SIZE", "5"))
BUY_BELOW       = float(os.getenv("BUY_BELOW", "0.25"))
SELL_AT         = float(os.getenv("SELL_AT", "0.40"))
MIN_VOLUME      = float(os.getenv("MIN_VOLUME", "10000"))
POLL_SECONDS    = int(os.getenv("POLL_SECONDS", "120"))
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
clob_client = None

bot_state = {
    "running": False,
    "started_at": None,
    "last_tick": None,
    "wallet": None,
    "positions": [],
    "total_buys": 0,
    "total_sells": 0,
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
    """Find high-volume markets with outcomes priced below BUY_BELOW."""
    qualifying = []

    try:
        resp = requests.get(
            f"{GAMMA_API}/markets",
            params={
                "closed": "false",
                "limit": 100,
                "order": "volumeNum",
                "ascending": "false",
                "volume_num_min": int(MIN_VOLUME),
            },
            timeout=10,
        )
        resp.raise_for_status()
        markets = resp.json()

        for market in markets:
            try:
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

                volume = float(market.get("volumeNum") or market.get("volume") or 0)

                for i in range(min(len(token_list), len(price_list), len(outcome_list))):
                    p = float(price_list[i])
                    tid = token_list[i]

                    if p > BUY_BELOW or p < 0.05:
                        continue
                    if tid in active_token_ids:
                        continue

                    question = market.get("question", "Unknown")
                    outcome_name = str(outcome_list[i])
                    label = f"{question} → {outcome_name}"

                    qualifying.append({
                        "market_id": market.get("id"),
                        "question": label,
                        "token_id": tid,
                        "condition_id": market.get("conditionId"),
                        "price": p,
                        "volume": volume,
                        "tick_size": market.get("orderPriceMinTickSize", 0.01),
                        "neg_risk": bool(market.get("negRisk")),
                    })

            except Exception as e:
                log.debug("Skipped market: %s", e)
                continue

        log.info("Scan — %d candidates (from %d markets)", len(qualifying), len(markets))

    except Exception as e:
        log.error("Scan failed: %s", e)

    qualifying.sort(key=lambda m: m["volume"], reverse=True)
    return qualifying


# ── Order Placement ───────────────────────────────────────────────────────────

def place_buy(client: ClobClient, market: dict) -> dict | None:
    """Place a BUY limit order at the market's current price."""
    token_id = market["token_id"]
    price = market["price"]
    tick = float(market.get("tick_size", 0.01))
    neg_risk = market.get("neg_risk", False)

    size = round(BET_SIZE / price, 2)
    cost = round(price * size, 2)

    log.info(
        "BUY: %s | %.0f shares @ $%.2f = $%.2f",
        market["question"][:55],
        size, price, cost,
    )

    try:
        buy_args = OrderArgs(
            token_id=token_id,
            price=round(price, 4),
            size=size,
            side=BUY,
        )
        opts = CreateOrderOptions(tick_size=str(tick), neg_risk=neg_risk)
        signed = client.create_order(buy_args, options=opts)
        result = client.post_order(signed, OrderType.GTC)

        if not result.get("success", True) and result.get("errorMsg"):
            log.warning("Buy rejected: %s", result["errorMsg"])
            return None

        order_id = result.get("orderID", "?")
        log.info("Buy order live. ID: %s", order_id)

        position = {
            "buy_order_id": order_id,
            "sell_order_id": None,
            "market_id": market["market_id"],
            "question": market["question"],
            "token_id": token_id,
            "condition_id": market["condition_id"],
            "buy_price": price,
            "sell_target": SELL_AT,
            "size": size,
            "cost": cost,
            "tick_size": tick,
            "neg_risk": neg_risk,
            "status": "buying",
            "placed_at": datetime.now(timezone.utc).isoformat(),
        }

        bot_state["total_buys"] += 1
        bot_state["total_spent"] += cost
        add_trade({
            "type": "BUY",
            "question": market["question"][:80],
            "price": price,
            "size": size,
            "cost": cost,
            "time": datetime.now(timezone.utc).isoformat(),
        })

        return position

    except Exception as e:
        log.error("Buy failed: %s", e)
        return None


def place_sell(client: ClobClient, position: dict) -> bool:
    """Place a SELL limit order at SELL_AT target price."""
    token_id = position["token_id"]
    size = position["size"]
    tick = float(position.get("tick_size", 0.01))
    neg_risk = position.get("neg_risk", False)

    log.info(
        "SELL: %s | %.0f shares @ $%.2f",
        position["question"][:55],
        size, SELL_AT,
    )

    try:
        sell_args = OrderArgs(
            token_id=token_id,
            price=round(SELL_AT, 4),
            size=size,
            side=SELL,
        )
        opts = CreateOrderOptions(tick_size=str(tick), neg_risk=neg_risk)
        signed = client.create_order(sell_args, options=opts)
        result = client.post_order(signed, OrderType.GTC)

        if not result.get("success", True) and result.get("errorMsg"):
            log.warning("Sell rejected: %s", result["errorMsg"])
            return False

        sell_id = result.get("orderID", "?")
        position["sell_order_id"] = sell_id
        position["status"] = "selling"
        log.info("Sell order live. ID: %s", sell_id)

        bot_state["total_sells"] += 1
        add_trade({
            "type": "SELL",
            "question": position["question"][:80],
            "price": SELL_AT,
            "size": size,
            "time": datetime.now(timezone.utc).isoformat(),
        })

        return True

    except Exception as e:
        log.error("Sell failed: %s", e)
        return False


def check_order_filled(client: ClobClient, order_id: str) -> bool:
    """Check if an order has been fully filled."""
    try:
        order = client.get_order(order_id)
        if order:
            status = order.get("status", "")
            return status in ("MATCHED", "FILLED")
    except Exception:
        pass
    return False


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
            log.info("Claim OK. TX: %s", tx_hash.hex())
            add_trade({
                "type": "CLAIM",
                "question": position["question"][:80],
                "tx": tx_hash.hex(),
                "time": datetime.now(timezone.utc).isoformat(),
            })
            return True
    except Exception as e:
        if "revert" not in str(e).lower():
            log.error("Claim error: %s", e)
    return False


# ── Dashboard ─────────────────────────────────────────────────────────────────

flask_app = Flask(__name__)
flask_app.logger.setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.WARNING)

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vig Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;background:#0a0a0f;color:#e0e0e0;min-height:100vh;padding:20px}
.c{max-width:860px;margin:0 auto}
h1{font-size:1.5rem;color:#fff;margin-bottom:4px;display:flex;align-items:center;gap:8px}
.sub{color:#666;font-size:0.82rem;margin-bottom:24px}
.wallet{font-family:monospace;font-size:0.75rem;color:#555;margin-bottom:20px;word-break:break-all}
.strat{background:#0f1a2e;border:1px solid #1e2e50;border-radius:8px;padding:10px 14px;margin-bottom:20px;font-size:0.8rem;color:#7aa2d6}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:24px}
.card{background:#141420;border:1px solid #1e1e30;border-radius:12px;padding:16px}
.card .l{font-size:0.7rem;color:#888;text-transform:uppercase;letter-spacing:.5px}
.card .v{font-size:1.5rem;font-weight:700;margin-top:4px;color:#fff}
.card .v.g{color:#22c55e}.card .v.r{color:#ef4444}.card .v.b{color:#3b82f6}.card .v.y{color:#f59e0b}
.sec{background:#141420;border:1px solid #1e1e30;border-radius:12px;padding:16px;margin-bottom:16px}
.sec h2{font-size:0.85rem;color:#aaa;margin-bottom:12px;text-transform:uppercase;letter-spacing:.5px}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:0.68rem;color:#555;text-transform:uppercase;padding:6px 8px;border-bottom:1px solid #1e1e30}
td{padding:8px;font-size:0.82rem;border-bottom:1px solid #0e0e18}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.68rem;font-weight:600}
.badge.buy{background:#1e3a5f;color:#60a5fa}
.badge.sell{background:#3f2a1a;color:#f59e0b}
.badge.claim{background:#1a3f2a;color:#22c55e}
.badge.withdraw{background:#2a1a3f;color:#c084fc}
.st{font-size:0.72rem;padding:2px 6px;border-radius:3px}
.st.buying{background:#1e3a5f;color:#60a5fa}
.st.selling{background:#3f2a1a;color:#f59e0b}
.st.done{background:#1a3f2a;color:#22c55e}
.wf{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
input,button{font-family:inherit;font-size:0.85rem;padding:8px 12px;border-radius:8px;border:1px solid #1e1e30;background:#0a0a0f;color:#e0e0e0}
input{flex:1;min-width:120px}input:focus{outline:none;border-color:#3b82f6}
button{background:#3b82f6;border:none;color:white;font-weight:600;cursor:pointer;white-space:nowrap}
button:hover{background:#2563eb}button:disabled{opacity:.5;cursor:not-allowed}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%}
.dot.on{background:#22c55e;box-shadow:0 0 6px #22c55e}.dot.off{background:#ef4444}
.msg{margin-top:8px;font-size:0.8rem;padding:8px;border-radius:6px}
.msg.ok{background:#1a3f2a;color:#22c55e}.msg.err{background:#3f1a1a;color:#ef4444}
.empty{color:#444;font-style:italic;padding:12px 0;font-size:0.85rem}
.trunc{max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
@media(max-width:600px){.cards{grid-template-columns:1fr 1fr}.trunc{max-width:130px}}
</style>
</head>
<body>
<div class="c">
  <h1><span class="dot" id="dot"></span> Vig</h1>
  <div class="sub" id="sub">Connecting...</div>
  <div class="wallet" id="wallet"></div>
  <div class="strat" id="strat"></div>

  <div class="cards">
    <div class="card"><div class="l">USDC Balance</div><div class="v g" id="bal">--</div></div>
    <div class="card"><div class="l">Active</div><div class="v b" id="active">--</div></div>
    <div class="card"><div class="l">Buys</div><div class="v" id="tbuys">--</div></div>
    <div class="card"><div class="l">Sells</div><div class="v y" id="tsells">--</div></div>
    <div class="card"><div class="l">Spent</div><div class="v" id="tspent">--</div></div>
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
      ?'Running · Last tick '+tick+' · Poll '+d.config.poll_seconds+'s':'Offline';
    document.getElementById('wallet').textContent=d.wallet||'';
    document.getElementById('strat').textContent=
      'Strategy: Buy below $'+d.config.buy_below.toFixed(2)+' → Sell at $'+d.config.sell_at.toFixed(2)+
      ' · $'+d.config.bet_size+'/bet · Min volume $'+d.config.min_volume.toLocaleString();

    document.getElementById('bal').textContent='$'+d.usdc_balance.toFixed(2);
    document.getElementById('active').textContent=d.active_positions+'/'+d.max_bets;
    document.getElementById('tbuys').textContent=d.total_buys;
    document.getElementById('tsells').textContent=d.total_sells;
    document.getElementById('tspent').textContent='$'+d.total_spent.toFixed(2);
    document.getElementById('gas').textContent=d.gas_balance.toFixed(4);

    const pe=document.getElementById('pos');
    if(!d.positions.length){pe.innerHTML='<div class="empty">No active positions</div>'}
    else{
      let h='<table><tr><th>Market</th><th>Buy</th><th>Target</th><th>Status</th></tr>';
      d.positions.forEach(p=>{
        const st=p.status||'buying';
        h+=`<tr><td class="trunc">${p.question}</td><td>$${(p.buy_price||0).toFixed(2)}</td><td>$${(p.sell_target||0).toFixed(2)}</td><td><span class="st ${st}">${st}</span></td></tr>`;
      });
      pe.innerHTML=h+'</table>';
    }

    const te=document.getElementById('trades');
    if(!d.trades.length){te.innerHTML='<div class="empty">No trades yet</div>'}
    else{
      let h='<table><tr><th>Type</th><th>Market</th><th>Details</th><th>Time</th></tr>';
      d.trades.slice().reverse().forEach(t=>{
        const cls=t.type.toLowerCase();
        const det=t.type==='BUY'?'$'+(t.cost||0).toFixed(2)+' @ $'+(t.price||0).toFixed(2)
                  :t.type==='SELL'?(t.size||0).toFixed(0)+' shares @ $'+(t.price||0).toFixed(2)
                  :t.type==='CLAIM'?'Redeemed':'Sent';
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
      document.getElementById('wAmt').value='';setTimeout(refresh,3000);
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
        "total_buys": bot_state["total_buys"],
        "total_sells": bot_state["total_sells"],
        "total_spent": bot_state["total_spent"],
        "trades": trade_history[-30:],
        "config": {
            "bet_size": BET_SIZE,
            "buy_below": BUY_BELOW,
            "sell_at": SELL_AT,
            "min_volume": MIN_VOLUME,
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

    global clob_client
    log.info("Starting Vig swing bot")
    log.info("Buy below    : $%.2f", BUY_BELOW)
    log.info("Sell at      : $%.2f", SELL_AT)
    log.info("Bet size     : $%.0f", BET_SIZE)
    log.info("Max positions: %d", MAX_BETS)
    log.info("Min volume   : $%.0f", MIN_VOLUME)
    log.info("Poll interval: %ds", POLL_SECONDS)

    clob = build_clob_client()
    clob_client = clob
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
            log.info("Positions: %d / %d", len(positions), MAX_BETS)

            # 1. Check buy orders — if filled, place sell
            for pos in positions:
                if pos["status"] == "buying":
                    if check_order_filled(clob, pos["buy_order_id"]):
                        log.info("Buy filled: %s", pos["question"][:50])
                        pos["status"] = "bought"
                        place_sell(clob, pos)
                        save_positions(positions)

                elif pos["status"] == "selling":
                    if check_order_filled(clob, pos["sell_order_id"]):
                        log.info("Sell filled: %s", pos["question"][:50])
                        pos["status"] = "done"
                        add_trade({
                            "type": "SELL",
                            "question": pos["question"][:80],
                            "price": SELL_AT,
                            "size": pos["size"],
                            "time": datetime.now(timezone.utc).isoformat(),
                        })

            # 2. Check resolved markets — claim on-chain
            for pos in positions:
                if pos["status"] in ("buying", "bought", "selling"):
                    if check_market_resolved(pos):
                        try_claim(w3, account, ctf, pos)
                        pos["status"] = "done"

            # 3. Remove done positions
            positions = [p for p in positions if p["status"] != "done"]
            save_positions(positions)
            bot_state["positions"] = positions

            # 4. Fill empty slots with new buys
            slots = MAX_BETS - len(positions)
            log.info("Open slots: %d", slots)

            if slots > 0:
                active_ids = {p["token_id"] for p in positions}
                candidates = scan_markets(active_ids)

                for mkt in candidates[:slots]:
                    pos = place_buy(clob, mkt)
                    if pos:
                        positions.append(pos)
                        save_positions(positions)
                        bot_state["positions"] = positions
                        time.sleep(1)

        except KeyboardInterrupt:
            log.info("Shutting down.")
            save_positions(positions)
            break
        except Exception as e:
            log.error("Main loop error: %s", e)

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run()
