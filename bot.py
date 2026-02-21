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
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from flask import Flask, request as flask_request, jsonify, Response

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, CreateOrderOptions, BalanceAllowanceParams, AssetType
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
BUY_MIN         = float(os.getenv("BUY_MIN", "0.15"))
BUY_MAX         = float(os.getenv("BUY_MAX", "0.30"))
SELL_TARGET     = float(os.getenv("SELL_TARGET", "0.40"))
PROFIT_PCT      = float(os.getenv("PROFIT_PCT", "0.05"))
MAX_SPREAD_PCT  = float(os.getenv("MAX_SPREAD_PCT", "0.02"))
MAX_EXPIRY_DAYS = int(os.getenv("MAX_EXPIRY_DAYS", "7"))
POLL_SECONDS    = int(os.getenv("POLL_SECONDS", "30"))
PORT            = int(os.getenv("PORT", "8080"))

CLOB_HOST       = "https://clob.polymarket.com"

# Builder Program (gasless redemptions via relayer)
BUILDER_KEY        = os.getenv("POLY_BUILDER_API_KEY", "")
BUILDER_SECRET     = os.getenv("POLY_BUILDER_SECRET", "")
BUILDER_PASSPHRASE = os.getenv("POLY_BUILDER_PASSPHRASE", "")
GAMMA_API       = "https://gamma-api.polymarket.com"
DATA_API        = "https://data-api.polymarket.com"
POLY_API        = "https://gateway.polymarket.us"
SCAN_TAG_SLUGS  = ["crypto", "sports", "economics", "business"]

CTF_ADDRESS     = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
USDC_ADDRESS    = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"

relay_client = None  # Builder relayer for gasless redemptions
neg_risk_adapter = None  # NegRiskAdapter contract

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
    },
    {
        "inputs": [
            {"internalType": "address", "name": "account", "type": "address"},
            {"internalType": "uint256", "name": "id", "type": "uint256"},
        ],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "operator", "type": "address"},
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "id", "type": "uint256"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "TransferSingle",
        "type": "event",
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "operator", "type": "address"},
        ],
        "name": "isApprovedForAll",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "operator", "type": "address"},
            {"name": "approved", "type": "bool"},
        ],
        "name": "setApprovalForAll",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


