# CTO Deployment Instructions - Railway

## Current Status
- **Platform**: Railway only (Hetzner cancelled)
- **Issue**: Dashboard page not loading - likely build/deployment error
- **Action Required**: Check Railway deployment logs

## Why Railway Only
- ✅ Dashboard already on Railway
- ✅ Database already on Railway  
- ✅ US API is different endpoint — may not have Cloudflare issues
- ✅ One place, one bill

## Deployment Steps

### 1. Check Railway Deployment Logs
**First priority** - The "Application failed to respond" error is likely a build/deployment issue.

In Railway dashboard:
1. Go to your project → Deployments
2. Click on the latest deployment
3. Check **Build Logs** for errors
4. Check **Deploy Logs** for runtime errors

**Common issues to look for:**
- Missing dependencies (`fastapi`, `uvicorn`)
- Port binding errors
- Database connection failures
- Import errors

### 2. Deploy New Code (US API)
The code is already pushed to GitHub. Railway should auto-deploy, but verify:

1. **Verify latest commit is deployed:**
   - Check Railway → Deployments → Latest commit hash
   - Should match GitHub `main` branch

2. **If not auto-deployed, trigger manual deploy:**
   - Railway → Deployments → "Redeploy"

### 3. Verify Configuration

**Railway Environment Variables:**
- `DATABASE_URL` - PostgreSQL connection string (should be set)
- `PORT` - Automatically set by Railway (don't override)
- `POLYMARKET_US_KEY_ID` - If using US API
- `POLYMARKET_US_PRIVATE_KEY` - If using US API
- `POLYGON_PRIVATE_KEY` - If using legacy API

**Railway Configuration Files:**
- `railway.json` - Sets `startCommand: "uvicorn dashboard:app --host 0.0.0.0 --port $PORT"`
- `Procfile` - Defines `web` and `worker` services
- `Dockerfile` - Builds the application
- `requirements.txt` - Python dependencies (includes `fastapi` and `uvicorn`)

### 4. Test US API from Railway

**If US API keys are configured:**
1. Check Railway logs for bot startup
2. Verify bot connects to `api.polymarket.us` (not CLOB API)
3. Check if Cloudflare blocks occur

**If US API works → Done!**
**If US API blocked → Then consider Hetzner migration**

### 5. Verify Dashboard is Running

**Check these endpoints:**
- `https://vig-production.up.railway.app/api/health` - Should return JSON
- `https://vig-production.up.railway.app/` - Should show dashboard
- `https://vig-production.up.railway.app/terminal` - Should show trading terminal

**Expected health response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "bets_count": 0,
  "windows_count": 0
}
```

## Troubleshooting

### Dashboard Not Loading
1. **Check build logs** - Look for Python import errors
2. **Check deploy logs** - Look for uvicorn startup errors
3. **Verify startCommand** - Should be: `uvicorn dashboard:app --host 0.0.0.0 --port $PORT`
4. **Check dependencies** - Ensure `fastapi` and `uvicorn` are in `requirements.txt`

### Database Connection Issues
- Verify `DATABASE_URL` is set correctly
- Check if PostgreSQL service is running in Railway
- Verify connection string format: `postgresql://user:pass@host:port/dbname`

### Port Binding Issues
- Railway sets `$PORT` automatically
- Don't hardcode port numbers
- Use `--port $PORT` in startCommand

## Quick Commands

**Check Railway logs:**
```bash
# Via Railway CLI (if installed)
railway logs

# Or check in Railway web dashboard
```

**Test locally (to verify code works):**
```bash
cd /path/to/vig
python3 test_dashboard.py
PORT=8080 uvicorn dashboard:app --host 0.0.0.0 --port 8080
```

## Next Steps After Fix

1. ✅ Dashboard loads successfully
2. ✅ Bot starts and connects to US API
3. ✅ No Cloudflare blocks
4. ✅ Trading terminal shows live data

If US API still blocked by Cloudflare → Then we migrate to Hetzner.

---

**Last Updated**: After fixing Railway deployment configuration
**Status**: Waiting for CTO to check Railway logs and deploy
