"""Diagnostic: find markets with REAL order book liquidity."""
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
import requests, json, os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("PRIVATE_KEY")
clob = ClobClient("https://clob.polymarket.com", key=key, chain_id=POLYGON)

print("Scanning Gamma API for liquid markets...")
liquid = []
checked = 0

for offset in range(0, 2000, 100):
    resp = requests.get("https://gamma-api.polymarket.com/markets", params={
        "closed": "false", "limit": 100, "offset": offset,
    }, timeout=15)
    markets = resp.json()
    if not markets:
        break

    for m in markets:
        tl = json.loads(m.get("clobTokenIds", "[]")) if isinstance(m.get("clobTokenIds"), str) else m.get("clobTokenIds", [])
        ol = json.loads(m.get("outcomes", "[]")) if isinstance(m.get("outcomes"), str) else m.get("outcomes", [])
        vol = float(m.get("volumeNum", 0) or 0)
        q = m.get("question", "")

        for i, tid in enumerate(tl[:2]):
            try:
                book = clob.get_order_book(tid)
                bids = getattr(book, "bids", [])
                asks = getattr(book, "asks", [])
                bb = float(bids[0].price) if bids else 0
                ba = float(asks[0].price) if asks else 99
                spread = ba - bb
                checked += 1
                o = ol[i] if i < len(ol) else "?"

                if spread < 0.15 and bb >= 0.01:
                    liquid.append({
                        "q": q[:55], "o": o, "bid": bb, "ask": ba,
                        "spread": spread, "nb": len(bids), "na": len(asks),
                        "vol": vol, "tid": tid[:20],
                    })
                    print(f"  LIQUID #{len(liquid)}: {q[:50]} [{o}] bid={bb:.3f} ask={ba:.3f} spd={spread:.3f} bids={len(bids)} vol=${vol:,.0f}")

                if checked % 100 == 0:
                    print(f"  ... checked {checked} tokens, found {len(liquid)} liquid ...")

            except Exception as e:
                pass

        if len(liquid) >= 50 or checked > 2000:
            break
    if len(liquid) >= 50 or checked > 2000:
        break

print(f"\n=== RESULTS ===")
print(f"Checked {checked} tokens across {offset + 100} markets")
print(f"Found {len(liquid)} with spread < $0.15 and bid > $0.01")

liquid.sort(key=lambda x: x["spread"])
print(f"\nTop 30 by tightest spread:")
for i, l in enumerate(liquid[:30]):
    print(f"  {i+1}. {l['q']} [{l['o']}]")
    print(f"     bid=${l['bid']:.3f} ask=${l['ask']:.3f} spread=${l['spread']:.3f} bids={l['nb']} asks={l['na']} vol=${l['vol']:,.0f}")
