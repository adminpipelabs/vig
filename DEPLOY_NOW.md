# 🚀 Deploy to Railway NOW

## Problem
**Nothing is deployed because code hasn't been pushed to GitHub yet.**

Railway deploys from GitHub, but we can't push due to git authentication.

## Solution: Push Manually

### Quick Push Options

**Option 1: GitHub Desktop** (Easiest)
1. Open GitHub Desktop
2. Open `/Users/mikaelo/vig` repository
3. Click "Push origin" button
4. ✅ Done!

**Option 2: Terminal with Token**
```bash
cd /Users/mikaelo/vig

# Get token from: https://github.com/settings/tokens
# Create token with "repo" permissions

git remote set-url origin https://YOUR_TOKEN@github.com/adminpipelabs/vig.git
git push origin main
```

**Option 3: SSH Key** (If you have one)
```bash
cd /Users/mikaelo/vig
git remote set-url origin git@github.com:adminpipelabs/vig.git
git push origin main
```

**Option 4: GitHub CLI**
```bash
cd /Users/mikaelo/vig
gh auth login
git push origin main
```

## After Push: Railway Auto-Deploys

1. ✅ Railway detects new commit on GitHub
2. ✅ Builds Docker image
3. ✅ Deploys both services (web + worker)
4. ✅ Shows logs in dashboard

## What's Ready to Deploy

**5 commits:**
- ✅ Polymarket US API migration
- ✅ Auth module (Ed25519)
- ✅ Orders module
- ✅ Position tracking
- ✅ Sell-before-expiry logic
- ✅ Dockerfile + Procfile
- ✅ Railway config

**New files:**
- `auth.py` - Ed25519 authentication
- `orders.py` - US API order functions
- `positions.py` - Position tracking
- `bet_manager_us.py` - US API bet manager
- `railway.json` - Railway config
- `Procfile` - Service definitions
- Updated `main.py`, `config.py`, `Dockerfile`

## Next Steps After Push

1. **Check Railway Dashboard**
   - Go to https://railway.app
   - Find your `vig` project
   - Watch deployment logs

2. **Set Environment Variables**
   ```
   USE_US_API=true
   POLYMARKET_US_KEY_ID=...
   POLYMARKET_US_PRIVATE_KEY=...
   DATABASE_URL=... (from Railway PostgreSQL)
   PAPER_MODE=false
   ```

3. **Verify Deployment**
   - Check bot logs for "✅ Polymarket US API initialized"
   - Check dashboard URL works
   - Monitor first few cycles

## Current Status

```
Local:  ✅ 5 commits ready
GitHub: ❌ Not pushed (blocked by auth)
Railway: ❌ Waiting for GitHub push
```

**Action Required:** Push to GitHub manually using one of the options above.
