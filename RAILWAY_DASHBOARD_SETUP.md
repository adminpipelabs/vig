# Railway Dashboard Setup - Do This Now

## Step 1: Set DATABASE_URL on Railway

**Right now, while migration runs:**

1. **Go to Railway Dashboard:** https://railway.app/dashboard
2. **Click on your Dashboard service** (the one running FastAPI/dashboard.py)
3. **Click "Variables" tab**
4. **Click "New Variable"** (or find existing `DATABASE_URL` and edit)
5. **Set:**
   - **Name:** `DATABASE_URL`
   - **Value:** `postgresql://postgres:tcYZJUFgoyysWHEjAAKdBlLLPpoFCbDn@postgres.railway.internal:5432/railway`
6. **Save**

**Important:** 
- Use `postgres.railway.internal` (internal URL for Railway services)
- NOT the public URL (`shortline.proxy.rlwy.net`)
- Railway will auto-redeploy after you save

## Step 2: Verify Dashboard Requirements

**Check if dashboard service has:**
- [ ] `psycopg2-binary` in requirements.txt or installed
- [ ] Port 8000 exposed (or whatever port dashboard uses)
- [ ] Service is running/deployed

## Step 3: Test Dashboard After Redeploy

**After Railway redeploys (1-2 minutes):**
1. Visit: https://vig-production.up.railway.app/
2. Check if it shows data (might still show "No data" until migration completes)
3. Check Railway logs for any connection errors

## Why This Matters

- Dashboard needs `DATABASE_URL` to connect to PostgreSQL
- Once migration completes, dashboard will immediately show data
- If we wait until after migration, we'll have to wait another 1-2 minutes for Railway redeploy

**Do this now so dashboard is ready when migration finishes!** ✅
