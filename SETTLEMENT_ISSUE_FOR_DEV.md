# Settlement Issue — Markets Resolved But Not Settling

**Date:** February 4, 2026  
**Issue:** Markets showing resolved prices but `closed: False`, preventing settlement

---

## 🔍 Problem

**Example:** Solana Up or Down - February 4, 1PM ET (Market ID: 1320833)

**Market Status:**
- `closed: False` (but market is clearly resolved)
- `outcomePrices: ["0.9995", "0.0005"]` (YES won, NO lost)
- Our bet: NO side @ $0.795, $10.00

**Current Settlement Logic:**
```python
if not market.get("closed", False):
    return "pending", 0.0
```

This requires `closed: True` before checking prices, but Polymarket sometimes sets resolved prices (`0.9995`/`0.0005`) before marking the market as `closed: True`.

---

## ✅ Temporary Fix Applied

Updated `_check_live_settlement()` to check prices first:

```python
# Check if market is resolved (either closed OR prices show clear resolution)
market_closed = market.get("closed", False)
clearly_resolved = winning_price >= 0.95 or winning_price <= 0.05

if market_closed or clearly_resolved:
    if winning_price >= 0.95:
        return "won", bet.size
    elif winning_price <= 0.05:
        return "lost", 0.0
```

**Result:** Successfully settled the Solana bet (LOST, -$10.00)

---

## ❓ Question for Dev

**Is this the correct approach?** 

Should we:
1. **Check prices first** (settle if `>= 0.95` or `<= 0.05` even if `closed: False`)?
2. **Wait for `closed: True`** (risk missing settlements if Polymarket delays the flag)?
3. **Use a different API endpoint** or field to check resolution?

**Current behavior:** Polymarket Gamma API sometimes shows resolved prices (`0.9995`/`0.0005`) before setting `closed: True`. This causes bets to stay pending even though the market is clearly resolved.

---

## 📊 Impact

- **Before fix:** 14 pending bets (some may have been resolved but not settled)
- **After fix:** 13 pending bets (Solana bet settled)
- **Risk:** Other markets may have the same issue

---

**Need guidance on:** Best practice for detecting market resolution when `closed` flag is delayed.
