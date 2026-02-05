# Quick Start Guide - Run Bot with SQLite

## Start Bot Now (SQLite Mode)

The bot is ready to run with SQLite. Your `.env` currently has `DATABASE_URL` set, which makes it try PostgreSQL. To run with SQLite instead:

### Option 1: Use Startup Script (Recommended)

```bash
cd /Users/mikaelo/vig
./start_bot_sqlite.sh
```

This script automatically:
- Unsets `DATABASE_URL` to force SQLite
- Loads other config from `.env`
- Starts the bot

### Option 2: Manual Start

```bash
cd /Users/mikaelo/vig

# Unset DATABASE_URL for this session
unset DATABASE_URL

# Start bot
python3 main.py
```

### Option 3: Edit .env Temporarily

Comment out `DATABASE_URL` in `.env`:
```bash
# DATABASE_URL=postgresql://...
```

Then run:
```bash
python3 main.py
```

## Verify It's Using SQLite

When the bot starts, you should see:
```
=== Vig v1 Starting (PAPER/LIVE mode) ===
📂 Reading from SQLite: vig.db
```

NOT:
```
📊 Connecting to PostgreSQL...
```

## Current Status

✅ **SQLite database exists**: `vig.db` (3.3 MB, 23 bets, 33,160 windows)  
✅ **Bot code ready**: Already supports SQLite fallback  
✅ **Startup script created**: `start_bot_sqlite.sh`  
⚠️ **PostgreSQL**: Currently experiencing connection timeouts (not blocking bot)

## Architecture

- **Bot runs locally** on your Mac (needs residential IP)
- **Uses SQLite** for data storage (local file, fast, reliable)
- **Dashboard** (when ready) will use PostgreSQL on Railway

## Next Steps After Bot Starts

1. Bot will scan Polymarket every hour
2. Place bets on qualifying markets
3. Store results in local SQLite database
4. You can view data locally or migrate to PostgreSQL later for dashboard

## Troubleshooting

**Bot tries to connect to PostgreSQL?**
- Make sure `DATABASE_URL` is unset: `echo $DATABASE_URL` should be empty
- Use the startup script: `./start_bot_sqlite.sh`

**Want to switch back to PostgreSQL later?**
- Set `DATABASE_URL` in `.env` again
- Or export it: `export DATABASE_URL="postgresql://..."`
