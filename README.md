# Trading Bridge — Production Reference

**Last updated: Feb 22, 2026**

## Server

| | Details |
|---|---|
| **Provider** | Hetzner, Helsinki (Finland) |
| **Hostname** | ubuntu-4gb-hel1-1 |
| **IP** | 46.62.211.255 |
| **SSH** | `ssh root@46.62.211.255` |
| **Why Finland** | Polymarket CLOB allows trading from Finland. No proxy needed. |

> **Do NOT use the Ashburn server (5.161.64.209).** It is in the US which is geoblocked on Polymarket. Bots there are stopped.

## Dashboards

| Bot | URL | Password |
|-----|-----|----------|
| Vig | http://46.62.211.255:8080 | API_SECRET from .env |
| Scalper | http://46.62.211.255:8081 | API_SECRET from .env |

## Bots — How They Run

Both bots run as **Docker containers** on the Helsinki server.

```
docker ps                    # see running containers
docker restart vig-bot       # restart Vig
docker restart vig-scalper   # restart Scalper
docker logs vig-bot --tail 50        # view Vig logs
docker logs vig-scalper --tail 50    # view Scalper logs
```

### File Locations (on Helsinki server)

| Path | What |
|------|------|
| `/root/vig/bot.py` | Vig bot code (mounted read-only into Docker) |
| `/root/vig/scalper.py` | Scalper bot code (mounted into Docker) |
| `/root/vig/.env` | Environment variables (keys, config) |
| `/root/vig/data/` | Vig data: positions.json, closed.json, trades.json |
| `/root/vig/scalper_data/` | Scalper data: scalp_positions.json, etc. |

### GitHub Repo

https://github.com/mikaelo/trading-bridge (branch: main)

> **Note:** The Docker containers mount code from `/root/vig/`, NOT from the git repo at `/opt/trading-bridge/`. To update bot code, edit the files in `/root/vig/` and restart the Docker container.

## Wallets

| Bot | Address | Private Key |
|-----|---------|-------------|
| Vig | `0x989B7F2308924eA72109367467B8F8e4d5ea5A1D` | PRIVATE_KEY in `/root/vig/.env` |
| Scalper | `0x4ae36dfA7CD02BB87334EDC35639f70981c02F54` | PRIVATE_KEY in scalper Docker env |

Both wallets need **USDC on Polygon** to trade.

## Vig Strategy

Swing-trades on any Polymarket market that meets criteria.

| Setting | Value |
|---------|-------|
| Buy range | $0.10 – $0.30 |
| Sell target | $0.45 GTC |
| Bet size | $5 |
| Max spread | 5.0% |
| Max expiry | 1 day (24 hours) |
| Poll interval | 30 seconds |

**Flow:** Scan markets → Buy at ask within range → Place GTC sell at $0.45 → Auto-redeem when market resolves → Reinvest USDC into new bets.

## Scalper Strategy

Trades crypto up/down markets at short intervals.

| Setting | Value |
|---------|-------|
| 15-min | ETH + BTC, $0.40 GTC bid on Up AND Down |
| 5-min | ETH, $0.40 GTC bid on Up AND Down, $2/side |
| Poll interval | 15 seconds |

**Flow:** Find next 15m/5m ETH market → Bid $0.40 on both Up and Down → Auto-redeem after market closes → Reinvest.

## Auto-Redeem

Both bots automatically:
1. Detect when a market resolves
2. Call `redeemPositions` on-chain to convert winning tokens → USDC
3. Sweep orphaned tokens from old positions
4. Use freed USDC to place new bets

No manual intervention needed for redemption.

## Market Maker Rewards

Both bots earn rewards automatically — **no claiming or registration needed**. Polymarket distributes rewards daily at midnight UTC directly to the wallet addresses.

### Two Programs

