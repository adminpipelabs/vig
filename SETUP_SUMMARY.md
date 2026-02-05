# Vig Bot Setup Summary — Token Approvals & CLOB Configuration

**Date:** February 4, 2026  
**Status:** Approvals complete, awaiting USDC.e balance confirmation

---

## ✅ What Was Completed

### 1. Token Approvals (All 4 Complete)

**Initial Issue:** The original `approve_tokens.py` script approved **native USDC** (`0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359`), but Polymarket's CLOB uses **USDC.e** (`0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`) as collateral.

**Solution:** Created `approve_tokens_correct.py` that approves USDC.e instead.

**Approvals Completed:**
- ✅ USDC.e → Exchange (`0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E`)
- ✅ USDC.e → NegRisk Exchange (`0xC5d563A36AE78145C45a50134d48A1215220f80a`)
- ✅ CTF → Exchange (ERC1155) — Already approved
- ✅ CTF → NegRisk Exchange (ERC1155) — Already approved

**Transaction Hashes:**
- USDC.e → Exchange: `0x6bf28f5aef65608565d3aaa81322e31845cfbec51037e223e5738aa41000ddca`
- USDC.e → NegRisk: `0x43a49f6fddcb59f448290524dbfee29f957b5275c399d0c3e61f17b7aa706a14`

**Gas Cost:** ~0.0785 MATIC

---

## 🔍 Key Discovery: USDC vs USDC.e

**Problem Identified:**
- Polymarket CLOB collateral address: `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` (USDC.e)
- Original script approved: `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359` (native USDC)
- Wallet currently has: 0.00 USDC.e

**Current Error:**
```
Order failed: PolyApiException[status_code=400, error_message={'error': 'not enough balance / allowance'}]
```

This error occurs because:
1. ✅ Allowances are now set correctly (USDC.e approved)
2. ❌ Wallet has 0 USDC.e balance

---

## 🤔 Open Question: Fund Deposit Process

**User Context:**
- User reports "$93 USDC deposited on Polymarket"
- Wallet shows 0 USDC.e balance
- Bot cannot place orders due to "not enough balance"

**Possible Scenarios:**
1. **Funds deposited via Polymarket UI** → May be in Polymarket's internal system, not accessible via CLOB API
2. **Funds need to be USDC.e** → If deposited as native USDC, may need conversion
3. **Deposit via CLOB API** → There might be a `deposit()` function we haven't found yet
4. **Simpler onboarding** → Polymarket likely has a streamlined process we haven't discovered

**What to Investigate:**
- Check Polymarket docs for CLOB deposit/balance methods
- Verify if `py-clob-client` has deposit functionality
- Check if funds deposited via UI are accessible via API
- Look for balance checking methods in CLOB client

---

## 📋 Current Bot Status

**Bot is Running:**
- ✅ Scanning markets every 60 minutes
- ✅ Finding qualifying markets (3-4 per window)
- ✅ Attempting to place orders
- ❌ Failing with "not enough balance / allowance"

**Configuration:**
- `PAPER_MODE=false` (live trading)
- `STARTING_CLIP=10.0`
- `MAX_CLIP=10.0`
- `MAX_BETS_PER_WINDOW=10`
- Wallet: `0x989B7F2308924eA72109367467B8F8e4d5ea5A1D`
- Alchemy RPC: Configured and working

---

## 🛠️ Files Created/Modified

1. **`approve_tokens.py`** — Original script (approves native USDC)
2. **`approve_tokens_correct.py`** — Fixed script (approves USDC.e) ✅
3. **`check_env.py`** — Environment variable verification script
4. **`check_approvals.py`** — Existing script to verify approvals

---

## 🔧 Technical Details

**CLOB Client Methods Available:**
- `get_collateral_address()` → Returns `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` (USDC.e)
- `get_exchange_address()` → Returns `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E`
- `get_balance_allowance()` → ✅ **Working!** Returns balance and allowances

**Current Balance Check Result:**
```python
params = BalanceAllowanceParams(
    asset_type=AssetType.COLLATERAL,
    signature_type=0
)
result = clob.get_balance_allowance(params)
# Returns: {'balance': '0', 'allowances': {...}}
```
**Balance: 0** (confirms funds need to be deposited)

**Contract Addresses:**
- USDC (native): `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359`
- USDC.e (CLOB collateral): `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`
- CTF: `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045`
- Exchange: `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E`
- NegRisk Exchange: `0xC5d563A36AE78145C45a50134d48A1215220f80a`

---

## 📝 Next Steps

1. **Investigate Polymarket deposit process:**
   - Check if `py-clob-client` has deposit methods
   - Review Polymarket CLOB documentation for balance/deposit flows
   - Verify if UI deposits are accessible via API

2. **Verify fund availability:**
   - Confirm if $93 USDC is accessible via CLOB API
   - Check if conversion from native USDC → USDC.e is needed
   - Test balance checking methods

3. **Once funds are available:**
   - Bot should automatically start placing orders
   - Monitor first 5-10 windows closely
   - Verify orders appear on polymarket.com

---

## 💡 Recommendations

1. **Update original `approve_tokens.py`** to use USDC.e instead of native USDC
2. **Add balance checking** to `bet_manager.py` before placing orders (better error messages)
3. **Document the USDC.e requirement** clearly in setup instructions
4. **Investigate Polymarket's recommended onboarding flow** — there's likely a simpler way

---

## 📞 Questions for Dev

1. ✅ **Balance checking works** — `get_balance_allowance()` confirms balance is 0
2. ❓ **How to deposit funds?** — Is there a CLOB API deposit method, or must funds be deposited via Polymarket UI?
3. ❓ **UI vs API deposits** — Are funds deposited via Polymarket UI accessible via CLOB API?
4. ❓ **USDC.e requirement** — Do users need to swap native USDC → USDC.e, or does Polymarket handle this?
5. 💡 **Recommendation** — Add balance checking to `bet_manager.py` before placing orders for better error messages

---

**Bot Log Location:** `/Users/mikaelo/.cursor/projects/Users-mikaelo-trading-bridge/terminals/43597.txt`

**Dashboard:** https://vig-production.up.railway.app/ (password: vig2026)
