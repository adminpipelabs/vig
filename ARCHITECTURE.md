# Vig Bot Architecture

## Current Setup (Post-Migration Issues)

### Component Locations

| Component | Location | Database | Purpose |
|---|---|---|---|
| **Bot (main.py)** | Local Mac | SQLite (vig.db) | Runs trading logic, needs residential IP to avoid Cloudflare/CLOB blocking |
| **Dashboard** | Railway | PostgreSQL | Web UI for viewing trades/stats (when PostgreSQL is ready) |

### Why This Architecture?

1. **Bot must run locally**: Cloudflare and CLOB block datacenter IPs. Residential IP required for API access.
2. **SQLite for bot**: Works perfectly for local bot operation. Already proven with 95+ paper trades.
3. **PostgreSQL for dashboard**: Needed for Railway deployment (ephemeral filesystem), but not blocking bot operation.

## Database Configuration

### Bot (Local Mac)

**SQLite Mode** (default when `DATABASE_URL` not set):
- Database file: `vig.db` (local file)
- Persistent across restarts
- No network dependency
- Fast and reliable

**To run bot with SQLite:**
```bash
# Option 1: Unset DATABASE_URL
unset DATABASE_URL
python3 main.py

# Option 2: Use startup script
./start_bot_sqlite.sh
```

### Dashboard (Railway)

**PostgreSQL Mode** (when `DATABASE_URL` is set):
- Railway provides `DATABASE_URL` automatically
- Required because Railway filesystem is ephemeral
- Currently experiencing connection timeout issues

## Migration Status

**Status**: ⚠️ **Blocked** - PostgreSQL connection timeouts

**Data to migrate**:
- 23 bets
- 33,160 windows  
- 0 circuit_breaker_log entries

**Migration script**: `migrate_to_postgres.py` (ready, but PostgreSQL too slow)

## Getting Started

### Start Bot Locally (SQLite)

```bash
cd /Users/mikaelo/vig
./start_bot_sqlite.sh
```

Or manually:
```bash
unset DATABASE_URL
python3 main.py
```

### Check Bot Status

```bash
# Check if bot is running
ps aux | grep "main.py" | grep -v grep

# View recent logs
tail -f migration.log  # or check console output
```

## PostgreSQL Debugging (For Dashboard)

### 1. Check Railway PostgreSQL Status

- Railway Dashboard → Database service → Metrics
- Look for CPU/memory spikes
- Check connection count

### 2. Test Connection Locally

```bash
# From your Mac
psql $DATABASE_URL -c "SELECT COUNT(*) FROM information_schema.tables;"
```

### 3. Check Database Tier

- Free tier has aggressive connection limits
- Consider upgrading to paid ($5/mo) for better performance

### 4. Alternative Migration (CSV Export/Import)

If programmatic migration keeps timing out:

```bash
# Export from SQLite
sqlite3 vig.db ".headers on" ".mode csv" ".output windows.csv" "SELECT * FROM windows;"
sqlite3 vig.db ".headers on" ".mode csv" ".output bets.csv" "SELECT * FROM bets;"

# Import to PostgreSQL (from Mac, better connection)
psql $DATABASE_URL -c "\COPY windows FROM 'windows.csv' WITH CSV HEADER;"
psql $DATABASE_URL -c "\COPY bets FROM 'bets.csv' WITH CSV HEADER;"
```

## Next Steps

1. ✅ **Start bot with SQLite** - Get live trades flowing immediately
2. ⏳ **Debug PostgreSQL** - Fix connection issues for dashboard
3. ⏳ **Migrate data** - Once PostgreSQL is stable, migrate historical data
4. ⏳ **Deploy dashboard** - Connect dashboard to PostgreSQL

## Files

- `main.py` - Bot main loop
- `db.py` - Database abstraction (supports both SQLite and PostgreSQL)
- `start_bot_sqlite.sh` - Startup script for SQLite mode
- `migrate_to_postgres.py` - Migration script (when PostgreSQL is ready)
