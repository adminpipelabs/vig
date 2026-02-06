# Railway Not Working - Troubleshooting

## Issue
- ✅ Works on localhost
- ❌ Not working on Railway (no data feed)

## Possible Causes

### 1. Bot Not Running on Railway

**Check Railway Logs:**
- Railway Dashboard → Your Service → Logs
- Look for: `=== Vig v1 Starting ===`

**If NOT running:**
- Check for errors in logs
- Verify environment variables are set
- Check if bot process crashed

### 2. Database Connection Issue

**Local:** Uses SQLite (vig.db file)  
**Railway:** Needs PostgreSQL or SQLite on persistent volume

**Check:**
- Is `DATABASE_URL` set on Railway?
- Is PostgreSQL service running?
- Can dashboard connect to database?

**Test:**
```bash
# From your Mac, test Railway database
export DATABASE_URL="postgresql://..."  # From Railway
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM windows;"
```

### 3. Bot Running But Not Scanning

**Check logs for:**
- "Scanning Polymarket..." messages
- Any errors during scanning
- "No qualifying markets found" (normal)

**If no scanning:**
- Check `SCAN_INTERVAL_SECONDS` is set
- Verify bot process is actually running
- Check for Python errors

### 4. Different Databases

**Local:** Reading from local SQLite file  
**Railway:** Reading from PostgreSQL (or different SQLite)

**Issue:** Bot writing to one database, dashboard reading from another

**Fix:**
- Ensure both use same `DATABASE_URL`
- Or migrate local data to Railway database

### 5. Environment Variables Missing

**Check Railway → Variables:**

**Required:**
- `DATABASE_URL` (or `DB_PATH`)
- `POLYGON_PRIVATE_KEY`
- `PAPER_MODE`

**Missing vars:** Bot may not start or run incorrectly

## Quick Diagnostic Steps

### Step 1: Check Railway Logs

**Railway Dashboard → Logs**

**Look for:**
```
=== Vig v1 Starting ===
Scanning Polymarket...
```

**If you see this:** Bot is running ✅  
**If you DON'T:** Bot not running ❌

### Step 2: Check Database

**Test Railway database:**
```bash
export DATABASE_URL="postgresql://..."  # From Railway
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM windows;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM bets;"
```

**If counts = 0:** Database empty (bot hasn't run yet)  
**If counts > 0:** Database has data (dashboard should show it)

### Step 3: Compare Local vs Railway

**Local:**
- Database: SQLite (vig.db)
- Bot: Running locally
- Dashboard: Reading from local SQLite

**Railway:**
- Database: PostgreSQL (or different SQLite)
- Bot: Should be running on Railway
- Dashboard: Reading from Railway database

**Issue:** They're using different databases!

### Step 4: Migrate Local Data to Railway

**If local has data but Railway doesn't:**

```bash
# Export from local SQLite
sqlite3 vig.db ".mode csv" ".headers on" ".output windows.csv" "SELECT * FROM windows;"
sqlite3 vig.db ".mode csv" ".headers on" ".output bets.csv" "SELECT * FROM bets;"

# Import to Railway PostgreSQL
export DATABASE_URL="postgresql://..."  # From Railway
psql "$DATABASE_URL" -c "\COPY windows FROM 'windows.csv' WITH CSV HEADER;"
psql "$DATABASE_URL" -c "\COPY bets FROM 'bets.csv' WITH CSV HEADER;"
```

## Most Likely Issue: Different Databases

**Local:** Using SQLite file (`vig.db`)  
**Railway:** Using PostgreSQL (empty)

**Solution:** Migrate local data to Railway PostgreSQL

## Quick Fix: Use Same Database

### Option A: Railway Uses PostgreSQL (Recommended)

1. Migrate local SQLite → Railway PostgreSQL
2. Ensure Railway `DATABASE_URL` is set
3. Bot and dashboard both use PostgreSQL

### Option B: Railway Uses SQLite Volume

1. Railway → Volumes → Create volume at `/data`
2. Set `DB_PATH=/data/vig.db` on Railway
3. Copy local `vig.db` to Railway volume (if possible)
4. Or let bot create fresh database

## Action Items

1. ✅ **Check Railway logs** - Is bot running?
2. ✅ **Test Railway database** - Does it have data?
3. ✅ **Compare databases** - Local vs Railway
4. ✅ **Migrate data** - If needed, copy local data to Railway
5. ✅ **Verify config** - Ensure Railway env vars are set

## Expected After Fix

- Railway logs show bot running
- Railway database has data
- Dashboard shows data from Railway database
- Bot continues placing bets on Railway
