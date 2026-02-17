# Railway Fix - Action Required

## The Problem
Railway might not be reading `startCommand` from `railway.json` automatically. You need to **manually set it in Railway dashboard**.

## Immediate Fix (Do This Now)

### Step 1: Go to Railway Dashboard
1. Open https://railway.app
2. Go to your project → **vig-production** (or your service name)
3. Click on the **service** (not the project)

### Step 2: Set Start Command Manually
1. Click **Settings** tab
2. Scroll to **"Start Command"** section
3. **Set it to exactly this:**
   ```
   uvicorn dashboard:app --host 0.0.0.0 --port $PORT
   ```
4. Click **Save**

### Step 3: Redeploy
1. Go to **Deployments** tab
2. Click **"Redeploy"** on the latest deployment
3. Wait for build to complete

### Step 4: Check Logs
1. Go to **Deployments** → Latest deployment
2. Click **"View Logs"**
3. Look for:
   - ✅ `INFO:     Uvicorn running on http://0.0.0.0:XXXX`
   - ✅ `INFO:     Application startup complete.`
   - ❌ Any errors about missing modules or port binding

## Why This Happens

Railway's precedence:
1. **Service Settings** (dashboard UI) - **HIGHEST PRIORITY**
2. Dockerfile CMD - Used if no service setting
3. railway.json startCommand - **Might not be read automatically**

So even though `railway.json` has the correct command, Railway might be using the Dockerfile CMD instead.

## Verify It's Fixed

After setting startCommand and redeploying:

1. **Check dashboard loads:**
   - https://vig-production.up.railway.app/
   - Should show dashboard HTML (not 502 error)

2. **Check health endpoint:**
   - https://vig-production.up.railway.app/api/health
   - Should return: `{"status":"healthy",...}` or `{"status":"unhealthy","error":"no such table: bets"}` (latter is OK - just means DB tables need init)

3. **Check terminal:**
   - https://vig-production.up.railway.app/terminal
   - Should show trading terminal UI

## If Still Not Working

Check deployment logs for:
- `ModuleNotFoundError` → Dependencies not installed
- `Address already in use` → Port conflict
- `Cannot import 'dashboard'` → Module path issue
- `Application startup failed` → Check full error message

---

**TL;DR: Set startCommand manually in Railway dashboard → Redeploy → Check logs**
