# Vig v1 — Prediction Market Bot

Automated prediction market bot that exploits the favorite-longshot bias on Polymarket. Buys heavy favorites near expiry, grinds consistent small profits at high volume.

## Quick Start

```bash
# 1. Clone and install
cd vig
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env — PAPER_MODE=true for testing

# 3. Run paper trading
python main.py
```

## How It Works

Every 60 minutes:

1. **Scan** — Query Polymarket Gamma API for markets expiring within 60 min
2. **Filter** — Find favorites priced $0.70 - $0.90 with sufficient volume
3. **Bet** — Place limit buy orders on qualifying favorites
4. **Settle** — Wait for market resolution, record results
5. **Snowball** — Reinvest 50% of profit (growth) or pocket 100% (harvest)
6. **Repeat**

## Strategy

| Parameter | Value |
|-----------|-------|
| Side | Whichever side priced $0.70 - $0.90 |
| Starting clip | $10 per bet |
| Max clip | $100 per bet |
| Bets per window | Up to 15 |
| Growth | Reinvest 50%, pocket 50% |
| Harvest | Once at $100 max, pocket 100% |
| Target win rate | >85% |
| Kill switch | <80% over 200 bets |

## Architecture

```
vig/
├── main.py           # Main loop — scan → bet → settle → snowball
├── config.py         # Configuration and env vars
├── scanner.py        # Gamma API market discovery + filtering
├── bet_manager.py    # Order placement (paper + live via py-clob-client)
├── snowball.py       # Clip size management and growth/harvest logic
├── risk_manager.py   # Circuit breaker
├── db.py             # SQLite storage
├── notifier.py       # Telegram alerts
├── requirements.txt
└── .env.example
```

## Modes

### Paper Trading (default)
```bash
PAPER_MODE=true python main.py
```
Scans real Polymarket markets, simulates bets with realistic win probability (price + 5% edge). No wallet needed.

### Live Trading
```bash
PAPER_MODE=false python main.py
```
Requires funded Polygon wallet with USDC on Polymarket.

## Configuration

All strategy params in `config.py`:

- `min_favorite_price` / `max_favorite_price` — Price range for favorites (0.70 - 0.90)
- `expiry_window_minutes` — How close to expiry (60 min)
- `max_bets_per_window` — Max simultaneous bets (15)
- `starting_clip` / `max_clip` — Bet sizes ($10 → $100)
- `snowball_reinvest_pct` — Profit reinvestment rate (50%)
- `max_volume_pct` — Max bet as % of market volume (2%)

## Circuit Breaker

Bot auto-stops if:
- 5 consecutive losses
- Win rate drops below 80% over last 100 bets
- Daily loss exceeds 15% of bankroll
- 4+ losses in a single window

## Telegram Notifications

Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env` for:
- Window summaries (bets, W/L, profit, clip)
- Circuit breaker alerts
- Milestones (hit max clip, etc.)
- Daily summaries

## Validation Plan

1. **Week 1**: Paper trade — collect 500+ simulated bets
2. **Week 2-3**: Live with $10 clips — prove win rate >85%
3. **Week 3-4**: Enable snowball — grow to $100 max
4. **Month 2+**: Scale to $100 clips, target $20k+/month

## Key APIs

| API | Purpose | Auth |
|-----|---------|------|
| Gamma (`gamma-api.polymarket.com`) | Market discovery, prices, metadata | None |
| CLOB (`clob.polymarket.com`) | Order books, live prices, order placement | Private key |
| py-clob-client (PyPI) | Python SDK for CLOB | — |

## License

MIT
