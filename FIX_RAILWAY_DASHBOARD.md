# Fix Railway Dashboard - "No data" Issue

## Problem

Railway dashboard shows "No data" because:
1. Migration might not be complete (0 bets, 0 windows)
2. Railway dashboard doesn't have `DATABASE_URL` set
3. Railway dashboard is using wrong URL (needs internal URL, not public)

## Solution

### Step 1: Set DATABASE_URL on Railway Dashboard

1. **Go to Railway Dashboard** → Your dashboard service (the one running FastAPI)
2. **Click "Variables" tab**
3. **Add/Update `DATABASE_URL`**:
   ```
   DATABASE_URL=postgresql://postgres:tcYZJUFgoyysWHEjAAKdBlLLPpoFCbDn@postgres.railway.internal:5432/railway
   ```
   **Important:** Use `postgres.railway.internal` (internal URL) for Railway services, NOT the public URL!

4. **Save** - Railway will auto-redeploy

### Step 2: Verify Migration Completed

**Check migration status:**
```bash
cd /Users/mikaelo/vig
python3.11 -c "from db import Database; import os; from dotenv import load_dotenv; load_dotenv(); db = Database(database_url=os.getenv('DATABASE_URL')); cur = db.conn.cursor(); cur.execute('SELECT COUNT(*) FROM bets'); print(f'Bets: {cur.fetchone()[0]}'); cur.execute('SELECT COUNT(*) FROM windows'); print(f'Windows: {cur.fetchone()[0]}')"
```

**Expected:** 23 bets, 33,160 windows

**If migration not complete:**
- Run: `python3.11 migrate_to_postgres.py`
- Wait for it to finish (33,160 windows takes a few minutes)

### Step 3: Verify Dashboard Connection

**After Railway redeploys:**
1. Visit: https://vig-production.up.railway.app/
2. Check if data appears
3. If still "No data", check Railway logs for connection errors

## Quick Checklist

- [ ] Railway dashboard service has `DATABASE_URL` variable set
- [ ] `DATABASE_URL` uses `postgres.railway.internal` (internal URL)
- [ ] Migration completed (23 bets, 33,160 windows in PostgreSQL)
- [ ] Railway dashboard redeployed after setting `DATABASE_URL`
- [ ] Dashboard shows data (not "No data")

## URLs

**For Local Bot:**
- Use: `postgresql://postgres:...@shortline.proxy.rlwy.net:23108/railway` (public URL)

**For Railway Dashboard:**
- Use: `postgresql://postgres:...@postgres.railway.internal:5432/railway` (internal URL)

Both connect to the same database! ✅
