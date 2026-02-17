# Railway Deployment Setup

## Current Status

✅ Code is ready (4 commits waiting to push)  
❌ Not pushed to GitHub yet  
❌ Railway not connected/deployed  

## Step-by-Step Setup

### 1. Push Code to GitHub

**You need to push manually** (git auth required):

```bash
cd /Users/mikaelo/vig

# Option A: Use GitHub CLI
gh auth login
git push origin main

# Option B: Use personal access token
# Get token from: https://github.com/settings/tokens
git remote set-url origin https://YOUR_TOKEN@github.com/adminpipelabs/vig.git
git push origin main

# Option C: Use GitHub Desktop or IDE git push
```

### 2. Connect Railway to GitHub

1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose `adminpipelabs/vig` repository
5. Railway will auto-detect:
   - Dockerfile (for building)
   - Procfile (for services)

### 3. Configure Railway Services

Railway will create 2 services from Procfile:

**Service 1: Web (Dashboard)**
- Command: `python3 dashboard.py`
- Port: 8080 (auto-assigned)
- Public URL: Auto-generated

**Service 2: Worker (Bot)**
- Command: `python3 main.py`
- No public URL needed

### 4. Set Environment Variables

In Railway dashboard, go to each service → Variables tab:

**For Worker (Bot) Service:**
```
USE_US_API=true
POLYMARKET_US_KEY_ID=your-key-id-uuid
POLYMARKET_US_PRIVATE_KEY=your-ed25519-private-key
DATABASE_URL=postgresql://... (Railway PostgreSQL)
PAPER_MODE=false
PROFIT_TARGET_PCT=0.15
FORCE_EXIT_MINUTES=10
POLL_INTERVAL_SECONDS=5
MAX_BETS_PER_WINDOW=500
LOG_LEVEL=INFO
```

**For Web (Dashboard) Service:**
```
DATABASE_URL=postgresql://... (same as bot)
DB_PATH=vig.db
```

### 5. Add PostgreSQL Database

1. In Railway project → "New" → "Database" → "Add PostgreSQL"
2. Railway will auto-create `DATABASE_URL` variable
3. Copy this URL to both services

### 6. Deploy

Railway will automatically:
1. Build Docker image from Dockerfile
2. Install dependencies (cryptography, httpx, etc.)
3. Run both services
4. Show logs in dashboard

## Verify Deployment

### Check Bot Logs
Railway dashboard → Worker service → Logs tab

Look for:
```
=== Vig v2 Agent Starting (LIVE mode) ===
✅ Polymarket US API initialized
[SCAN] Found X market candidates
✅ Order placed: ...
```

### Check Dashboard
Railway dashboard → Web service → Settings → Generate Domain

Visit the URL and check:
- `/api/health` - Should return `{"status": "healthy"}`
- `/api/bot-status` - Should show bot status
- Dashboard UI should load

## Troubleshooting

### Build Fails
- Check Dockerfile syntax
- Verify Python version (3.12)
- Check requirements.txt format

### Bot Not Starting
- Check environment variables are set
- Verify `POLYMARKET_US_KEY_ID` and `POLYMARKET_US_PRIVATE_KEY` are correct
- Check logs for auth errors

### Database Connection Fails
- Verify `DATABASE_URL` is set in both services
- Check PostgreSQL is running
- Verify connection string format

### No Logs Appearing
- Check service is running (not crashed)
- Verify `LOG_LEVEL=INFO` is set
- Check Railway logs tab

## Quick Commands

**View logs:**
```bash
railway logs --service worker
railway logs --service web
```

**Redeploy:**
- Push new commit to GitHub
- Railway auto-redeploys
- Or click "Redeploy" in Railway dashboard

**Check status:**
```bash
railway status
```

## Next Steps After Deployment

1. ✅ Monitor bot logs for first few cycles
2. ✅ Check dashboard shows data
3. ✅ Verify orders are being placed
4. ✅ Monitor position tracking
5. ✅ Check force-exit before expiry works
