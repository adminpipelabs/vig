"""RAW order book diagnostic — check what the API actually returns."""
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
import requests, json, os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("PRIVATE_KEY")
clob = ClobClient("https://clob.polymarket.com", key=key, chain_id=POLYGON)

# Find "US strikes Iran" market
resp = requests.get("https://gamma-api.polymarket.com/markets", params={
    "closed": "false", "limit": 100, "offset": 0,
}, timeout=15)

target = None
for m in resp.json():
    if "iran" in m.get("question", "").lower() and "18" in m.get("question", "").lower():
        target = m
        break

if not target:
    # Try search
    resp2 = requests.get("https://gamma-api.polymarket.com/markets", params={
        "closed": "false", "limit": 100, "offset": 100,
    }, timeout=15)
    for m in resp2.json():
        if "iran" in m.get("question", "").lower():
            target = m
            break

if not target:
    print("Could not find Iran market, trying first 3 markets with volume > 100K")
    resp3 = requests.get("https://gamma-api.polymarket.com/markets", params={
        "closed": "false", "limit": 20, "order": "volumeNum", "ascending": "false",
    }, timeout=15)
    for m in resp3.json()[:3]:
        target = m
        break

if not target:
    print("No market found at all!")
    exit()

q = target.get("question", "?")
tl = json.loads(target.get("clobTokenIds", "[]")) if isinstance(target.get("clobTokenIds"), str) else target.get("clobTokenIds", [])
ol = json.loads(target.get("outcomes", "[]")) if isinstance(target.get("outcomes"), str) else target.get("outcomes", [])
vol = target.get("volumeNum", 0)
neg_risk = target.get("negRisk", False)

print(f"Market: {q}")
print(f"Volume: ${vol}")
print(f"NegRisk: {neg_risk}")
print(f"Tokens: {len(tl)}")
print()

for i, tid in enumerate(tl[:2]):
    o = ol[i] if i < len(ol) else "?"
    print(f"--- Token {i}: {o} ---")
    print(f"  ID: {tid}")

    book = clob.get_order_book(tid)
    print(f"  Type: {type(book)}")
    print(f"  Dir: {[a for a in dir(book) if not a.startswith('_')]}")

    bids = getattr(book, "bids", [])
    asks = getattr(book, "asks", [])
    ltp = getattr(book, "last_trade_price", None)
    print(f"  last_trade_price: {ltp}")
    print(f"  Bids ({len(bids)}):")
    for b in bids[:8]:
        print(f"    price={b.price} size={b.size} type={type(b.price)}")
    print(f"  Asks ({len(asks)}):")
    for a in asks[:8]:
        print(f"    price={a.price} size={a.size} type={type(a.price)}")

    bb = float(bids[0].price) if bids else 0
    ba = float(asks[0].price) if asks else 0
    print(f"  best_bid={bb} best_ask={ba} spread={ba-bb}")
    print()
