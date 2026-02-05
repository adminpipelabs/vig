# Settlement Timing Question for Dev

**Date:** February 4, 2026  
**Issue:** Market shows resolved prices but `closed: False`

---

## Problem

**Market:** Solana Up or Down - February 4, 1PM ET  
**Bet ID:** 15  
**Our Side:** NO @ $0.795  
**Status:** Still showing as "pending" in database

**Market API Response:**
```json
{
  "closed": false,
  "outcomePrices": ["0.9995", "0.0005"]
}
```

**Analysis:**
- Outcome prices clearly show YES won (0.9995) and NO lost (0.0005)
- We bet NO, so this should be a **loss**
- But `closed: false` prevents settlement

---

## Current Settlement Logic

**File:** `bet_manager.py` line 149
```python
if not market.get("closed", False):
    return "pending", 0.0
```

The bot requires `closed: True` before settling, but Polymarket may:
1. Set outcome prices before marking `closed: True`
2. Have a delay between resolution and the `closed` flag
3. Use a different field to indicate resolution

---

## Questions for Dev

1. **Should we check outcome prices even if `closed` is False?**
   - If prices are clearly resolved (e.g., 0.9995/0.0005 or 0.0005/0.9995), should we settle immediately?
   - Or wait for `closed: True`?

2. **Is there another field that indicates resolution?**
   - Does Polymarket expose a different field that shows the market is resolved?
   - Should we check `resolved` or `finalized` fields?

3. **What's the recommended approach?**
   - Wait for `closed: True` (current approach)
   - Check prices when they're clearly resolved (0.95+ or 0.05-)
   - Use a combination of both

---

## Impact

- **Current:** Bet stays "pending" even though market is clearly resolved
- **Risk:** Delayed P&L updates, dashboard shows stale data
- **Frequency:** This may happen with other markets too

---

**Recommendation:** Update settlement logic to check outcome prices even when `closed` is False, if prices are clearly resolved (>= 0.95 or <= 0.05).
