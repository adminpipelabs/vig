# CRITICAL BUG: Missing Share Redemption

## Summary

**The bot marks bets as "won" but does NOT redeem the shares for cash.**

## Evidence

1. **14 winning bets** marked as "won" in database
2. **Total payout recorded:** $164.06
3. **Actual CLOB cash:** $0.24
4. **Missing:** $56.64 (likely unredeemed shares)

## Current Code Flow

```python
# bet_manager.py line 110-116
def settle_bets(self, window_id):
    for bet in pending:
        result, payout = self._check_live_settlement(bet)  # ✅ Detects win
        
        if result == "won":
            # ❌ MISSING: client.redeem(token_id=bet.token_id)
            self.db.update_bet_result(bet.id, "won", payout, profit)  # Only updates DB
```

## What's Missing

When a bet wins:
1. ✅ Market resolution detected (working)
2. ✅ Database updated (working)
3. ❌ **Shares NOT redeemed** (BUG)
4. ❌ **Cash NOT received** (BUG)

## Impact

- Winning shares worth ~$164 are sitting unredeemed
- Cash balance is $0.24 instead of $56.88
- Bot can't place new bets (insufficient balance)

## Immediate Actions Needed

1. **Check Polymarket.com manually:**
   - Go to Portfolio
   - Look for "Redeem" buttons on winning positions
   - Manually redeem to recover funds

2. **Find redemption API method:**
   - Check py-clob-client GitHub: https://github.com/Polymarket/py-clob-client
   - Look for `redeem()`, `claim()`, or similar method
   - May need to use Conditional Token Framework (CTF) directly

3. **Fix settlement code:**
   ```python
   if result == "won":
       # Step 1: Redeem shares
       redemption = client.redeem(token_id=bet.token_id, amount=bet.size)
       
       # Step 2: Only mark as won if redemption succeeded
       if redemption.success:
           self.db.update_bet_result(bet.id, "won", payout, profit)
   ```

4. **Create redemption script:**
   - Script to redeem all existing winning positions
   - Run once to recover the $56.64

## Files to Update

- `bet_manager.py` - Add redemption call in `settle_bets()`
- Create `redeem_winnings.py` - One-time script to redeem existing wins
