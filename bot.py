"""
Vig - Polymarket Rolling Bet Bot
==================================
Strategy: Always hold up to MAX_BETS active positions.
Each position: YES token on any market priced $0.60-$0.80 expiring within 60 mins.
Claims resolved positions in the background and redeploys capital.

Setup:
    pip install py-clob-client python-dotenv web3 requests

Config:
    Copy .env.example to .env and fill in your values.

Run:
    python bot.py
"""

import os
import json
import time
import logging
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, Side
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
BET_SIZE        = float(os.getenv("BET_SIZE", "10"))       # USDC per bet
MIN_PRICE       = float(os.getenv("MIN_PRICE", "0.60"))    # min YES price
MAX_PRICE       = float(os.getenv("MAX_PRICE", "0.80"))    # max YES price
EXPIRY_WINDOW   = int(os.getenv("EXPIRY_WINDOW", "60"))    # minutes
POLL_SECONDS    = int(os.getenv("POLL_SECONDS", "60"))     # loop interval

# Polymarket endpoints
CLOB_HOST       = "https://clob.polymarket.com"
GAMMA_API       = "https://gamma-api.polymarket.com"

# Polymarket CTF Exchange on Polygon (for claiming)
CTF_ADDRESS     = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

# Minimal ABI — just redeemPositions
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

# USDC on Polygon
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

# Positions file — persists active bets across restarts
POSITIONS_FILE = "positions.json"


# ── State ─────────────────────────────────────────────────────────────────────

def load_positions() -> list:
    """Load active positions from disk."""
    if os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE) as f:
            return json.load(f)
    return []


def save_positions(positions: list):
    """Persist positions to disk."""
    with open(POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2)


# ── Clients ───────────────────────────────────────────────────────────────────

def build_clob_client() -> ClobClient:
    if not PRIVATE_KEY:
        raise ValueError("PRIVATE_KEY not set in .env")
    client = ClobClient(host=CLOB_HOST, key=PRIVATE_KEY, chain_id=POLYGON)
    client.set_api_creds(client.create_or_derive_api_creds())
    log.info("CLOB ready. Address: %s", client.get_address())
    return client


def build_web3() -> tuple:
    """Returns (web3, account, ctf_contract)."""
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to RPC: {RPC_URL}")
    account = w3.eth.account.from_key(PRIVATE_KEY)
    ctf = w3.eth.contract(
        address=Web3.to_checksum_address(CTF_ADDRESS),
        abi=CTF_ABI
    )
    log.info("Web3 ready. Wallet: %s", account.address)
    return w3, account, ctf


# ── Market Scanner ────────────────────────────────────────────────────────────

