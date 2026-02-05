# CLOB Internal Accounting — Key Finding

## The Discovery

**Polymarket CLOB uses internal accounting, NOT direct ERC1155 token custody.**

## How It Works

1. **When you place a bet:**
   - USDC.e goes to exchange contract ✅ (seen on-chain)
   - Position tracked **internally by Polymarket** (not ERC1155 in wallet)

2. **When you win:**
   - Polymarket credits your **internal balance**
   - No on-chain ERC1155 tokens created
   - No redemption transaction needed

3. **To get money OUT:**
   - Need to **WITHDRAW** from Polymarket internal system
   - This triggers on-chain transfer to wallet

## Why ERC1155 Balances Are 0

- Tokens aren't held in your wallet
- They're tracked in Polymarket's internal database
- Only when you withdraw does money move on-chain

## The $97.10 Explained

**Polymarket.com shows:**
- Total Portfolio Value: $97.10
- This is your **internal equity** (cash + positions)

**CLOB API shows:**
- Available Cash: $0.24
- This is **withdrawable cash** only

**The difference ($96.86) is:**
- Position value: ~$31.99 (pending bets)
- Settled winnings: ~$65 (not yet withdrawn)

## Next Steps

1. Check Polymarket.com for "Withdraw" button
2. Positions may auto-settle but need manual withdrawal
3. Or there's a "Claim" step we're missing
