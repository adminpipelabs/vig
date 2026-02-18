# Vig — Polymarket Rolling Bet Bot

Automated prediction market bot. Buys YES tokens on favorites near expiry, claims resolved positions, redeploys capital.

## How It Works

Every 60 seconds:

1. **Claim** — Check active positions for resolution, redeem on-chain via CTF contract
2. **Scan** — Query Gamma API for markets expiring within 60 min, priced $0.60–$0.80
3. **Bet** — Fill empty slots (up to 10 simultaneous positions) with market orders
4. **Repeat**

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your private key
python bot.py
```

## Deploy (Railway)

Push to GitHub — Railway auto-deploys. Set env vars in Railway dashboard:
- `PRIVATE_KEY` — Polygon wallet key (onboarded on Polymarket)
- `RPC_URL` — Polygon RPC endpoint
- `MAX_BETS`, `BET_SIZE`, `MIN_PRICE`, `MAX_PRICE`, `EXPIRY_WINDOW`, `POLL_SECONDS`

## Config

| Parameter | Default | Description |
|-----------|---------|-------------|
| MAX_BETS | 10 | Max simultaneous positions |
| BET_SIZE | $10 | USDC per bet |
| MIN_PRICE | $0.60 | Min YES price to enter |
| MAX_PRICE | $0.80 | Max YES price to enter |
| EXPIRY_WINDOW | 60 min | Only bet on markets expiring within this window |
| POLL_SECONDS | 60s | Main loop interval |