def scan_markets(active_token_ids: set) -> list:
    """
    Fetch markets from Gamma API.
    Returns qualifying markets not already held.
    Criteria:
      - Active (not resolved)
      - Expires within EXPIRY_WINDOW minutes
      - YES price between MIN_PRICE and MAX_PRICE
      - Not already in our portfolio
    """
    qualifying = []
    now = datetime.now(timezone.utc)

    try:
        resp = requests.get(
            f"{GAMMA_API}/markets",
            params={
                "active": "true",
                "closed": "false",
                "limit": 100,
                "order": "end_date_min",
                "ascending": "true",
            },
            timeout=10,
        )
        resp.raise_for_status()
        markets = resp.json()

        for market in markets:
            try:
                # Parse expiry
                end_str = market.get("end_date_iso") or market.get("endDateIso")
                if not end_str:
                    continue
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                mins_to_expiry = (end_dt - now).total_seconds() / 60

                # Must expire within window and not already expired
                if not (0 < mins_to_expiry <= EXPIRY_WINDOW):
                    continue

                # Get YES token and price
                tokens = market.get("tokens", [])
                yes_token = next((t for t in tokens if t.get("outcome", "").upper() == "YES"), None)
                if not yes_token:
                    continue

                token_id = yes_token.get("token_id")
                price = float(yes_token.get("price", 0))

                # Price filter
                if not (MIN_PRICE <= price <= MAX_PRICE):
                    continue

                # Skip if already held
                if token_id in active_token_ids:
                    continue

                qualifying.append({
                    "market_id": market.get("id"),
                    "question": market.get("question", "Unknown"),
                    "token_id": token_id,
                    "condition_id": market.get("condition_id"),
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

    # Sort by highest price first (most confident)
    qualifying.sort(key=lambda m: m["price"], reverse=True)
    return qualifying


# ── Bet Placement ─────────────────────────────────────────────────────────────

def place_bet(client: ClobClient, market: dict) -> dict | None:
    """Place a market order on the YES token."""
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
            side=Side.BUY,
        )
        result = client.create_and_post_order(args)
        order_id = result.get("orderID", "?")
        log.info("Bet placed. Order ID: %s", order_id)

        return {
            "order_id": order_id,
            "market_id": market["market_id"],
            "question": market["question"],
            "token_id": token_id,
            "condition_id": market["condition_id"],
            "price": price,
            "size": BET_SIZE,
            "end_date": market["end_date"],
            "placed_at": datetime.now(timezone.utc).isoformat(),
            "claimed": False,
        }

    except Exception as e:
        log.error("Failed to place bet: %s", e)
        return None


# ── Claim / Settlement ────────────────────────────────────────────────────────

def check_market_resolved(position: dict) -> bool:
    """Check via Gamma API if market is resolved before attempting on-chain claim."""
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
    """
    Redeem a resolved position on-chain via CTF contract.
    This is completely separate from the CLOB — it is a direct Polygon transaction.
    Returns True if claim succeeded.
    """
    condition_id = position.get("condition_id")
    if not condition_id:
        log.warning("No condition_id for position %s — cannot claim", position.get("order_id"))
        return False

    try:
        log.info("Claiming: %s", position["question"][:60])

        tx = ctf.functions.redeemPositions(
            Web3.to_checksum_address(USDC_ADDRESS),
            b"\x00" * 32,                                          # parentCollectionId = 0x00
            bytes.fromhex(condition_id.replace("0x", "")),         # conditionId
            [1, 2],                                                 # redeem YES and NO slots
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


# ── Main Loop ─────────────────────────────────────────────────────────────────

def run():
    if not PRIVATE_KEY:
        raise ValueError("PRIVATE_KEY not set in .env")

    log.info("Starting Vig rolling bet bot")
    log.info("Max bets     : %d", MAX_BETS)
    log.info("Bet size     : $%.0f USDC", BET_SIZE)
    log.info("Price range  : $%.2f – $%.2f", MIN_PRICE, MAX_PRICE)
    log.info("Expiry window: %d mins", EXPIRY_WINDOW)
    log.info("Poll interval: %ds", POLL_SECONDS)

    clob = build_clob_client()
    w3, account, ctf = build_web3()
    positions = load_positions()

    while True:
        try:
            log.info("── Tick ──────────────────────────────────────────")
            log.info("Active positions: %d / %d", len(positions), MAX_BETS)

            # ── 1. Claim any resolved positions ───────────────────────
            for pos in [p for p in positions if not p.get("claimed")]:
                if check_market_resolved(pos):
                    success = try_claim(w3, account, ctf, pos)
                    if success:
                        pos["claimed"] = True
                        pos["claimed_at"] = datetime.now(timezone.utc).isoformat()

            # Drop claimed positions — capital is freed
            positions = [p for p in positions if not p.get("claimed")]
            save_positions(positions)

            # ── 2. Fill empty slots with new bets ─────────────────────
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
                        time.sleep(1)
            else:
                log.info("Portfolio full — skipping scan")

        except KeyboardInterrupt:
            log.info("Shutting down. Positions saved to %s", POSITIONS_FILE)
            save_positions(positions)
            break
        except Exception as e:
            log.error("Unexpected error in main loop: %s", e)

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run()
