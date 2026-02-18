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
import random
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
import httpx

load_dotenv()

# Route py-clob-client's httpx requests through residential proxy (non-US exit)
_RAW_PROXY = os.getenv("RESIDENTIAL_PROXY_URL") or os.getenv("PROXY_URL") or ""
if _RAW_PROXY and "-country-" not in _RAW_PROXY:
    _PROXY_URL = _RAW_PROXY.replace("residential_proxy1:", "residential_proxy1-country-gb:")
else:
    _PROXY_URL = _RAW_PROXY

if _PROXY_URL:
    print(f"[PROXY] Routing CLOB via: {_PROXY_URL[:40]}...", flush=True)
    _OrigClient = httpx.Client
    class _ProxiedClient(_OrigClient):
        def __init__(self, **kwargs):
            if "proxy" not in kwargs and "proxies" not in kwargs:
                kwargs["proxy"] = _PROXY_URL
            super().__init__(**kwargs)
    httpx.Client = _ProxiedClient
else:
    print("[PROXY] No proxy configured — CLOB may be geoblocked", flush=True)

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

MAX_BETS        = int(os.getenv("MAX_BETS", "999"))
BET_SIZE        = float(os.getenv("BET_SIZE", "10"))
BUY_MIN         = float(os.getenv("BUY_MIN", "0.25"))
BUY_MAX         = float(os.getenv("BUY_MAX", "0.40"))
PROFIT_PCT      = float(os.getenv("PROFIT_PCT", "0.05"))
MAX_SPREAD_PCT  = float(os.getenv("MAX_SPREAD_PCT", "0.02"))
POLL_SECONDS    = int(os.getenv("POLL_SECONDS", "30"))
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

DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)
POSITIONS_FILE = os.path.join(DATA_DIR, "positions.json")
TRADES_FILE = os.path.join(DATA_DIR, "trades.json")
CLOSED_FILE = os.path.join(DATA_DIR, "closed.json")

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
    "closed_positions": [],
    "total_buys": 0,
    "total_sells": 0,
    "total_spent": 0.0,
    "total_returned": 0.0,
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


def load_closed() -> list:
    if os.path.exists(CLOSED_FILE):
        with open(CLOSED_FILE) as f:
            return json.load(f)
    return []


def save_closed(closed: list):
    with open(CLOSED_FILE, "w") as f:
        json.dump(closed[-200:], f, indent=2)


def close_position(pos: dict, exit_type: str, exit_price: float):
    """Move a position to closed list with P&L calculated."""
    cost = pos.get("cost", 0)
    size = pos.get("size", 0)
    revenue = round(size * exit_price, 2) if exit_type == "sold" else round(size * exit_price, 2)
    pnl = round(revenue - cost, 2)

    closed = {
        "question": pos["question"],
        "buy_price": pos.get("buy_price", 0),
        "exit_price": exit_price,
        "size": size,
        "cost": cost,
        "revenue": revenue,
        "pnl": pnl,
        "exit_type": exit_type,
        "opened_at": pos.get("placed_at", ""),
        "closed_at": datetime.now(timezone.utc).isoformat(),
    }

    bot_state["closed_positions"].append(closed)
    bot_state["total_returned"] += revenue
    save_closed(bot_state["closed_positions"])


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

