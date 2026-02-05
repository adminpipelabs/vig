# Redemption Setup — Complete

## ✅ Completed

1. **Added condition_id to database schema**
   - Column added to `bets` table
   - Updated `BetRecord` dataclass
   - Updated `insert_bet()` method

2. **Updated bet_manager.py**
   - Now stores `condition_id` when placing bets
   - Future bets will have condition_id automatically

3. **Backfilled existing bets**
   - All 23 bets now have condition_id
   - Looked up from Gamma API using market_id

## Current Status

- **Wallet Type:** EOA with funder address (signature_type=0)
- **condition_id in DB:** ✅ Yes (all 23 bets)
- **Can look up condition_id:** ✅ Yes (via Gamma API)

## Next Steps

**Option A: Programmatic Redemption (if pure EOA)**
- Create `redeem_winnings.py` script
- Use CTF contract `redeemPositions()` method
- Requires: Pure EOA wallet (no funder/proxy)

**Option B: Manual Redemption (if proxy/funder)**
- Go to Polymarket.com
- Connect wallet
- Portfolio → Closed positions
- Click "Redeem" on each winning position

## Verification

Check if condition_ids are stored:
```bash
sqlite3 vig.db "SELECT id, condition_id FROM bets WHERE result='won' LIMIT 5;"
```

All bets should now have condition_id populated.
