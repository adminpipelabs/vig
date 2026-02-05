# 🚀 Start the Bot

## Quick Start

```bash
cd /Users/mikaelo/vig
python3.11 main.py
```

## What the Bot Will Do

1. **Connect to PostgreSQL** (automatically detected from `DATABASE_URL`)
2. **Scan Polymarket** every hour for markets expiring in 5-60 minutes
3. **Place bets** on qualifying markets (favorite price 0.70-0.90)
4. **Settle bets** automatically when markets resolve
5. **Track everything** in PostgreSQL database

## Monitor the Bot

**Check logs:**
- Bot will print status to console
- Look for: "WINDOW X", "Scanning Polymarket", "Placing bets"

**Check database:**
```bash
python3.11 -c "from db import Database; import os; from dotenv import load_dotenv; load_dotenv(); db = Database(database_url=os.getenv('DATABASE_URL')); cur = db.conn.cursor(); cur.execute('SELECT COUNT(*) FROM bets WHERE result=\"pending\"'); print(f'Pending bets: {cur.fetchone()[0]}')"
```

**Check Railway Dashboard:**
- Visit: https://vig-production.up.railway.app/
- Should show live stats from PostgreSQL

## Bot Configuration

- **Mode:** LIVE (`PAPER_MODE=false`)
- **Database:** PostgreSQL ✅
- **Scan Interval:** 3600 seconds (1 hour)
- **Expiry Window:** 5-60 minutes
- **Price Range:** 0.70-0.90 (favorite)
- **Max Bets/Window:** 10

## Stop the Bot

Press `Ctrl+C` to stop gracefully (finishes current window)

---

**Ready to start!** Run: `python3.11 main.py` 🚀
