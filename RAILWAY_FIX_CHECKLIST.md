# Railway Fix Checklist - Step by Step

**Goal:** Get bot running on Railway with data flowing to dashboard

---

## Step 1: Fix Railway PostgreSQL (CRITICAL - Do This First)

### Option A: Restart PostgreSQL Service

**Railway Dashboard → PostgreSQL Service → Settings → Restart**

**Test connection:**
1. Railway Dashboard → PostgreSQL Service → Data tab
2. Run: `SELECT 1;`
3. **If it works:** ✅ Proceed to Step 2
4. **If it times out:** ❌ Try Option B

### Option B: Create Fresh PostgreSQL Instance

**If restart doesn't work:**

1. Railway Dashboard → New → Database → Add PostgreSQL
2. Copy new `DATABASE_URL` (Railway auto-generates)
3. Railway Dashboard → Vig Service → Variables
4. Update `DATABASE_URL` with new connection string
5. Test: Railway → PostgreSQL → Data tab → `SELECT 1;`

**If still timing out:** Use Option C (SQLite + Volume)

### Option C: SQLite + Persistent Volume (Fallback)

**If PostgreSQL keeps timing out:**

1. Railway Dashboard → Vig Service → Settings → Volumes
2. Click "Add Volume"
3. Mount path: `/data`
4. Railway Dashboard → Vig Service → Variables
5. Add: `DB_PATH=/data/vig.db`
6. Remove or unset: `DATABASE_URL` (so app uses SQLite)
7. Redeploy service

**Note:** SQLite works fine for bot-only. If you add dashboard that reads same file, consider PostgreSQL for concurrent access.

---

## Step 2: Migrate Local Data to Railway

**Once Railway database is accessible:**

### From Your Mac:

```bash
cd /Users/mikaelo/vig

# Get Railway DATABASE_URL from Railway Dashboard → Variables
export DATABASE_URL="postgresql://..."  # Copy from Railway

# Set local SQLite path
export SQLITE_PATH=./vig.db

# Run migration
python3 migrate_to_postgres.py
```

**Expected output:**
```
SQLite counts: {'bets': 23, 'windows': 33160, 'circuit_breaker_log': 0}
✓ PostgreSQL connected
✓ Schema created
  bets: Migrating 23 new rows...
  windows: Migrating 33160 new rows...
✅ MIGRATION COMPLETE
```

**Verify:**
```bash
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM windows;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM bets;"
```

**Should show:** 33160 windows, 23 bets

---

## Step 3: Add Residential Proxy (For Live Trading)

**If using live mode (`PAPER_MODE=false`):**

1. Sign up for Bright Data (or SmartProxy/Oxylabs)
2. Get proxy credentials: `http://username:password@host:port`
3. Railway Dashboard → Vig Service → Variables
4. Add: `RESIDENTIAL_PROXY_URL=http://username:password@host:port`

**For testing:** Keep `PAPER_MODE=true` (no proxy needed)

---

## Step 4: Verify Bot is Running

**Railway Dashboard → Vig Service → Logs**

**Look for:**
```
=== Vig v1 Starting (PAPER/LIVE mode) ===
✓ PostgreSQL connected (or SQLite)
CLOB client initialized (with/without proxy)
```

**If you DON'T see this:**
- Check for errors in logs
- Verify environment variables are set
- Check if service restarted successfully

---

## Step 5: Verify Dashboard Shows Data

**Refresh:** https://vig-production.up.railway.app/

**Should show:**
- ✅ Window count > 0 (should show 33160 after migration)
- ✅ Bets count > 0 (should show 23 after migration)
- ✅ Statistics updating
- ✅ Recent bets table populated

**If still empty:**
- Check database has data (Step 2 verification)
- Check Railway logs for dashboard errors
- Verify `DATABASE_URL` is set correctly

---

## Step 6: Monitor Bot Activity

**Railway Dashboard → Logs**

**Watch for:**
```
WINDOW 1
Scanning Polymarket for expiring markets...
Gamma API returned X markets
Placing bets on Y markets...
```

**If bot is scanning:** ✅ Working correctly  
**If no activity:** Check `SCAN_INTERVAL_SECONDS` (default: 3600 = 1 hour)

**To speed up testing:**
- Railway Dashboard → Variables → Add: `SCAN_INTERVAL_SECONDS=300` (5 minutes)
- Change back to `3600` after testing

---

## Quick Diagnostic Commands

### Check Railway PostgreSQL

**Railway Dashboard → PostgreSQL → Data Tab:**
```sql
SELECT COUNT(*) FROM windows;
SELECT COUNT(*) FROM bets;
SELECT COUNT(*) FROM circuit_breaker_log;
```

**Expected after migration:** 33160, 23, 0

### Check Bot Status

**Railway Dashboard → Logs → Search for:**
- "Vig v1 Starting" = Bot running ✅
- "Scanning Polymarket" = Bot active ✅
- "Placing bets" = Bot working ✅
- Errors = Need to fix ❌

### Test Dashboard API

```bash
curl https://vig-production.up.railway.app/api/stats
curl https://vig-production.up.railway.app/api/bets?limit=5
curl https://vig-production.up.railway.app/api/windows?limit=5
```

**Expected:** JSON with data (not empty arrays)

---

## Troubleshooting

### PostgreSQL Still Timing Out?

**Try:**
1. Restart PostgreSQL service
2. Create fresh PostgreSQL instance
3. Use SQLite + volume instead (Option C)

### Migration Fails?

**Check:**
- `DATABASE_URL` is correct format
- PostgreSQL is accessible (test with `SELECT 1;`)
- Local SQLite file exists (`vig.db`)

**If connection times out:**
- Use SQLite + volume (Option C)
- Or try migration from Railway service itself (if possible)

### Bot Not Running?

**Check:**
- Railway logs for errors
- Environment variables set correctly
- `Procfile` or `railway.toml` startCommand correct
- Service restarted after env var changes

### Dashboard Still Empty?

**Check:**
- Database has data (run `SELECT COUNT(*) FROM windows;`)
- `DATABASE_URL` matches in both bot and dashboard
- Dashboard can connect to database (check logs)

---

## Success Criteria

✅ **PostgreSQL working** (or SQLite volume set up)  
✅ **Data migrated** (33160 windows, 23 bets in Railway database)  
✅ **Bot running** (logs show "Vig v1 Starting")  
✅ **Dashboard shows data** (window/bet counts > 0)  
✅ **Bot placing bets** (logs show "Placing bets...")  

**All checked? You're running! 🚀**

---

## After Everything Works

1. **Monitor logs** - Watch for bot activity
2. **Check dashboard** - Verify data updating
3. **Set normal scan interval** - `SCAN_INTERVAL_SECONDS=3600` (1 hour)
4. **Switch to live mode** - `PAPER_MODE=false` (if ready)
5. **Add proxy** - `RESIDENTIAL_PROXY_URL` (if live mode)

---

## Files Reference

- `migrate_to_postgres.py` - Migration script
- `Procfile` - Runs dashboard + bot
- `railway.toml` - Deployment config
- `clob_proxy.py` - Proxy support
