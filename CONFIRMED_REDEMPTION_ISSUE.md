# CONFIRMED: Redemption Issue — On-Chain Proof

## On-Chain Evidence

**From Polygonscan transfer CSV:**

### Incoming Transfers: 4 total
- +$20.00 USDC (initial deposit)
- +$75.00 USDC (initial deposit)  
- +$10.00 USDC.e (from Polymarket Proxy)
- +$84.94 USDC.e (from Polymarket Proxy)
- **Total: $189.94**

### Outgoing Transfers: 24 total
- -$95.00 USDC (to Polymarket Deposit)
- **22 transfers to exchanges:**
  - CTF Exchange: $55.47
  - NegRisk Exchange: $39.23
- **Total: $189.70**

### Critical Finding
**ZERO incoming transfers FROM exchanges (CTF or NegRisk) after bets were placed.**

When you win a bet and redeem:
- Exchange should send USDC.e BACK to your wallet
- **Expected: ~14 incoming transfers for 14 winning bets**
- **Actual: 0 incoming transfers from exchanges**

**Conclusion:** Winnings were **NEVER redeemed** — they exist as ERC1155 conditional tokens somewhere.

## ERC1155 Balance Check Results

Checked balances at:
- Main wallet: `0x989B7F2308924eA72109367467B8F8e4d5ea5A1D`
- Proxy address: `0xdcad0a12379d4f22ce014826774517937b702277`

**Result:** All balances show **0.00** for all token_ids from won bets.

## Puzzle

If tokens weren't redeemed (confirmed by on-chain data), but balances are 0, where are they?

**Possible explanations:**
1. Tokens held in exchange contracts (not yet withdrawn to wallet)
2. Tokens at a different address (CLOB sub-account?)
3. Token ID format issue (need to verify format)
4. Tokens automatically redeemed by Polymarket (but no on-chain evidence)

## Database Status

✅ All 23 bets have `condition_id` populated
✅ Code updated to store `condition_id` going forward
✅ Ready for redemption once we locate tokens

## Next Steps

1. **Check Polymarket.com UI:**
   - Portfolio → Closed positions
   - Look for "Redeem" buttons
   - Check if positions show as "Redeemable"

2. **Investigate token location:**
   - Check if tokens are in exchange contracts
   - Verify token_id format matches Polymarket's system
   - Check CLOB sub-accounts or proxy addresses

3. **If tokens found:**
   - Create redemption script using `condition_id`
   - Update settlement code to auto-redeem

## Addresses Identified

- **Main Wallet:** `0x989B7F2308924eA72109367467B8F8e4d5ea5A1D`
- **Proxy:** `0xdcad0a12379d4f22ce014826774517937b702277` (Polymarket Proxy)
- **CTF Exchange:** `0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e`
- **NegRisk Exchange:** `0xc5d563a36ae78145c45a50134d48a1215220f80a`
- **Polymarket Deposit:** `0xe0a47b404713f716099b5d65a7cd452045c9aaf5`
