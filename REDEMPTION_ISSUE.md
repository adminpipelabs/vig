# CRITICAL: Missing Share Redemption in Settlement

## Problem

The bot detects winning bets and marks them as "won" in the database, but **does NOT redeem the shares** to convert them to cash.

## Current Settlement Flow

```python
# bet_manager.py line 110-116
def settle_bets(self, window_id):
    for bet in pending:
        result, payout = self._check_live_settlement(bet)  # Checks Gamma API
        
        if result == "won":
            # ❌ MISSING: Actually redeem shares on Polymarket
            self.db.update_bet_result(bet.id, "won", payout, profit)  # Just updates DB
```

## What Should Happen

When a bet wins:
1. ✅ Detect market resolved (currently working)
2. ✅ Mark as "won" in database (currently working)
3. ❌ **REDEEM shares on Polymarket** (MISSING)
4. ❌ Verify redemption succeeded before marking as won

## Impact

- **14 winning bets** have been marked as "won"
- **Shares worth ~$164** are sitting unredeemed on Polymarket
- **Cash balance shows $0.24** instead of expected $56.88
- **Missing $56.64** is actually unredeemed winning shares

## Check on Polymarket.com

1. Go to Portfolio
2. Look for positions showing "Redeem" or "Claim" button
3. These are winning positions that haven't been cashed out

## API Investigation

Checked `py-clob-client` for redemption methods:
- ❌ No `redeem()` method found
- ❌ No `claim()` method found
- ❌ No `get_positions()` method found
- ✅ `get_balance_allowance()` exists but requires specific `token_id` for conditional tokens

## Next Steps

1. **Check Polymarket.com manually** for redeemable positions
2. **Find the correct API method** to redeem winning shares
3. **Update settlement code** to redeem shares before marking as won
4. **Manually redeem existing winning positions** to recover the $56.64

## Code Location

- Settlement logic: `bet_manager.py` line 97-131
- Live settlement check: `bet_manager.py` line 141-193
- Missing redemption call: Should be added after line 116