def _parse_market_candidates(markets: list, active_token_ids: set) -> list:
    """Extract ALL outcomes — let the order book scoring decide what's tradeable."""
    found = []
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

                if tid in active_token_ids:
                    continue

                question = market.get("question", "Unknown")
                outcome_name = str(outcome_list[i])
                label = f"{question} → {outcome_name}"

                found.append({
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
    return found


BLACKLIST_FILE = os.path.join(DATA_DIR, "blacklist.json")


def load_blacklist() -> set:
    try:
        with open(BLACKLIST_FILE) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_blacklist(bl: set):
    with open(BLACKLIST_FILE, "w") as f:
        json.dump(list(bl), f)


blacklisted_tokens: set = load_blacklist()


def scan_markets(active_token_ids: set) -> list:
    """Scan all open markets, paginating through everything."""
    seen_tokens = set()
    qualifying = []
    total_scanned = 0
    offset = 0
    page_size = 100

    while True:
        try:
            resp = requests.get(
                f"{GAMMA_API}/markets",
                params={"closed": "false", "limit": page_size, "offset": offset},
                timeout=15,
            )
            resp.raise_for_status()
            markets = resp.json()

            if not markets:
                break

            total_scanned += len(markets)

            for c in _parse_market_candidates(markets, active_token_ids):
                tid = c["token_id"]
                if tid not in seen_tokens and tid not in blacklisted_tokens:
                    seen_tokens.add(tid)
                    qualifying.append(c)

            if len(markets) < page_size:
                break
            offset += page_size

        except Exception as e:
            log.error("Scan page failed (offset %d): %s", offset, e)
            break

    log.info("Scan — %d candidates (from %d total markets, %d blacklisted)",
             len(qualifying), total_scanned, len(blacklisted_tokens))

    qualifying.sort(key=lambda m: m["volume"], reverse=True)
    return qualifying


# ── Order Placement ───────────────────────────────────────────────────────────

STALE_ORDER_MINUTES = int(os.getenv("STALE_MINUTES", "10"))


def score_market(token_id: str, client: ClobClient, label: str = "") -> dict | None:
    """
    Find tight-spread markets priced $0.25-$0.40.
    Spread must be <= 1% of price. Score by depth and tightness.
    """
    try:
        book = client.get_order_book(token_id)
        bids = getattr(book, "bids", [])
        asks = getattr(book, "asks", [])
        ltp = float(getattr(book, "last_trade_price", 0) or 0)

        best_bid = float(bids[-1].price) if bids else 0
        best_ask = float(asks[-1].price) if asks else 0

        if not bids or not asks:
            return None
        if best_ask < BUY_MIN or best_ask > BUY_MAX:
            return None
        if best_bid < BUY_MIN * 0.8:
            return None

        spread = best_ask - best_bid
        spread_pct = spread / best_ask if best_ask > 0 else 1
        if spread_pct > MAX_SPREAD_PCT:
            return None

        all_bid_usd = sum(float(b.price) * float(b.size) for b in bids)

        score = all_bid_usd / max(spread_pct, 0.0001)

        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "all_bid_usd": all_bid_usd,
            "n_bids": len(bids),
            "n_asks": len(asks),
            "spread": spread,
            "spread_pct": spread_pct,
            "last_trade": ltp,
            "score": score,
        }
    except Exception:
        return None


def place_buy(client: ClobClient, market: dict) -> dict | None:
    """Place a GTC limit buy at OUR price — we're the bid, waiting for sellers."""
    token_id = market["token_id"]
    tick = float(market.get("tick_size", 0.01))
    neg_risk = market.get("neg_risk", False)

    info = market.get("_score")
    if not info:
        info = score_market(token_id, client, market["question"])
        if not info:
            return None

    best_bid = info["best_bid"]
    best_ask = info["best_ask"]
    spread = info["spread"]

    price = best_ask
    if price < BUY_MIN or price > BUY_MAX:
        return None

    size = round(BET_SIZE / price, 2)
    cost = round(price * size, 2)

    log.info(
        "BUY: %s | %.0f@$%.3f=$%.2f bid=$%.3f ask=$%.3f spd=$%.3f depth=$%.0f",
        market["question"][:30],
        size, price, cost, best_bid, best_ask, spread, info["all_bid_usd"],
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
        result = client.post_order(signed, OrderType.FOK)

        order_id = result.get("orderID", "")
        filled = result.get("status") in ("MATCHED", "FILLED")

        if not filled or not order_id:
            signed2 = client.create_order(buy_args, options=opts)
            result = client.post_order(signed2, OrderType.GTC)
            order_id = result.get("orderID", "")
            filled = result.get("status") in ("MATCHED", "FILLED")

        if not order_id:
            if result.get("errorMsg"):
                log.warning("Buy rejected: %s", result["errorMsg"])
            return None

        status = "held" if filled else "pending"
        log.info("Buy %s. ID: %s", "filled" if filled else "pending", order_id)

        position = {
            "buy_order_id": order_id,
            "sell_order_id": None,
            "market_id": market["market_id"],
            "question": market["question"],
            "token_id": token_id,
            "condition_id": market["condition_id"],
            "buy_price": price,
            "sell_target": round(min(price * (1 + PROFIT_PCT), 0.99), 4),
            "size": size,
            "cost": cost,
            "tick_size": tick,
            "neg_risk": neg_risk,
            "status": status,
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

        if filled:
            place_sell(client, position)

        return position

    except Exception as e:
        log.error("Buy failed: %s", e)
        return None


def place_sell(client: ClobClient, position: dict) -> bool:
    """Place a SELL limit order — uses dynamic pricing based on order book."""
    token_id = position["token_id"]
    size = position["size"]
    tick = float(position.get("tick_size", 0.01))
    neg_risk = position.get("neg_risk", False)
    buy_price = position.get("buy_price", 0)

    sell_price = position.get("sell_target") or round(buy_price * (1 + PROFIT_PCT), 4)

    try:
        book = client.get_order_book(token_id)
        bids = getattr(book, "bids", [])
        best_bid = float(bids[-1].price) if bids else 0

        if best_bid > sell_price:
            sell_price = min(best_bid + tick, 0.99)
    except Exception:
        pass

    sell_price = round(sell_price, 4)
    position["sell_target"] = sell_price

    log.info(
        "SELL: %s | %.0f shares @ $%.4f (bought $%.3f, +%.0f%%)",
        position["question"][:40],
        size, sell_price, buy_price,
        ((sell_price - buy_price) / buy_price * 100) if buy_price > 0 else 0,
    )

    try:
        sell_args = OrderArgs(
            token_id=token_id,
            price=sell_price,
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
        position["status"] = "held"
        log.info("Sell order live. ID: %s", sell_id)

        bot_state["total_sells"] += 1
        add_trade({
            "type": "SELL",
            "question": position["question"][:80],
            "price": sell_price,
            "size": size,
            "time": datetime.now(timezone.utc).isoformat(),
        })

        return True

    except Exception as e:
        log.error("Sell failed: %s", e)
        return False


def get_price_info(token_id: str) -> dict:
    """Fetch last trade price and best bid/ask for a token."""
    info = {"last_trade": None, "best_bid": None, "best_ask": None}
    try:
        if clob_client:
            book = clob_client.get_order_book(token_id)
            if book:
                ltp = getattr(book, "last_trade_price", None)
                if ltp and float(ltp) > 0:
                    info["last_trade"] = round(float(ltp), 4)

                bids = getattr(book, "bids", [])
                asks = getattr(book, "asks", [])
                if bids:
                    info["best_bid"] = round(float(bids[-1].price), 4)
                if asks:
                    info["best_ask"] = round(float(asks[-1].price), 4)
    except Exception:
        pass
    return info


def get_current_price(token_id: str) -> float | None:
    """Shortcut: return last trade price."""
    return get_price_info(token_id).get("last_trade")


def cancel_order(client: ClobClient, order_id: str) -> bool:
    """Cancel an open order."""
    try:
        result = client.cancel(order_id)
        return bool(result)
    except Exception as e:
        log.error("Cancel failed for %s: %s", order_id, e)
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
.c{max-width:960px;margin:0 auto}
h1{font-size:1.5rem;color:#fff;margin-bottom:4px;display:flex;align-items:center;gap:8px}
.sub{color:#666;font-size:0.82rem;margin-bottom:24px}
.wallet{font-family:monospace;font-size:0.75rem;color:#555;margin-bottom:20px;word-break:break-all}
.strat{background:#0f1a2e;border:1px solid #1e2e50;border-radius:8px;padding:10px 14px;margin-bottom:20px;font-size:0.8rem;color:#7aa2d6}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin-bottom:24px}
.card{background:#141420;border:1px solid #1e1e30;border-radius:12px;padding:14px}
.card .l{font-size:0.65rem;color:#888;text-transform:uppercase;letter-spacing:.5px}
.card .v{font-size:1.35rem;font-weight:700;margin-top:4px;color:#fff}
.card .v.g{color:#22c55e}.card .v.r{color:#ef4444}.card .v.b{color:#3b82f6}.card .v.y{color:#f59e0b}
.sec{background:#141420;border:1px solid #1e1e30;border-radius:12px;padding:16px;margin-bottom:16px}
.sec h2{font-size:0.85rem;color:#aaa;margin-bottom:12px;text-transform:uppercase;letter-spacing:.5px}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:0.65rem;color:#555;text-transform:uppercase;padding:6px 8px;border-bottom:1px solid #1e1e30}
td{padding:8px;font-size:0.8rem;border-bottom:1px solid #0e0e18}
.st{font-size:0.7rem;padding:2px 6px;border-radius:3px;font-weight:600}
.st.pending{background:#1e3a5f;color:#60a5fa}
.st.held{background:#1a3f2a;color:#22c55e}
.st.sold{background:#1a3f2a;color:#22c55e}
.st.claimed{background:#1a3f2a;color:#22c55e}
.st.expired{background:#3f1a1a;color:#ef4444}
.pnl-pos{color:#22c55e;font-weight:600}
.pnl-neg{color:#ef4444;font-weight:600}
.pnl-zero{color:#888;font-weight:600}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.68rem;font-weight:600}
.badge.buy{background:#1e3a5f;color:#60a5fa}
.badge.sell{background:#3f2a1a;color:#f59e0b}
.badge.claim{background:#1a3f2a;color:#22c55e}
.badge.withdraw{background:#2a1a3f;color:#c084fc}
.badge.close{background:#3f1a1a;color:#ef4444}
.st.manual{background:#3f1a1a;color:#ef4444}
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
.trunc{max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tabs{display:flex;gap:4px;margin-bottom:12px}
.tab{padding:6px 14px;border-radius:6px;font-size:0.78rem;cursor:pointer;background:#0a0a0f;border:1px solid #1e1e30;color:#888}
.tab.active{background:#1e3a5f;color:#60a5fa;border-color:#2e4a6f}
.tab .cnt{font-size:0.68rem;margin-left:4px;opacity:.7}
.cbtn{background:#ef4444;border:none;color:white;padding:3px 8px;border-radius:4px;font-size:0.7rem;cursor:pointer;font-weight:600}.cbtn:hover{background:#dc2626}
@media(max-width:600px){.cards{grid-template-columns:1fr 1fr}.trunc{max-width:110px}}
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
    <div class="card"><div class="l">Open Bets</div><div class="v b" id="active">--</div></div>
    <div class="card"><div class="l">Invested</div><div class="v" id="tspent">--</div></div>
    <div class="card"><div class="l">Returned</div><div class="v g" id="treturned">--</div></div>
    <div class="card"><div class="l">Net P&L</div><div class="v" id="pnl">--</div></div>
    <div class="card"><div class="l">Win Rate</div><div class="v y" id="winrate">--</div></div>
    <div class="card"><div class="l">Closed</div><div class="v" id="tclosed">--</div></div>
    <div class="card"><div class="l">Gas (POL)</div><div class="v" id="gas">--</div></div>
  </div>

  <div class="sec">
    <div class="tabs">
      <div class="tab active" onclick="showTab('open')" id="tabOpen">Open Bets<span class="cnt" id="openCnt"></span></div>
      <div class="tab" onclick="showTab('closed')" id="tabClosed">Closed Bets<span class="cnt" id="closedCnt"></span></div>
      <div class="tab" onclick="showTab('log')" id="tabLog">Trade Log</div>
    </div>
    <div id="panelOpen"></div>
    <div id="panelClosed" style="display:none"></div>
    <div id="panelLog" style="display:none"></div>
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
let currentTab='open';
function showTab(t){
  currentTab=t;
  ['open','closed','log'].forEach(x=>{
    document.getElementById('panel'+x.charAt(0).toUpperCase()+x.slice(1)).style.display=x===t?'':'none';
    document.getElementById('tab'+x.charAt(0).toUpperCase()+x.slice(1)).className='tab'+(x===t?' active':'');
  });
}

function pnlClass(v){return v>0?'pnl-pos':v<0?'pnl-neg':'pnl-zero'}
function pnlStr(v){return (v>=0?'+':'')+v.toFixed(2)}
function timeFmt(s){if(!s)return'--';const d=new Date(s);return d.toLocaleDateString('en-US',{month:'short',day:'numeric'})+' '+d.toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit'})}

async function refresh(){
  try{
    const r=await fetch('/api/status',{signal:AbortSignal.timeout(8000)});
    if(!r.ok){document.getElementById('sub').textContent='Server error ('+r.status+')';return}
    const d=await r.json();

    document.getElementById('dot').className='dot '+(d.running?'on':'off');
    const tick=d.last_tick?new Date(d.last_tick).toLocaleTimeString():'--';
    document.getElementById('sub').textContent=d.running
      ?'Running \u00b7 Last tick '+tick+' \u00b7 Poll '+d.config.poll_seconds+'s':'Offline';
    document.getElementById('wallet').textContent=d.wallet||'';
    document.getElementById('strat').textContent=
      'Buy '+d.config.buy_range+' \u2192 +'+d.config.profit_target+' profit'+
      ' \u00b7 $'+d.config.bet_size+'/bet \u00b7 Spread \u2264'+d.config.max_spread;

    document.getElementById('bal').textContent='$'+d.usdc_balance.toFixed(2);
    document.getElementById('active').textContent=d.active_positions+'/'+d.max_bets;
    document.getElementById('tspent').textContent='$'+d.total_spent.toFixed(2);
    document.getElementById('treturned').textContent='$'+d.total_returned.toFixed(2);

    const netPnl=d.total_returned-d.total_spent;
    const pnlEl=document.getElementById('pnl');
    pnlEl.textContent='$'+pnlStr(netPnl);
    pnlEl.className='v '+(netPnl>=0?'g':'r');

    const closed=d.closed_positions||[];
    const wins=closed.filter(c=>c.pnl>0).length;
    const wr=closed.length?((wins/closed.length)*100).toFixed(0)+'%':'--';
    document.getElementById('winrate').textContent=wr;
    document.getElementById('tclosed').textContent=closed.length;
    document.getElementById('gas').textContent=d.gas_balance.toFixed(4);

    document.getElementById('openCnt').textContent='('+d.positions.length+')';
    document.getElementById('closedCnt').textContent='('+closed.length+')';

    // Open positions
    const pe=document.getElementById('panelOpen');
    if(!d.positions.length){pe.innerHTML='<div class="empty">No open bets</div>'}
    else{
      let h='<table><tr><th>Market</th><th>Shares</th><th>Entry</th><th>Bid</th><th>Ask</th><th>P&L (at Bid)</th><th>Target</th><th>Status</th><th></th></tr>';
      d.positions.forEach((p,i)=>{
        const st=p.status||'pending';
        const bp=p.buy_price||0;const sz=p.size||0;
        const bid=p.best_bid||0;const ask=p.best_ask||0;
        const bidStr=bid?'$'+bid.toFixed(3):'--';
        const askStr=ask?'$'+ask.toFixed(3):'--';
        const bc=bid>bp?'pnl-pos':bid<bp?'pnl-neg':'';
        const ac=ask>bp?'pnl-pos':ask<bp?'pnl-neg':'';
        const upnl=bid?(bid*sz)-(p.cost||0):0;
        const upnlStr=bid?'$'+pnlStr(upnl):'--';
        const upnlCls=bid?pnlClass(upnl):'';
        h+=`<tr><td class="trunc">${p.question}</td><td>${sz.toFixed(0)}</td><td>$${bp.toFixed(3)}</td><td class="${bc}">${bidStr}</td><td class="${ac}">${askStr}</td><td class="${upnlCls}">${upnlStr}</td><td>$${(p.sell_target||0).toFixed(2)}</td><td><span class="st ${st}">${st}</span></td><td><button class="cbtn" onclick="closePos('${p.token_id}')">\u2715</button></td></tr>`;
      });
      pe.innerHTML=h+'</table>';
    }

    // Closed positions
    const ce=document.getElementById('panelClosed');
    if(!closed.length){ce.innerHTML='<div class="empty">No closed bets yet</div>'}
    else{
      let h='<table><tr><th>Market</th><th>Buy</th><th>Exit</th><th>Cost</th><th>Return</th><th>P&L</th><th>Type</th><th>Closed</th></tr>';
      closed.slice().reverse().forEach(c=>{
        const pc=pnlClass(c.pnl);
        h+=`<tr><td class="trunc">${c.question}</td><td>$${(c.buy_price||0).toFixed(3)}</td><td>$${(c.exit_price||0).toFixed(2)}</td><td>$${(c.cost||0).toFixed(2)}</td><td>$${(c.revenue||0).toFixed(2)}</td><td class="${pc}">$${pnlStr(c.pnl)}</td><td><span class="st ${c.exit_type}">${c.exit_type}</span></td><td>${timeFmt(c.closed_at)}</td></tr>`;
      });
      ce.innerHTML=h+'</table>';
    }

    // Trade log
    const te=document.getElementById('panelLog');
    if(!d.trades.length){te.innerHTML='<div class="empty">No trades yet</div>'}
    else{
      let h='<table><tr><th>Type</th><th>Market</th><th>Details</th><th>Time</th></tr>';
      d.trades.slice().reverse().forEach(t=>{
        const cls=t.type.toLowerCase();
        const det=t.type==='BUY'?'$'+(t.cost||0).toFixed(2)+' @ $'+(t.price||0).toFixed(2)
                  :t.type==='SELL'?(t.size||0).toFixed(0)+' shares @ $'+(t.price||0).toFixed(2)
                  :t.type==='CLOSE'?'Manual close @ $'+(t.price||0).toFixed(3)
                  :t.type==='CLAIM'?'Redeemed':'Sent';
        h+=`<tr><td><span class="badge ${cls}">${t.type}</span></td><td class="trunc">${t.question||''}</td><td>${det}</td><td>${timeFmt(t.time)}</td></tr>`;
      });
      te.innerHTML=h+'</table>';
    }
  }catch(e){
    document.getElementById('sub').textContent='Reconnecting... (bot busy scanning)';
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

async function closePos(tokenId){
  if(!confirm('Close this position? This will cancel the order.'))return;
  try{
    const r=await fetch('/api/close',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token_id:tokenId})});
    const d=await r.json();
    if(d.success){alert('Position closed: '+d.message);refresh()}
    else{alert('Error: '+d.error)}
  }catch(e){alert('Request failed')}
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
    positions_with_prices = []
    for p in bot_state["positions"]:
        pp = dict(p)
        pi = get_price_info(p["token_id"])
        pp["current_price"] = pi["last_trade"]
        pp["best_bid"] = pi["best_bid"]
        pp["best_ask"] = pi["best_ask"]
        positions_with_prices.append(pp)

    return jsonify({
        "running": bot_state["running"],
        "started_at": bot_state["started_at"],
        "last_tick": bot_state["last_tick"],
        "wallet": bot_state["wallet"],
        "usdc_balance": get_usdc_balance(),
        "gas_balance": get_matic_balance(),
        "active_positions": len(bot_state["positions"]),
        "max_bets": MAX_BETS,
        "positions": positions_with_prices,
        "total_buys": bot_state["total_buys"],
        "total_sells": bot_state["total_sells"],
        "total_spent": bot_state["total_spent"],
        "total_returned": bot_state["total_returned"],
        "closed_positions": bot_state["closed_positions"][-50:],
        "trades": trade_history[-30:],
        "config": {
            "bet_size": BET_SIZE,
            "buy_range": f"${BUY_MIN}-${BUY_MAX}",
            "profit_target": f"{PROFIT_PCT*100:.0f}%",
            "max_spread": f"{MAX_SPREAD_PCT*100:.1f}%",
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


@flask_app.route("/api/close", methods=["POST"])
def api_close():
    if not clob_client:
        return jsonify({"success": False, "error": "Bot not initialized"})

    data = flask_request.get_json()
    token_id = data.get("token_id", "").strip()

    if not token_id:
        return jsonify({"success": False, "error": "No token_id provided"})

    pos = None
    for p in bot_state["positions"]:
        if p["token_id"] == token_id:
            pos = p
            break

    if not pos:
        return jsonify({"success": False, "error": "Position not found"})

    try:
        actions = []

        if pos["status"] == "pending":
            cancel_order(clob_client, pos["buy_order_id"])
            actions.append("cancelled buy order")
            current = get_current_price(token_id) or 0
            close_position(pos, "manual", 0)

        elif pos["status"] == "held":
            if pos.get("sell_order_id"):
                cancel_order(clob_client, pos["sell_order_id"])
                actions.append("cancelled sell order")

            size = pos["size"]
            tick = float(pos.get("tick_size", 0.01))
            neg_risk = pos.get("neg_risk", False)
            buy_price = pos.get("buy_price", 0)

            book = clob_client.get_order_book(token_id)
            bids = getattr(book, "bids", [])
            ltp = float(getattr(book, "last_trade_price", 0) or 0)

            good_bids = [b for b in bids if float(b.price) >= buy_price]
            if good_bids:
                sell_price = float(good_bids[-1].price)
            elif ltp >= buy_price:
                sell_price = round(ltp * 0.95, 4)
            else:
                return jsonify({"success": False,
                    "error": f"No buyers above your buy price (${buy_price:.3f}). "
                             f"Best bid: ${float(bids[-1].price):.3f}" if bids else "No bids at all"})

            sell_args = OrderArgs(
                token_id=token_id,
                price=round(sell_price, 4),
                size=size,
                side=SELL,
            )
            opts = CreateOrderOptions(tick_size=str(tick), neg_risk=neg_risk)
            signed = clob_client.create_order(sell_args, options=opts)
            result = clob_client.post_order(signed, OrderType.GTC)

            if result.get("orderID"):
                actions.append(f"sell order placed @ ${sell_price:.3f} (GTC)")
                close_position(pos, "manual", sell_price)
            else:
                return jsonify({"success": False,
                    "error": f"Sell order failed: {result.get('errorMsg', 'unknown')}"})

        else:
            close_position(pos, "manual", 0)

        pos["status"] = "done"

        add_trade({
            "type": "CLOSE",
            "question": pos["question"][:80],
            "price": current if pos["status"] == "buying" else sell_price if 'sell_price' in dir() else 0,
            "time": datetime.now(timezone.utc).isoformat(),
        })

        bot_state["positions"] = [p for p in bot_state["positions"] if p["status"] != "done"]
        save_positions(bot_state["positions"])

        msg = "; ".join(actions) if actions else "Position closed"
        log.info("Manual close: %s — %s", pos["question"][:50], msg)
        return jsonify({"success": True, "message": msg})

    except Exception as e:
        log.error("Manual close failed: %s", e)
        return jsonify({"success": False, "error": str(e)})


@flask_app.route("/api/scan")
def api_scan():
    """Diagnostic: run a quick scan and show what the bot sees."""
    if not clob_client:
        return jsonify({"error": "bot not ready"})
    try:
        results = []
        active_ids = {p["token_id"] for p in bot_state.get("positions", [])}
        candidates = scan_markets(active_ids)
        sample = random.sample(candidates[:3000], min(30, len(candidates)))
        for mkt in sample:
            info = score_market(mkt["token_id"], clob_client, mkt["question"])
            results.append({
                "question": mkt["question"][:60],
                "gamma_price": mkt["price"],
                "volume": mkt["volume"],
                "score": info["score"] if info else None,
                "best_bid": info["best_bid"] if info else None,
                "best_ask": info["best_ask"] if info else None,
                "n_bids": info["n_bids"] if info else None,
                "bid_depth": info["all_bid_usd"] if info else None,
                "passed": info is not None,
            })
        passed = [r for r in results if r["passed"]]
        failed = [r for r in results if not r["passed"]]
        return jsonify({"total_candidates": len(candidates), "sampled": len(results),
                        "passed": len(passed), "failed": len(failed),
                        "results": sorted(results, key=lambda r: r["score"] or 0, reverse=True)})
    except Exception as e:
        return jsonify({"error": str(e)})


def start_dashboard():
    log.info("Dashboard on port %d", PORT)
    flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False, threaded=True)


# ── Main Loop ─────────────────────────────────────────────────────────────────

def run():
    if not PRIVATE_KEY:
        raise ValueError("PRIVATE_KEY not set in .env")

    global clob_client
    log.info("Starting Vig swing bot")
    log.info("Buy range    : $%.2f - $%.2f", BUY_MIN, BUY_MAX)
    log.info("Profit target: %.0f%%", PROFIT_PCT * 100)
    log.info("Max spread   : %.1f%%", MAX_SPREAD_PCT * 100)
    log.info("Bet size     : $%.0f", BET_SIZE)
    log.info("Max positions: %d", MAX_BETS)
    log.info("Poll interval: %ds", POLL_SECONDS)

    clob = build_clob_client()
    clob_client = clob
    w3, account, ctf = build_web3()

    global trade_history
    positions = load_positions()
    for p in positions:
        if p.get("status") == "buying":
            p["status"] = "pending"
        elif p.get("status") in ("selling", "bought"):
            p["status"] = "held"
    trade_history = load_trades()
    bot_state["closed_positions"] = load_closed()
    bot_state["total_returned"] = sum(c.get("revenue", 0) for c in bot_state["closed_positions"])

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

            # 1. Auto-cancel stale pending orders
            now = datetime.now(timezone.utc)
            for pos in positions:
                if pos["status"] == "pending":
                    try:
                        placed = datetime.fromisoformat(pos["placed_at"]).replace(tzinfo=timezone.utc)
                    except (ValueError, KeyError):
                        continue
                    age_min = (now - placed).total_seconds() / 60
                    if age_min > STALE_ORDER_MINUTES:
                        log.info("AUTO-CANCEL: %s (pending %.0f min)",
                                 pos["question"][:40], age_min)
                        cancel_order(clob, pos["buy_order_id"])
                        close_position(pos, "expired", 0)
                        pos["status"] = "done"

            # 2. Check pending buys — if filled, place sell
            for pos in positions:
                if pos["status"] == "pending":
                    if check_order_filled(clob, pos["buy_order_id"]):
                        log.info("Buy filled: %s", pos["question"][:50])
                        pos["status"] = "held"
                        place_sell(clob, pos)
                        save_positions(positions)

                elif pos["status"] == "held":
                    if pos.get("sell_order_id") and check_order_filled(clob, pos["sell_order_id"]):
                        actual_sell = pos.get("sell_target", pos.get("buy_price", 0) * (1 + PROFIT_PCT))
                        log.info("Sell filled: %s @ $%.3f", pos["question"][:50], actual_sell)
                        pos["status"] = "done"
                        close_position(pos, "sold", actual_sell)
                        add_trade({
                            "type": "SELL",
                            "question": pos["question"][:80],
                            "price": actual_sell,
                            "size": pos["size"],
                            "time": datetime.now(timezone.utc).isoformat(),
                        })

            # 3. Re-price stale sell orders if market moved up
            for pos in positions:
                if pos["status"] == "held" and pos.get("sell_order_id"):
                    try:
                        info = score_market(pos["token_id"], clob, pos.get("question", ""))
                        cur_target = pos.get("sell_target", pos.get("buy_price", 0) * (1 + PROFIT_PCT))
                        if info and info["best_bid"] > cur_target * 1.05:
                            new_target = min(info["best_bid"] + float(pos.get("tick_size", 0.01)), 0.99)
                            log.info("REPRICE: %s sell $%.3f → $%.3f (bid=$%.3f)",
                                     pos["question"][:35], cur_target,
                                     new_target, info["best_bid"])
                            cancel_order(clob, pos["sell_order_id"])
                            pos["sell_target"] = new_target
                            pos["sell_order_id"] = None
                            place_sell(clob, pos)
                            save_positions(positions)
                    except Exception:
                        pass

            # 4. Check resolved markets — claim on-chain
            for pos in positions:
                if pos["status"] in ("pending", "held"):
                    if check_market_resolved(pos):
                        claimed = try_claim(w3, account, ctf, pos)
                        pos["status"] = "done"
                        exit_price = 1.0 if claimed else 0.0
                        close_position(pos, "claimed" if claimed else "expired", exit_price)

            # 5. Remove done positions
            positions = [p for p in positions if p["status"] != "done"]
            save_positions(positions)
            bot_state["positions"] = positions

            # 6. Fill empty slots — score a batch, buy the best
            slots = MAX_BETS - len(positions)
            log.info("Open slots: %d", slots)

            if slots > 0:
                active_ids = {p["token_id"] for p in positions}
                candidates = scan_markets(active_ids)

                pool_size = min(len(candidates), 3000)
                check_pool = random.sample(candidates[:pool_size], min(80, pool_size))

                scored = []
                for mkt in check_pool:
                    info = score_market(mkt["token_id"], clob, mkt["question"])
                    if info:
                        mkt["_score"] = info
                        scored.append(mkt)
                    if len(scored) >= slots * 3:
                        break

                scored.sort(key=lambda m: m["_score"]["score"], reverse=True)
                log.info("Scored %d/%d — top: %s",
                         len(scored), len(check_pool),
                         " | ".join(
                             f"bid${m['_score']['all_bid_usd']:.0f}({m['_score']['n_bids']}lvl)@${m['_score']['best_bid']:.2f}"
                             for m in scored[:5]
                         ))

                filled = 0
                for mkt in scored:
                    if filled >= slots:
                        break
                    pos = place_buy(clob, mkt)
                    if pos:
                        positions.append(pos)
                        save_positions(positions)
                        bot_state["positions"] = positions
                        filled += 1
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
