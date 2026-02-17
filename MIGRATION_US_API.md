# Migration to Polymarket US API

## Overview

Vig v2 now supports the Polymarket US API with Ed25519 authentication. This eliminates the need for settlement/redemption flows by using `close-position` endpoint.

## Setup

### 1. Get Polymarket US API Credentials

1. Download Polymarket US iOS app
2. Create account with identity verification
3. Visit https://polymarket.us/developer
4. Generate Ed25519 API keys
5. **Save private key immediately** (shown only once)

### 2. Environment Variables

Add to `.env` or Railway environment:

```bash
# Enable US API
USE_US_API=true

# Polymarket US API credentials
POLYMARKET_US_KEY_ID=your-key-id-uuid
POLYMARKET_US_PRIVATE_KEY=your-ed25519-private-key

# Optional: Profit target and exit timing
PROFIT_TARGET_PCT=0.15  # 15% profit target
FORCE_EXIT_MINUTES=10   # Exit 10 minutes before expiry
```

### 3. Install Dependencies

```bash
pip install cryptography httpx
```

## How It Works

### Strategy Flow

1. **Buy**: Place limit buy order at favorite price
2. **Profit Target**: Immediately place limit sell order at target price (buy_price + profit_target_pct)
3. **Force Exit**: If sell not filled, force-close position 10 minutes before expiry

### Key Differences from Legacy API

| Feature | Legacy CLOB API | US API |
|---------|----------------|--------|
| Authentication | HMAC | Ed25519 signature |
| Order Types | FAK/FOK only | Limit + Market orders |
| Position Exit | Wait for settlement | `close-position` endpoint |
| Redemption | Manual/automated | Not needed |
| Balance | Token-based | USD-based |

## Hetzner Compatibility

✅ **Yes, Hetzner works perfectly!**

The US API is just REST HTTP calls - no special networking requirements. Works from:
- Hetzner servers
- Railway
- Any VPS/cloud provider
- Local development

## Testing

### Paper Mode (Default)

```bash
PAPER_MODE=true python main.py
```

### Live Mode

```bash
USE_US_API=true
POLYMARKET_US_KEY_ID=...
POLYMARKET_US_PRIVATE_KEY=...
PAPER_MODE=false
python main.py
```

## Monitoring

The bot tracks:
- Open positions (buy + sell orders)
- Profit target fills
- Positions needing force-exit
- All via `PositionTracker`

Check logs for:
- `✅ Order placed` - Buy order successful
- `💰 Profit target placed` - Sell order placed
- `💰 Profit target filled` - Sell order executed
- `🚨 Force closing position` - Exiting before expiry
- `✅ Position force-closed` - Exit successful

## Troubleshooting

### Auth Errors

- Verify `POLYMARKET_US_KEY_ID` is correct UUID
- Verify `POLYMARKET_US_PRIVATE_KEY` is correct Ed25519 key
- Check key format (base64, hex, or PEM)

### Order Failures

- Check balance in Polymarket US account
- Verify market slug is correct
- Check rate limits (400 orders/10sec)

### Position Not Closing

- Verify `FORCE_EXIT_MINUTES` is set correctly
- Check expiry time is being parsed correctly
- Verify `close-position` endpoint is accessible

## Rollback

To use legacy CLOB API:

```bash
USE_US_API=false
POLYGON_PRIVATE_KEY=...
```

## Benefits

✅ No settlement wait  
✅ No redemption flow  
✅ Instant position exit  
✅ Cleaner API  
✅ Better rate limits  
✅ Market orders supported  
