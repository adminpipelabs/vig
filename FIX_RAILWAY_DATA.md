# Fix Railway - Get Data Flowing

## Problem
- ✅ Works on localhost (has data)
- ❌ Railway shows no data (empty)

## Root Cause: Different Databases

**Local:** Using SQLite file (`vig.db`)  
**Railway:** Using PostgreSQL (empty or different)

They're reading from different databases!

## Solution: Migrate Local Data to Railway

### Step 1: Export Local Data

```bash
cd /Users/mikaelo/vig

# Export windows
sqlite3 vig.db ".mode csv" ".headers on" ".output windows.csv" "SELECT * FROM windows;"

# Export bets
sqlite3 vig.db ".mode csv" ".headers on" ".output bets.csv" "SELECT * FROM bets;"

# Export circuit_breaker_log (if exists)
sqlite3 vig.db ".mode csv" ".headers on" ".output circuit_breaker_log.csv" "SELECT * FROM circuit_breaker_log;"
```

### Step 2: Get Railway DATABASE_URL

**Railway Dashboard → Variables → Copy `DATABASE_URL`**

### Step 3: Import to Railway PostgreSQL

```bash
# Set Railway DATABASE_URL
export DATABASE_URL="postgresql://..."  # From Railway

# Import windows
psql "$DATABASE_URL" -c "\COPY windows FROM 'windows.csv' WITH CSV HEADER;"

# Import bets
psql "$DATABASE_URL" -c "\COPY bets FROM 'bets.csv' WITH CSV HEADER;"

# Import circuit_breaker_log (if exists)
psql "$DATABASE_URL" -c "\COPY circuit_breaker_log FROM 'circuit_breaker_log.csv' WITH CSV HEADER;"
```

### Step 4: Verify Data

```bash
# Check counts
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM windows;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM bets;"
```

### Step 5: Refresh Dashboard

**Refresh:** https://vig-production.up.railway.app/

**Should now show:**
- ✅ Window count > 0
- ✅ Bets count > 0
- ✅ Statistics updating

## Alternative: Use Migration Script

```bash
# Set Railway DATABASE_URL
export DATABASE_URL="postgresql://..."  # From Railway
export SQLITE_PATH=vig.db

# Run migration
python3 migrate_to_postgres.py
```

## Ensure Bot Keeps Running

**After migration, verify:**

1. **Bot is running** - Check Railway logs for "Vig v1 Starting"
2. **Bot is scanning** - Check logs for "Scanning Polymarket..."
3. **New bets flowing** - Bot should continue placing bets
4. **Dashboard updating** - New data appears after each window

## Quick Checklist

- [ ] Export local SQLite data
- [ ] Get Railway DATABASE_URL
- [ ] Import data to Railway PostgreSQL
- [ ] Verify data imported (check counts)
- [ ] Refresh dashboard
- [ ] Verify bot is running on Railway
- [ ] Monitor for new bets

## After Migration

**Both local and Railway will use PostgreSQL:**
- Local: Set `DATABASE_URL` in `.env`
- Railway: Already has `DATABASE_URL` set
- Both read/write to same database ✅

**Or keep separate:**
- Local: Keep using SQLite (for testing)
- Railway: Use PostgreSQL (for production)
- Just migrate data once to populate Railway
