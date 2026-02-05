# Redemption Status Summary

## ✅ Completed

1. **Database Updated:**
   - Added `condition_id` column to `bets` table
   - Updated `BetRecord` dataclass to include `condition_id`
   - Updated `insert_bet()` to store `condition_id`
   - Updated `bet_manager.py` to pass `condition_id` when creating bets

2. **Backfilled Existing Bets:**
   - All 23 bets now have `condition_id` populated
   - Looked up from Gamma API using `market_id`

## ⚠️ Wallet Configuration

- **Type:** EOA with funder address (`signature_type=0`, `POLYGON_FUNDER_ADDRESS` set)
- **Status:** May need manual redemption on Polymarket.com (funder address suggests proxy setup)

## 📋 Next Steps

1. **Check Polymarket.com manually:**
   - Go to Portfolio → Closed positions
   - Look for "Redeem" buttons on winning positions
   - If redeem buttons exist, manual redemption is possible

2. **Create redemption script** (if pure EOA):
   - Script ready to create once wallet type confirmed
   - Will use `redeemPositions` on CTF contract
   - Requires condition_id (now available ✅)

3. **Update settlement code:**
   - Add redemption call in `bet_manager.py` `settle_bets()`
   - Only redeem if wallet type supports it

## 🔍 Verification

Run this to verify condition_ids:
```bash
sqlite3 vig.db "SELECT id, market_question, condition_id FROM bets WHERE result='won' LIMIT 5;"
```

All bets should now have condition_id populated.
