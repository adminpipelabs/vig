# Vig Bot Status Update — Awaiting Dev Input

**Date:** February 4, 2026  
**Status:** Orders failing despite balance and approvals

---

## ✅ What We've Completed

1. **Token Approvals (On-Chain):**
   - ✅ USDC.e → Exchange: Approved
   - ✅ USDC.e → NegRisk Exchange: Approved  
   - ✅ CTF → Exchange (ERC1155): Approved
   - ✅ CTF → NegRisk Exchange (ERC1155): Approved

2. **CLOB Setup:**
   - ✅ CLOB balance: **$94.94 USDC.e** (confirmed via `get_balance_allowance()`)
   - ✅ Called `update_balance_allowance()` successfully
   - ✅ Bot code updated to use `derive_api_key()` and call `update_balance_allowance()` on startup

3. **Bot Status:**
   - ✅ Running and scanning markets
   - ✅ Finding qualifying markets (1-4 per window)
   - ❌ **Orders failing** with "not enough balance / allowance"

---

## ❌ Current Issue

**Error:** All orders fail with:
```
PolyApiException[status_code=400, error_message={'error': 'not enough balance / allowance'}]
```

**Despite:**
- Having $94.94 USDC.e in CLOB exchange ✅
- All on-chain approvals complete ✅
- `update_balance_allowance()` called ✅

---

## 🔍 What We Tested

**1. `client.set_allowances()` Method:**
- ❌ **Does not exist** in py-clob-client v0.34.5
- Available methods: `get_balance_allowance()`, `update_balance_allowance()`

**2. Manual Order Test:**
- Token ID: `88935552803805200614363760402590819779763081586466777299788105505305613405537`
- Price: $0.83
- Size: 1.1976 shares ($1 test)
- **Result:** Same error — "not enough balance / allowance"

**Full traceback:** See `TEST_RESULTS_FOR_DEV.md`

---

## ❓ Questions for Dev

1. **`set_allowances()` method:**
   - You mentioned `client.set_allowances()` but it doesn't exist in v0.34.5
   - Is it in a newer version? Or called something else?
   - Is `update_balance_allowance()` the correct method?

2. **Missing approval step?**
   - We've approved USDC.e and CTF on-chain
   - We've called `update_balance_allowance()` via API
   - Is there another approval step we're missing?

3. **Order format:**
   - Current: `OrderArgs(token_id=..., price=0.83, size=1.1976, side=BUY)`
   - Is the size format correct? (shares vs raw token units?)
   - Is price format correct?

4. **Conditional tokens:**
   - Do we need to approve the specific conditional token (CTF) for each market?
   - Or is the general CTF approval enough?

---

## 📋 Current Configuration

- **py-clob-client:** v0.34.5 (latest)
- **Wallet:** `0x989B7F2308924eA72109367467B8F8e4d5ea5A1D`
- **CLOB Balance:** $94.94 USDC.e
- **Bot:** Running, scanning every 60 minutes

---

## 🎯 What We Need

**Clarification on:**
1. The correct method to set allowances (if not `update_balance_allowance()`)
2. Any missing approval steps
3. Whether order format needs adjustment

**Once clarified, we can:**
- Fix the approval flow
- Test order placement
- Get the bot trading live

---

**Files:**
- Full test results: `TEST_RESULTS_FOR_DEV.md`
- Setup summary: `SETUP_SUMMARY.md`
- Test script: `test_order.py`
