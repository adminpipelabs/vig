# P&L Calculation Issues — Need Dev Help

## Problem Summary

There are two critical issues with P&L calculations in the dashboard:

### Issue 1: P&L Values Don't Match Between Tabs

**Overview Tab:**
- Shows Total P&L: **-$1.13** (from `SUM(profit)` in database)

**P&L Flow Tab:**
- Shows Net P&L: **+$38.87** (incorrect calculation)
- Should show: **-$33.12** (actual cash flow impact)

**The Discrepancy:**
- Database `SUM(profit)` = -$1.13 (only includes settled bets, pending bets have profit=0)
- Actual cash flow: Starting $90.00 → Current $56.88 = **-$33.12**
- Difference: $31.99 (exactly matches pending bets amount)

### Issue 2: Expected Balance Calculation

**Current Problem:**
- We're calculating expected balance from cash flow simulation
- But we have EXACT data in the BET records:
  - `amount` = exact bet size
  - `payout` = exact payout if won (or 0 if lost)
  - `profit` = exact profit/loss
  - `result` = won/lost/pending

**What We Should Do:**
- Calculate expected balance directly from BET table data
- For each bet: subtract `amount`, then add `payout` if settled
- This gives us the EXACT expected balance, not an estimate

## Current Data

```
Starting Balance: $90.00
Total Deployed: $197.18
Total Payout (settled): $164.06
Pending Bets: $31.99 (5 bets)

Expected Balance (from bet data): $90 - $197.18 + $164.06 = $56.88
Actual CLOB Balance: $0.24
Missing: $56.64
```

## Questions for Dev

1. **Which P&L should we show?**
   - Option A: Realized P&L (-$1.13) — only settled bets
   - Option B: Cash Flow P&L (-$33.12) — includes pending bets impact
   - Option C: Both (Realized vs. Unrealized)

2. **Expected Balance Calculation:**
   - Should we calculate from BET table directly (we have exact amounts)?
   - Or continue with cash flow simulation?
   - The BET table has all the data we need: `amount`, `payout`, `result`

3. **P&L Flow Table:**
   - The table is showing empty — is the API returning data correctly?
   - Need to verify `/api/pnl-flow` endpoint is working

## Code Locations

- **Overview P&L:** `dashboard.py` line 36 — `SUM(profit)`
- **P&L Flow API:** `dashboard.py` line 134 — `/api/pnl-flow`
- **P&L Flow Display:** `dashboard.py` line 721 — `loadPnlFlow()`

## Recommendation

Use BET table data directly:
```sql
SELECT 
  SUM(amount) as total_deployed,
  SUM(CASE WHEN result != 'pending' THEN payout ELSE 0 END) as total_returned,
  SUM(profit) as realized_pnl,
  SUM(CASE WHEN result = 'pending' THEN amount ELSE 0 END) as pending_amount
FROM bets
```

Expected Balance = Starting + Realized P&L - Pending Amount
= $90.00 + (-$1.13) - $31.99 = $56.88 ✓

This matches the cash flow calculation exactly.