NEG_RISK_ABI = [
    {"inputs": [{"name": "_conditionId", "type": "bytes32"}, {"name": "_amounts", "type": "uint256[]"}],
     "name": "redeemPositions", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
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
bot_paused = False

bot_state = {
    "running": False,
    "paused": False,
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
    no_cost = exit_type in ("expired", "cancelled")
    actual_cost = 0 if no_cost else cost
    revenue = round(size * exit_price, 2)
    pnl = round(revenue - actual_cost, 2)

    closed = {
        "question": pos["question"],
        "buy_price": pos.get("buy_price", 0),
        "exit_price": exit_price,
        "size": size,
        "cost": actual_cost,
        "revenue": revenue,
        "pnl": pnl,
        "exit_type": exit_type,
        "opened_at": pos.get("placed_at", ""),
        "closed_at": datetime.now(timezone.utc).isoformat(),
        "token_id": pos.get("token_id", ""),
        "condition_id": pos.get("condition_id", ""),
        "market_id": pos.get("market_id", ""),
    }

    bot_state["closed_positions"].append(closed)
    if not no_cost:
        bot_state["total_returned"] += revenue
    save_closed(bot_state["closed_positions"])

    tid = pos.get("token_id", "")
    if tid:
        blacklisted_tokens.add(tid)
        save_blacklist(blacklisted_tokens)


# ── Clients ───────────────────────────────────────────────────────────────────

def build_clob_client() -> ClobClient:
    if not PRIVATE_KEY:
        raise ValueError("PRIVATE_KEY not set in .env")
    client = ClobClient(host=CLOB_HOST, key=PRIVATE_KEY, chain_id=POLYGON)
    client.set_api_creds(client.create_or_derive_api_creds())
    log.info("CLOB ready. Address: %s", client.get_address())

    try:
        collateral = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        log.info("USDC allowance: %s", collateral)
    except Exception as e:
        log.warning("Could not check USDC allowance: %s", e)

    try:
        client.set_allowances()
        log.info("Exchange approvals set (USDC + conditional tokens)")
    except Exception as e:
        log.warning("Could not set allowances: %s", e)

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
    global neg_risk_adapter
    neg_risk_adapter = w3.eth.contract(
        address=Web3.to_checksum_address(NEG_RISK_ADAPTER), abi=NEG_RISK_ABI)
    # Ensure CTF approval for NegRiskAdapter (needed for neg_risk redemptions)
    try:
        is_approved = ctf.functions.isApprovedForAll(account.address, NEG_RISK_ADAPTER).call()
        if not is_approved:
            log.info("Setting CTF approval for NegRiskAdapter...")
            nonce = w3.eth.get_transaction_count(account.address)
            atx = ctf.functions.setApprovalForAll(NEG_RISK_ADAPTER, True).build_transaction({
                "from": account.address, "nonce": nonce, "gas": 100_000,
                "maxFeePerGas": int(w3.eth.gas_price * 1.5),
                "maxPriorityFeePerGas": w3.to_wei(30, "gwei"),
            })
            signed = account.sign_transaction(atx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            log.info("CTF approved for NegRiskAdapter")
    except Exception as e:
        log.warning("CTF approval check failed: %s", e)
    log.info("Web3 ready. Wallet: %s", account.address)
    return w3, account, ctf, neg_risk_adapter


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




# ── Data API (authoritative source of truth) ─────────────────────────────────

def data_api_positions():
    """Fetch open positions from Polymarket Data API."""
    try:
        r = requests.get(f"{DATA_API}/positions",
                         params={"user": account_instance.address.lower()}, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        log.debug("Data API positions: %s", e)
    return []


def data_api_value():
    """Fetch total portfolio value from Data API."""
    try:
        r = requests.get(f"{DATA_API}/value",
                         params={"user": account_instance.address.lower()}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data:
                return data[0].get("value", 0)
    except Exception:
        pass
    return 0


# ── Market Scanner ────────────────────────────────────────────────────────────

PRIORITY_KEYWORDS = {
    "bitcoin", "btc", "ethereum", "eth", "solana", "sol", "crypto", "bnb", "xrp",
    "dogecoin", "doge", "cardano", "polygon", "matic", "ripple", "litecoin",
    "fed", "interest rate", "inflation", "gdp", "cpi", "treasury", "fomc",
    "earnings", "revenue", "profit", "quarterly", "eps", "beat",
    "stock", "s&p", "nasdaq", "dow", "spy", "qqq", "ipo", "market cap",
    "oil", "gold", "silver", "commodity",
    "recession", "unemployment", "economy", "economic",
    "nba", "nfl", "nhl", "mlb", "premier league", "champions league", "la liga",
    "serie a", "bundesliga", "ligue 1", "stanley cup", "super bowl",
    "olympic", "olympics", "world cup", "uefa", "fifa",
    "tennis", "golf", "formula 1", "f1", "ufc", "boxing",
    "spread:", "o/u", "over/under", "moneyline",
    "lakers", "celtics", "warriors", "knicks", "rockets", "grizzlies",
    "manchester", "arsenal", "liverpool", "chelsea", "barcelona", "real madrid",
}


def _is_priority_market(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in PRIORITY_KEYWORDS)


def _parse_market_candidates(markets: list, active_token_ids: set) -> list:
    """Extract ALL outcomes — let the order book scoring decide what's tradeable."""
    found = []
    now = datetime.now(timezone.utc)
    max_end = now + timedelta(days=MAX_EXPIRY_DAYS)
    for market in markets:
        try:
            end_str = market.get("endDate") or market.get("endDateIso") or ""
            if end_str:
                try:
                    end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    if end_dt > max_end or end_dt < now:
                        continue
                except (ValueError, TypeError):
                    pass

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

                if p < BUY_MIN * 0.5 or p > BUY_MAX * 1.5:
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
                    "best_bid": float(market.get("bestBid") or 0),
                    "best_ask": float(market.get("bestAsk") or 0),
                    "spread": float(market.get("spread") or 0),
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


def _fetch_markets_by_date(end_date_min: str, end_date_max: str,
                           limit: int = 500) -> list:
    """Fetch active markets from /markets with server-side date filtering."""
    try:
        resp = requests.get(
            f"{GAMMA_API}/markets",
            params={
                "closed": "false",
                "active": "true",
                "limit": limit,
                "order": "volume24hr",
                "ascending": "false",
                "end_date_min": end_date_min,
                "end_date_max": end_date_max,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error("Date-filtered market scan failed: %s", e)
        return []


def _fetch_events_markets(tag_slug: str, limit: int = 50) -> list:
    """Fetch active markets from the /events endpoint using tag_slug filtering."""
    markets = []
    try:
        resp = requests.get(
            f"{GAMMA_API}/events",
            params={
                "closed": "false",
                "active": "true",
                "limit": limit,
                "order": "volume24hr",
                "ascending": "false",
                "tag_slug": tag_slug,
            },
            timeout=15,
        )
        resp.raise_for_status()
        for event in resp.json():
            for m in event.get("markets", []):
                if m.get("closed") or not m.get("active"):
                    continue
                markets.append(m)
    except Exception as e:
        log.debug("Events scan %s failed: %s", tag_slug, e)
    return markets


def scan_markets(active_token_ids: set) -> list:
    """Scan markets: date-filtered /markets API + tag-filtered /events."""
    seen_tokens = set()
    qualifying = []
    total_scanned = 0
    tag_counts = {}

    now = datetime.now(timezone.utc)
    end_min = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_max = (now + timedelta(days=MAX_EXPIRY_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")

    date_markets = _fetch_markets_by_date(end_min, end_max, limit=500)
    tag_counts["expiring_7d"] = len(date_markets)
    total_scanned += len(date_markets)

    for c in _parse_market_candidates(date_markets, active_token_ids):
        tid = c["token_id"]
        if tid not in seen_tokens and tid not in blacklisted_tokens:
            seen_tokens.add(tid)
            c["_tag"] = "date"
            qualifying.append(c)

    for slug in SCAN_TAG_SLUGS:
        markets = _fetch_events_markets(slug, limit=50)
        tag_counts[slug] = len(markets)
        total_scanned += len(markets)

        for c in _parse_market_candidates(markets, active_token_ids):
            tid = c["token_id"]
            if tid not in seen_tokens and tid not in blacklisted_tokens:
                seen_tokens.add(tid)
                c["_tag"] = slug
                qualifying.append(c)

    tags_str = " ".join(f"{k}={v}" for k, v in tag_counts.items())
    log.info("Scan — %d candidates (scanned %d, blacklisted %d) [%s]",
             len(qualifying), total_scanned, len(blacklisted_tokens), tags_str)

    qualifying.sort(key=lambda m: m["volume"], reverse=True)
    return qualifying


# ── Order Placement ───────────────────────────────────────────────────────────

STALE_ORDER_MINUTES = int(os.getenv("STALE_MINUTES", "10"))


def score_market(token_id: str, client: ClobClient, label: str = "") -> dict | None:
    """Score market by spread tightness and bid depth. Rejects outside buy range."""
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
            log.info("REJECT %s: ask=$%.3f outside $%.2f-$%.2f", label[:30], best_ask, BUY_MIN, BUY_MAX)
            return None
        if best_bid < BUY_MIN * 0.8:
            log.info("REJECT %s: bid=$%.3f too low", label[:30], best_bid)
            return None

        spread = best_ask - best_bid
        spread_pct = spread / best_ask if best_ask > 0 else 1
        if spread_pct > MAX_SPREAD_PCT:
            log.info("REJECT %s: spread=%.1f%% > %.1f%%  bid=$%.3f ask=$%.3f", label[:30], spread_pct*100, MAX_SPREAD_PCT*100, best_bid, best_ask)
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

    bal = get_usdc_balance()
    if bal < BET_SIZE * 1.1:
        log.info("SKIP: low balance $%.2f", bal)
        return None

    size = int(BET_SIZE / price)
    if size < 1:
        return None
    cost = round(price * size, 2)

    log.info(
        "BUY: %s | %.0f@$%.3f=$%.2f bid=$%.3f ask=$%.3f spd=$%.3f depth=$%.0f",
        market["question"][:30],
        size, price, cost, best_bid, best_ask, spread, info["all_bid_usd"],
    )

    try:
        buy_args = OrderArgs(
            token_id=token_id,
            price=round(price, 2),
            size=int(size),
            side=BUY,
        )
        opts = CreateOrderOptions(tick_size=str(tick), neg_risk=neg_risk)

        signed = client.create_order(buy_args, options=opts)
        result = client.post_order(signed, OrderType.FAK)

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
            "sell_target": SELL_TARGET,
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
    tick = float(position.get("tick_size", 0.01))

    real_bal = None
    try:
        bal_info = client.get_balance_allowance(
            BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=token_id))
        raw = int(bal_info.get("balance", 0))
        real_bal = raw / 1e6
    except Exception:
        pass
    size = min(position["size"], real_bal) if real_bal else position["size"]
    size = round(size, 2)
    if size < 1:
        return False
    neg_risk = position.get("neg_risk", False)
    buy_price = position.get("buy_price", 0)

    sell_price = position.get("sell_target") or SELL_TARGET

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


def check_order_status(client: ClobClient, order_id: str) -> str:
    """Check order status. Returns: FILLED, INVALID, LIVE, or UNKNOWN."""
    try:
        order = client.get_order(order_id)
        if order:
            status = order.get("status", "")
            if status in ("MATCHED", "FILLED"):
                return "FILLED"
            if status in ("INVALID", "CANCELLED"):
                return "INVALID"
            return status
    except Exception:
        pass
    return "UNKNOWN"


def check_order_filled(client: ClobClient, order_id: str) -> bool:
    return check_order_status(client, order_id) == "FILLED"


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

    is_neg_risk_pos = position.get("neg_risk", False)
    # Try gasless relayer first
    if relay_client and _relayer_redeem(ctf, condition_id, neg_risk=is_neg_risk_pos,
                                         token_id=position.get("token_id"), outcome_index=0):
        add_trade({
            "type": "CLAIM",
            "question": position["question"][:80],
            "tx": "relayer",
            "time": datetime.now(timezone.utc).isoformat(),
        })
        return True

    is_neg_risk = position.get("neg_risk", False)
    try:
        log.info("Claiming (direct): %s", position["question"][:60])
        if is_neg_risk and neg_risk_adapter:
            token_id = int(position.get("token_id", 0))
            bal = ctf.functions.balanceOf(account.address, token_id).call()
            outcome_idx = 0  # default; ideally track outcomeIndex
            amounts = [bal, 0] if outcome_idx == 0 else [0, bal]
            tx = neg_risk_adapter.functions.redeemPositions(
                bytes.fromhex(condition_id.replace("0x", "")),
                amounts,
            ).build_transaction({
                "from": account.address,
                "nonce": w3.eth.get_transaction_count(account.address),
                "gas": 400_000,
                "maxFeePerGas": int(w3.eth.gas_price * 1.5),
                "maxPriorityFeePerGas": w3.to_wei(30, "gwei"),
            })
        else:
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


def _discover_held_token_ids(w3: Web3, account, ctf) -> list[int]:
    """Scan on-chain ERC-1155 TransferSingle events to find token IDs with nonzero balance."""
    token_ids = set()
    CHUNK = 45_000
    try:
        latest = w3.eth.block_number
        # ~14 days of blocks at ~2s/block ≈ 600k blocks
        scan_start = max(0, latest - 700_000)
        cursor = scan_start
        while cursor <= latest:
            end = min(cursor + CHUNK, latest)
            try:
                events = ctf.events.TransferSingle.get_logs(
                    from_block=cursor,
                    to_block=end,
                    argument_filters={"to": account.address},
                )
                for ev in events:
                    token_ids.add(ev.args["id"])
            except Exception:
                pass
            cursor = end + 1
        log.info("SWEEP: discovered %d unique token IDs from on-chain events", len(token_ids))
    except Exception as e:
        log.warning("SWEEP: event scan failed: %s", e)

    # Filter to only tokens we actually still hold
    held = []
    for tid in token_ids:
        try:
            bal = ctf.functions.balanceOf(account.address, tid).call()
            if bal > 0:
                held.append(tid)
        except Exception:
            pass
    log.info("SWEEP: %d/%d tokens still held in wallet", len(held), len(token_ids))
    return held


def _resolve_token_metadata(token_id: str) -> dict | None:
    """Look up condition_id, market_id, resolution status for a token_id via the Gamma API."""
    try:
        resp = requests.get(
            f"{GAMMA_API}/markets",
            params={"clob_token_ids": token_id, "limit": 1},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data:
                m = data[0]
                return {
                    "condition_id": m.get("conditionId") or m.get("condition_id", ""),
                    "market_id": str(m.get("id", "")),
                    "question": m.get("question", "?")[:80],
                    "resolved": m.get("closed", False) or m.get("resolved", False),
                }
    except Exception:
        pass
    return None


def sweep_orphaned_tokens(w3: Web3, account, ctf) -> int:
    """Scan for leftover conditional tokens and redeem resolved ones."""
    active_token_ids = {int(p["token_id"]) for p in bot_state.get("positions", [])}

    on_chain_ids = _discover_held_token_ids(w3, account, ctf)
    if not on_chain_ids:
        return 0

    # Build metadata from closed positions
    closed_by_tid = {}
    for pos in bot_state.get("closed_positions", []):
        tid = pos.get("token_id")
        if tid:
            closed_by_tid[int(tid)] = pos

    seen_conditions = set()
    redeemed = 0
    usdc_before = 0
    try:
        usdc_before = usdc_contract.functions.balanceOf(account.address).call() / 1e6
    except Exception:
        pass

    nonce = w3.eth.get_transaction_count(account.address)

    for tid in on_chain_ids:
        if tid in active_token_ids:
            continue

        # Look up metadata: first from closed positions, then from Gamma API
        meta = closed_by_tid.get(tid)
        cid = meta.get("condition_id") if meta else None
        question = meta.get("question", "?") if meta else "?"
        market_id = meta.get("market_id", "") if meta else ""
        resolved = False

        if not cid or not market_id:
            gamma = _resolve_token_metadata(str(tid))
            if gamma:
                cid = cid or gamma["condition_id"]
                question = gamma["question"]
                market_id = gamma["market_id"]
                resolved = gamma["resolved"]
            time.sleep(0.3)

        if not cid or cid in seen_conditions:
            continue
        seen_conditions.add(cid)

        if not resolved and market_id:
            dummy_pos = {"market_id": market_id, "question": question}
            resolved = check_market_resolved(dummy_pos)

        if not resolved:
            log.debug("SWEEP skip (not resolved): %s", question[:50])
            continue

        bal = ctf.functions.balanceOf(account.address, tid).call()
        log.info("SWEEP: redeeming %s (%.2f tokens) — %s", str(cid)[:16], bal / 1e6, question[:50])

        # Detect neg_risk from gamma metadata
        is_neg_risk = meta.get("neg_risk", False) if meta else False
        if not is_neg_risk and market_id:
            try:
                gr = requests.get(f"{GAMMA_API}/markets/{market_id}", timeout=5)
                if gr.ok:
                    is_neg_risk = bool(gr.json().get("negRisk"))
            except Exception:
                pass

        # Try gasless relayer first
        if relay_client and _relayer_redeem(ctf, cid, neg_risk=is_neg_risk,
                                             token_id=str(tid), outcome_index=0):
            redeemed += 1
            add_trade({
                "type": "REDEEM",
                "question": question[:80],
                "tx": "relayer",
                "time": datetime.now(timezone.utc).isoformat(),
            })
            continue

        try:
            if is_neg_risk and neg_risk_adapter:
                amounts = [bal, 0]  # try Yes first; if fails, try No
                tx = neg_risk_adapter.functions.redeemPositions(
                    bytes.fromhex(cid.replace("0x", "")),
                    amounts,
                ).build_transaction({
                    "from": account.address, "nonce": nonce, "gas": 400_000,
                    "maxFeePerGas": int(w3.eth.gas_price * 1.5),
                    "maxPriorityFeePerGas": w3.to_wei(30, "gwei"),
                })
            else:
                tx = ctf.functions.redeemPositions(
                    Web3.to_checksum_address(USDC_ADDRESS),
                    b"\x00" * 32,
                    bytes.fromhex(cid.replace("0x", "")),
                    [1, 2],
                ).build_transaction({
                    "from": account.address, "nonce": nonce, "gas": 200_000,
                    "gasPrice": w3.eth.gas_price,
                })
            signed = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=90)
            if receipt.status == 1:
                redeemed += 1
                nonce += 1
                log.info("SWEEP OK: %s tx=%s", question[:50], tx_hash.hex())
                add_trade({
                    "type": "REDEEM",
                    "question": question[:80],
                    "tx": tx_hash.hex(),
                    "time": datetime.now(timezone.utc).isoformat(),
                })
            else:
                nonce += 1
                log.warning("SWEEP reverted: %s (market may not be resolved)", question[:50])
        except Exception as e:
            err = str(e).lower()
            if "revert" in err or "execution reverted" in err:
                log.debug("SWEEP: %s not redeemable yet", question[:40])
            else:
                log.error("SWEEP error for %s: %s", question[:50], e)

    if redeemed > 0:
        try:
            usdc_after = usdc_contract.functions.balanceOf(account.address).call() / 1e6
            gained = usdc_after - usdc_before
            log.info("SWEEP done: %d redeemed, USDC gained: $%.2f (now $%.2f)",
                     redeemed, gained, usdc_after)
        except Exception:
            log.info("SWEEP done: %d redeemed", redeemed)
    return redeemed


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
.st.hold{background:#4a3520;color:#f59e0b}
.st.sold{background:#1a3f2a;color:#22c55e}
.st.claimed{background:#1a3f2a;color:#22c55e}
.st.expired{background:#3f1a1a;color:#ef4444}
.st.cancelled{background:#2a2a2a;color:#888}
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
.trunc{max-width:450px;white-space:normal;word-wrap:break-word}
.tabs{display:flex;gap:4px;margin-bottom:12px}
.tab{padding:6px 14px;border-radius:6px;font-size:0.78rem;cursor:pointer;background:#0a0a0f;border:1px solid #1e1e30;color:#888}
.tab.active{background:#1e3a5f;color:#60a5fa;border-color:#2e4a6f}
.tab .cnt{font-size:0.68rem;margin-left:4px;opacity:.7}
.cbtn{border:none;color:white;padding:3px 8px;border-radius:4px;font-size:0.7rem;cursor:pointer;font-weight:600}
.cbtn.sell{background:#ef4444}.cbtn.sell:hover{background:#dc2626}
.cbtn.cancel{background:#f59e0b}.cbtn.cancel:hover{background:#d97706}
.actions{display:flex;gap:3px}
@media(max-width:600px){.cards{grid-template-columns:1fr 1fr}.trunc{max-width:250px}}
</style>
</head>
<body>
<div class="c">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:4px">
    <h1><span class="dot" id="dot"></span> Vig</h1>
    <button id="pauseBtn" onclick="togglePause()" style="margin-left:auto;padding:6px 16px;border-radius:6px;border:none;font-weight:700;cursor:pointer;font-size:0.8rem">--</button>
  </div>
  <div class="sub" id="sub">Connecting...</div>
  <div class="wallet" id="wallet"></div>
  <div class="strat" id="strat"></div>

  <div class="cards">
    <div class="card"><div class="l">USDC Balance</div><div class="v g" id="bal">--</div></div>
    <div class="card"><div class="l">Open Bets</div><div class="v b" id="active">--</div></div>
    <div class="card"><div class="l">Invested</div><div class="v" id="tspent">--</div></div>
    <div class="card"><div class="l">Returned</div><div class="v g" id="treturned">--</div></div>
    <div class="card"><div class="l">Portfolio Value</div><div class="v b" id="portval">--</div></div>
    <div class="card"><div class="l">Net P&L</div><div class="v" id="pnl">--</div></div>
    <div class="card"><div class="l">Win Rate</div><div class="v y" id="winrate">--</div></div>
    <div class="card"><div class="l">W / L</div><div class="v" id="wl">--</div></div>
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
function timeFmt(s){if(!s)return'--';const d=new Date(s);return d.toLocaleDateString('en-US',{month:'short',day:'numeric',timeZone:'America/New_York'})+' '+d.toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',timeZone:'America/New_York'})+' ET'}

let _paused=false;
async function togglePause(){
  const ep=_paused?'/api/resume':'/api/pause';
  try{const r=await fetch(ep,{method:'POST'});const d=await r.json();if(d.success)_paused=d.paused;refresh()}catch(e){}
}

async function refresh(){
  try{
    const r=await fetch('/api/status',{signal:AbortSignal.timeout(8000)});
    if(!r.ok){document.getElementById('sub').textContent='Server error ('+r.status+')';return}
    const d=await r.json();

    _paused=d.paused||false;
    const pbtn=document.getElementById('pauseBtn');
    pbtn.textContent=_paused?'RESUME':'PAUSE';
    pbtn.style.background=_paused?'#22c55e':'#ef4444';

    const isLive=d.running&&!d.paused;
    document.getElementById('dot').className='dot '+(isLive?'on':'off');
    const tick=d.last_tick?new Date(d.last_tick).toLocaleTimeString('en-US',{timeZone:'America/New_York'}):'--';
    const stLabel=d.paused?'Paused':(d.running?'Running':'Offline');
    document.getElementById('sub').textContent=stLabel+' \u00b7 Last tick '+tick+' ET \u00b7 Poll '+d.config.poll_seconds+'s'+(d.builder_relayer?' \u00b7 Builder':'');
    document.getElementById('wallet').textContent=d.wallet||'';
    document.getElementById('strat').textContent=
      'Buy '+d.config.buy_range+' \u2192 Sell '+d.config.profit_target+' GTC'+
      ' \u00b7 $'+d.config.bet_size+'/bet \u00b7 Spread \u2264'+d.config.max_spread;

    document.getElementById('bal').textContent='$'+d.usdc_balance.toFixed(2);
    const pv=d.portfolio_value||0;
    document.getElementById('portval').textContent=pv?'$'+pv.toFixed(2):'--';
    document.getElementById('active').textContent=d.active_positions+'/'+d.max_bets;
    document.getElementById('tspent').textContent='$'+d.total_spent.toFixed(2);
    document.getElementById('treturned').textContent='$'+d.total_returned.toFixed(2);

    const netPnl=d.net_pnl||0;
    const pnlEl=document.getElementById('pnl');
    pnlEl.textContent='$'+pnlStr(netPnl);
    pnlEl.className='v '+(netPnl>=0?'g':'r');

    const closed=d.closed_positions||[];
    const wins=d.wins||0;const losses=d.losses||0;
    const total=wins+losses;
    const wr=total?((wins/total)*100).toFixed(0)+'%':'--';
    document.getElementById('winrate').textContent=wr;
    document.getElementById('wl').textContent=wins+'W / '+losses+'L';
    document.getElementById('gas').textContent=d.gas_balance.toFixed(4);

    document.getElementById('openCnt').textContent='('+d.positions.length+')';
    document.getElementById('closedCnt').textContent='('+closed.length+')';

    // Open positions
    const pe=document.getElementById('panelOpen');
    if(!d.positions.length){pe.innerHTML='<div class="empty">No open bets</div>'}
    else{
      let h='<table><tr><th>Market</th><th>Shares</th><th>Entry</th><th>Bid</th><th>Ask</th><th>P&L (at Bid)</th><th>Target</th><th>Status</th><th></th></tr>';
      d.positions.forEach((p,i)=>{
        const st=p.hold_override?'hold':(p.status||'pending');
        const bp=p.buy_price||0;const sz=p.size||0;
        const bid=p.best_bid||0;const ask=p.best_ask||0;
        const bidStr=bid?'$'+bid.toFixed(3):'--';
        const askStr=ask?'$'+ask.toFixed(3):'--';
        const bc=bid>bp?'pnl-pos':bid<bp?'pnl-neg':'';
        const ac=ask>bp?'pnl-pos':ask<bp?'pnl-neg':'';
        const upnl=bid?(bid*sz)-(p.cost||0):0;
        const upnlStr=bid?'$'+pnlStr(upnl):'--';
        const upnlCls=bid?pnlClass(upnl):'';
        let btns='';
        if(st==='held'){
          btns=`<div class="actions"><button class="cbtn sell" onclick="sellPos('${p.token_id}',${bid},${sz},${bp})">SELL</button><button class="cbtn cancel" onclick="cancelSell('${p.token_id}','${p.question}')">CANCEL</button></div>`;
        }else{
          btns=`<button class="cbtn sell" onclick="cancelPending('${p.token_id}')">✕</button>`;
        }
        h+=`<tr><td class="trunc">${p.question}</td><td>${sz.toFixed(0)}</td><td>$${bp.toFixed(3)}</td><td class="${bc}">${bidStr}</td><td class="${ac}">${askStr}</td><td class="${upnlCls}">${upnlStr}</td><td>$${(p.sell_target||0).toFixed(2)}</td><td><span class="st ${st}">${st}</span></td><td>${btns}</td></tr>`;
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

async function sellPos(tokenId,bid,sz,bp){
  const rev=(bid*sz).toFixed(2);const pnl=(bid*sz-bp*sz).toFixed(2);
  if(!confirm(`SELL ${sz.toFixed(0)} shares at bid $${bid.toFixed(3)}?\n\nReturn: ~$${rev}\nP&L: $${pnl}`))return;
  try{
    const r=await fetch('/api/close',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token_id:tokenId})});
    const d=await r.json();
    if(d.success){alert('Sold: '+d.message);refresh()}else{alert('Error: '+d.error)}
  }catch(e){alert('Request failed')}
}
async function cancelSell(tokenId,question){
  if(!confirm(`Cancel GTC sell for:\n${question}\n\nPosition will stay held without a sell order.`))return;
  try{
    const r=await fetch('/api/cancel-sell',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token_id:tokenId})});
    const d=await r.json();
    if(d.success){alert('Cancelled: '+d.message);refresh()}else{alert('Error: '+d.error)}
  }catch(e){alert('Request failed')}
}
async function cancelPending(tokenId){
  if(!confirm('Cancel this pending buy order?'))return;
  try{
    const r=await fetch('/api/close',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token_id:tokenId})});
    const d=await r.json();
    if(d.success){alert('Cancelled: '+d.message);refresh()}else{alert('Error: '+d.error)}
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

    closed_all = bot_state["closed_positions"]
    filled = [c for c in closed_all if c.get("exit_type") not in ("expired", "cancelled")]
    total_pnl = sum(c.get("pnl", 0) for c in filled)
    wins = len([c for c in filled if c.get("pnl", 0) > 0])
    losses = len([c for c in filled if c.get("pnl", 0) < 0])
    open_cost = sum(p.get("cost", 0) for p in bot_state["positions"])

    pv = 0
    try:
        pv = data_api_value()
    except Exception:
        pass

    return jsonify({
        "running": bot_state["running"],
        "paused": bot_state.get("paused", False),
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
        "net_pnl": round(total_pnl, 2),
        "wins": wins,
        "losses": losses,
        "open_cost": round(open_cost, 2),
        "portfolio_value": pv,
        "builder_relayer": relay_client is not None,
        "closed_positions": closed_all[-50:],
        "trades": trade_history[-30:],
        "config": {
            "bet_size": BET_SIZE,
            "buy_range": f"${BUY_MIN}-${BUY_MAX}",
            "profit_target": f"${SELL_TARGET:.2f}",
            "max_spread": f"{MAX_SPREAD_PCT*100:.1f}%",
            "poll_seconds": POLL_SECONDS,
        },
        "timezone": "UTC",
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
            actions.append("cancelled buy order — USDC returned")
            close_position(pos, "cancelled", 0)

        elif pos["status"] == "held":
            if pos.get("sell_order_id"):
                cancel_order(clob_client, pos["sell_order_id"])
                actions.append("cancelled sell order")

            tick = float(pos.get("tick_size", 0.01))
            neg_risk = pos.get("neg_risk", False)
            buy_price = pos.get("buy_price", 0)

            real_bal = None
            try:
                bal_info = clob_client.get_balance_allowance(
                    BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=token_id))
                raw = int(bal_info.get("balance", 0))
                real_bal = raw / 1e6
            except Exception:
                pass

            size = min(pos["size"], real_bal) if real_bal else pos["size"]
            size = round(size, 2)

            book = clob_client.get_order_book(token_id)
            bids = getattr(book, "bids", [])
            ltp = float(getattr(book, "last_trade_price", 0) or 0)

            if not bids:
                return jsonify({"success": False, "error": "No bids at all — cannot sell"})

            sell_price = float(bids[-1].price)
            if sell_price < 0.001:
                return jsonify({"success": False, "error": f"Best bid too low: ${sell_price:.4f}"})

            sell_args = OrderArgs(
                token_id=token_id,
                price=round(sell_price, 4),
                size=size,
                side=SELL,
            )
            opts = CreateOrderOptions(tick_size=str(tick), neg_risk=neg_risk)
            signed = clob_client.create_order(sell_args, options=opts)
            result = clob_client.post_order(signed, OrderType.FAK)

            order_id = result.get("orderID", "")
            if order_id:
                import time as _time
                _time.sleep(1)
                try:
                    bal_after = clob_client.get_balance_allowance(
                        BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=token_id))
                    remaining = int(bal_after.get("balance", 0)) / 1e6
                except Exception:
                    remaining = 0

                sold_shares = max(0, size - remaining)
                revenue = round(sell_price * sold_shares, 2)

                if remaining < 1:
                    close_position(pos, "sold", sell_price)
                    pos["status"] = "done"
                    bot_state["positions"] = [p for p in bot_state["positions"] if p["status"] != "done"]
                    save_positions(bot_state["positions"])
                    actions.append(
                        f"FAK sold {sold_shares:.0f} shares @ ${sell_price:.3f} — "
                        f"${revenue:.2f} returned (fully sold)")
                else:
                    pos["size"] = round(remaining, 2)
                    pos["sell_order_id"] = None
                    save_positions(bot_state["positions"])
                    actions.append(
                        f"FAK partial: sold {sold_shares:.0f}/{size:.0f} shares @ ${sell_price:.3f} — "
                        f"${revenue:.2f} returned, {remaining:.0f} shares remain")
            else:
                return jsonify({"success": False,
                    "error": f"FAK sell not filled (no liquidity at bid). Try again or wait."})

        else:
            close_position(pos, "manual", 0)
            pos["status"] = "done"
            bot_state["positions"] = [p for p in bot_state["positions"] if p["status"] != "done"]
            save_positions(bot_state["positions"])

        add_trade({
            "type": "CLOSE",
            "question": pos["question"][:80],
            "price": sell_price if 'sell_price' in dir() else 0,
            "time": datetime.now(timezone.utc).isoformat(),
        })

        msg = "; ".join(actions) if actions else "Position closed"
        log.info("Manual close: %s — %s", pos["question"][:50], msg)
        return jsonify({"success": True, "message": msg})

    except Exception as e:
        log.error("Manual close failed: %s", e)
        return jsonify({"success": False, "error": str(e)})


@flask_app.route("/api/cancel-sell", methods=["POST"])
def api_cancel_sell():
    """Cancel GTC sell order but keep position held (let it ride)."""
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
        if pos.get("sell_order_id"):
            cancel_order(clob_client, pos["sell_order_id"])
            pos["sell_order_id"] = None
            pos["hold_override"] = True
            save_positions(bot_state["positions"])
            log.info("Cancel sell: %s — GTC removed, holding", pos["question"][:50])
            return jsonify({"success": True,
                "message": f"GTC sell cancelled. Position stays held — bot will NOT auto-sell."})
        else:
            return jsonify({"success": False, "error": "No active sell order to cancel"})
    except Exception as e:
        log.error("Cancel sell failed: %s", e)
        return jsonify({"success": False, "error": str(e)})




@flask_app.route("/api/pause", methods=["POST"])
def api_pause():
    global bot_paused
    bot_paused = True
    bot_state["paused"] = True
    log.info("BOT PAUSED by user")
    return jsonify({"success": True, "paused": True})


@flask_app.route("/api/resume", methods=["POST"])
def api_resume():
    global bot_paused
    bot_paused = False
    bot_state["paused"] = False
    log.info("BOT RESUMED by user")
    return jsonify({"success": True, "paused": False})


@flask_app.route("/api/reconcile", methods=["POST"])
def api_reconcile():
    """Trigger Data API portfolio reconciliation."""
    try:
        api_pos = data_api_positions()
        pv = data_api_value()
        return jsonify({"success": True, "data_api_positions": len(api_pos),
                        "portfolio_value": pv})
    except Exception as e:
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

# ── Builder relayer init ──────────────────────────────────────────────────────

def init_builder_relayer():
    """Initialize Builder relayer for gasless transactions (optional)."""
    global relay_client
    if not (BUILDER_KEY and BUILDER_SECRET and BUILDER_PASSPHRASE):
        log.info("Builder relayer: disabled (no POLY_BUILDER_* env vars)")
        return
    try:
        from py_builder_relayer_client.client import RelayClient
        from py_builder_signing_sdk.config import BuilderConfig
        from py_builder_signing_sdk.sdk_types import BuilderApiKeyCreds
        builder_config = BuilderConfig(
            local_builder_creds=BuilderApiKeyCreds(
                key=BUILDER_KEY, secret=BUILDER_SECRET, passphrase=BUILDER_PASSPHRASE,
            )
        )
        relay_client = RelayClient(
            "https://relayer-v2.polymarket.com", 137, PRIVATE_KEY, builder_config
        )
        safe_addr = relay_client.get_expected_safe()
        if not relay_client.get_deployed(safe_addr):
            log.info("Deploying Safe wallet %s via relayer...", safe_addr)
            resp = relay_client.deploy()
            resp.wait()
            log.info("Safe wallet deployed: %s", safe_addr)
        else:
            log.info("Safe wallet already deployed: %s", safe_addr)
        log.info("Builder relayer: ENABLED (gasless redemptions)")
    except ImportError as e:
        log.warning("Builder relayer: import error — %s, using direct tx", e)
    except Exception as e:
        log.warning("Builder relayer init failed: %s — using direct tx", e)


def _relayer_redeem(ctf, condition_id: str, neg_risk=False, token_id=None, outcome_index=0) -> bool:
    """Attempt gasless redeem via Builder relayer. Returns True on success."""
    if not relay_client:
        return False
    try:
        from py_builder_relayer_client.models import SafeTransaction, OperationType
        if neg_risk:
            bal = ctf.functions.balanceOf(account_instance.address, int(token_id)).call() if token_id else 0
            if bal == 0:
                return False
            amounts = [bal, 0] if outcome_index == 0 else [0, bal]
            redeem_data = neg_risk_adapter.encode_abi(
                abi_element_identifier="redeemPositions",
                args=[bytes.fromhex(condition_id.replace("0x", "")), amounts]
            )
            target = NEG_RISK_ADAPTER
        else:
            redeem_data = ctf.encode_abi(
                abi_element_identifier="redeemPositions",
                args=[
                    Web3.to_checksum_address(USDC_ADDRESS),
                    b"\x00" * 32,
                    bytes.fromhex(condition_id.replace("0x", "")),
                    [1, 2],
                ]
            )
            target = CTF_ADDRESS
        tx = SafeTransaction(
            to=target,
            operation=OperationType.Call,
            data=redeem_data,
            value="0",
        )
        response = relay_client.execute([tx], f"Redeem {condition_id[:16]}")
        result = response.wait()
        if result:
            log.info("REDEEMED (gasless) condition %s...", condition_id[:16])
            return True
        log.error("RELAYER REDEEM FAILED %s...", condition_id[:16])
        return False
    except Exception as e:
        log.error("RELAYER REDEEM ERROR: %s — falling back to direct tx", e)
        return False


def run():
    if not PRIVATE_KEY:
        raise ValueError("PRIVATE_KEY not set in .env")

    global clob_client
    log.info("Starting Vig swing bot")
    log.info("Buy range    : $%.2f - $%.2f", BUY_MIN, BUY_MAX)
    log.info("Sell target  : $%.2f", SELL_TARGET)
    log.info("Max spread   : %.1f%%", MAX_SPREAD_PCT * 100)
    log.info("Bet size     : $%.0f", BET_SIZE)
    log.info("Max positions: %d", MAX_BETS)
    log.info("Poll interval: %ds", POLL_SECONDS)

    clob = build_clob_client()
    clob_client = clob
    w3, account, ctf, neg_risk_adapter = build_web3()
    init_builder_relayer()

    global trade_history
    positions = load_positions()
    for p in positions:
        if p.get("status") == "buying":
            p["status"] = "pending"
        elif p.get("status") in ("selling", "bought"):
            p["status"] = "held"
    trade_history = load_trades()
    bot_state["closed_positions"] = load_closed()
    closed = bot_state["closed_positions"]
    filled_closed = [c for c in closed if c.get("exit_type") not in ("expired", "cancelled")]
    bot_state["total_returned"] = sum(c.get("revenue", 0) for c in filled_closed)
    bot_state["total_spent"] = (
        sum(c.get("cost", 0) for c in filled_closed) +
        sum(p.get("cost", 0) for p in positions)
    )
    bot_state["total_buys"] = len(filled_closed) + len(positions)
    bot_state["total_sells"] = len([c for c in closed if c.get("exit_type") in ("sold", "manual")])
    log.info("Restored stats: spent=$%.2f returned=$%.2f buys=%d sells=%d",
             bot_state["total_spent"], bot_state["total_returned"],
             bot_state["total_buys"], bot_state["total_sells"])

    bot_state["running"] = True
    bot_state["started_at"] = datetime.now(timezone.utc).isoformat()
    bot_state["wallet"] = account.address
    bot_state["positions"] = positions

    threading.Thread(target=start_dashboard, daemon=True).start()

    tick_count = 0
    while True:
        try:
            tick_count += 1
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
                        close_position(pos, "cancelled", 0)
                        pos["status"] = "done"

            # 2. Check pending buys — if filled, place sell
            for pos in positions:
                if pos["status"] == "pending":
                    if check_order_filled(clob, pos["buy_order_id"]):
                        log.info("Buy filled: %s", pos["question"][:50])
                        pos["status"] = "held"
                        place_sell(clob, pos)
                        save_positions(positions)

                elif pos["status"] == "held" and not pos.get("sell_order_id") and not pos.get("hold_override"):
                    log.info("Placing sell for unmanaged position: %s", pos["question"][:50])
                    place_sell(clob, pos)
                    save_positions(positions)

                elif pos["status"] == "held" and pos.get("sell_order_id"):
                    sell_status = check_order_status(clob, pos["sell_order_id"])
                    if sell_status == "FILLED":
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
                    elif sell_status == "INVALID":
                        log.info("Sell order invalidated: %s — clearing for re-sell or redeem", pos["question"][:50])
                        pos["sell_order_id"] = None
                        save_positions(positions)

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

            # 5b. Cleanup orphaned CLOB orders (sell orders for closed positions)
            try:
                active_order_ids = set()
                for p in positions:
                    if p.get("buy_order_id"):
                        active_order_ids.add(p["buy_order_id"])
                    if p.get("sell_order_id"):
                        active_order_ids.add(p["sell_order_id"])

                clob_orders = clob.get_orders()
                for o in clob_orders:
                    if o.get("status") == "LIVE" and o.get("id") not in active_order_ids:
                        cancel_order(clob, o["id"])
                        log.info("CLEANUP: cancelled orphan %s order %s",
                                 o.get("side", "?"), o.get("id", "")[:20])
            except Exception as e:
                log.debug("Order cleanup check failed: %s", e)

            # 5c. Sweep orphaned conditional tokens from closed positions (every 5 ticks)
            if tick_count % 5 == 1:
                try:
                    sweep_orphaned_tokens(w3, account, ctf)
                except Exception as e:
                    log.debug("Token sweep failed: %s", e)

            # 6. Fill empty slots — score a batch, buy the best
            slots = MAX_BETS - len(positions)
            log.info("Open slots: %d%s", slots, " (PAUSED)" if bot_paused else "")

            if slots > 0 and not bot_paused:
                active_ids = {p["token_id"] for p in positions}
                candidates = scan_markets(active_ids)

                tagged = [c for c in candidates if c.get("_tag") != "volume"]
                fallback = [c for c in candidates if c.get("_tag") == "volume"]
                log.info("Candidates: %d tagged, %d volume-only (from %d total)",
                         len(tagged), len(fallback), len(candidates))

                check_pool = tagged[:80]
                remaining = 100 - len(check_pool)
                if remaining > 0 and fallback:
                    check_pool += random.sample(fallback, min(remaining, len(fallback)))
                random.shuffle(check_pool)

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