| Program | Eligible Markets | How It Works | Payout |
|---------|-----------------|--------------|--------|
| **Liquidity Rewards** | All markets | Resting GTC limit orders on the book are scored every minute. Two-sided quoting and tighter spreads score exponentially higher. | Daily USDC at midnight UTC |
| **Maker Rebates** | 5m + 15m crypto, NCAAB, Serie A | When your resting order gets filled by a taker, you earn a share of the taker fees (20% for crypto). | Daily USDC |

### Current Status

| Bot | Reward Eligibility | Notes |
|-----|-------------------|-------|
| **Scalper** | Fully eligible | GTC bids on both Up and Down = two-sided maker orders. Earns both Liquidity Rewards and Maker Rebates on 5m/15m crypto. |
| **Vig** | Partially eligible | Buys use FAK first (taker, no rewards), then falls back to GTC. GTC sell orders do score. |

### How Scoring Works

Orders are scored using a quadratic formula: `S = ((v - s) / v)^2` where `v` is the max incentive spread and `s` is your distance from midpoint. Tighter to midpoint = exponentially more rewards. Two-sided liquidity (bids on both sides) gets a significant bonus.

Each market defines `min_incentive_size` and `max_incentive_spread` — orders outside these bounds score zero. These can be fetched from the CLOB or Markets API.

### Checking Rewards

Rewards are paid directly to the bot wallets. Check USDC balance changes around midnight UTC, or query the Data API:

```bash
# Check Scalper wallet balance history
curl -s "https://data-api.polymarket.com/value?user=0x4ae36dfa7cd02bb87334edc35639f70981c02f54" | python3 -m json.tool
```

### Potential Improvements

1. **Vig bot**: Switch from FAK-first to GTC-only buys so all orders qualify as maker
2. **Both bots**: Check `min_incentive_size` and `max_incentive_spread` per market before placing orders
3. **Scalper**: Price bids relative to midpoint instead of fixed $0.40 for higher scoring
4. **Docs**: https://docs.polymarket.com/market-makers/liquidity-rewards and https://docs.polymarket.com/market-makers/maker-rebates

## Security

- All API endpoints require `API_SECRET` Bearer token
- `/api/status`, `/api/sell`, `/api/withdraw`, `/api/reconcile` — all protected
- Dashboard prompts for password on first visit
- Ports 8080/8081 open to internet (consider firewall or HTTPS reverse proxy)

## What Happened (Feb 21, 2026)

1. Previous agent set up bots on Ashburn (US) server instead of Helsinki (Finland)
2. API endpoints were left open without authentication
3. Attacker found open endpoints, sold 14 positions, withdrew USDC
4. Auth was added after the attack
5. Bots migrated back to Helsinki server where they work without proxy

## Quick Commands

```bash
# SSH into server
ssh root@46.62.211.255

# Check bot status
docker ps

# View Vig logs
docker logs vig-bot --tail 100

# View Scalper logs
docker logs vig-scalper --tail 100

# Restart after config change
docker restart vig-bot
docker restart vig-scalper

# Check on-chain positions for Vig wallet
curl -s "https://data-api.polymarket.com/positions?user=0x989b7f2308924ea72109367467b8f8e4d5ea5a1d" | python3 -m json.tool

# Check on-chain positions for Scalper wallet
curl -s "https://data-api.polymarket.com/positions?user=0x4ae36dfa7cd02bb87334edc35639f70981c02f54" | python3 -m json.tool
```

## Polymarket API Quick Reference

| API | Base URL | Auth |
|-----|----------|------|
| Gamma (market discovery) | https://gamma-api.polymarket.com | None |
| Data (positions, portfolio) | https://data-api.polymarket.com | None |
| CLOB (trading) | https://clob.polymarket.com | API key (derived from wallet) |

Key endpoints:
- `GET /positions?user={wallet}` — on-chain positions
- `GET /value?user={wallet}` — portfolio value
- `GET /book?token_id={id}` — order book
- `GET /midpoint?token_id={id}` — midpoint price

On-chain contracts (Polygon):
- CTF: `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045`
- NegRiskAdapter: `0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296`
- USDC: `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`
