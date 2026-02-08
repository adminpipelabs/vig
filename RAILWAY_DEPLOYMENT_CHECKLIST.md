# Railway Dashboard Deployment Checklist

## ✅ Code Status
- ✅ Professional dashboard code pushed to GitHub
- ✅ Procfile configured correctly
- ✅ Railway.toml configured correctly

## Steps to Deploy/Verify on Railway

### 1. Check Railway Auto-Deployment
Railway should automatically deploy when you push to GitHub. Check:

1. Go to https://railway.app
2. Open your project
3. Click on **Dashboard** service
4. Check **Deployments** tab
5. You should see a new deployment starting (or already completed)

### 2. Verify Environment Variables
**Critical:** Make sure `DATABASE_URL` is set on the Dashboard service:

1. Go to Railway → Your Project → **Dashboard** service
2. Click **Variables** tab
3. Verify `DATABASE_URL` exists:
   ```
   postgresql://postgres:tcYZJUFgoyysWHEjAAKdBlLLPpoFCbDn@shortline.proxy.rlwy.net:23108/railway
   ```
4. If missing, click **+ New Variable** and add it

### 3. Check Service Status
1. Go to **Dashboard** service
2. Check **Metrics** tab - should show it's running
3. Check **Logs** tab - should show "Application startup complete"

### 4. Access Dashboard
1. Go to **Dashboard** service → **Settings**
2. Find **Public Domain** or generate one
3. Visit the URL - you should see the new professional dashboard

### 5. If Not Auto-Deployed
If Railway didn't auto-deploy:

1. Go to **Dashboard** service
2. Click **Settings** → **Redeploy**
3. Or trigger via GitHub: Make a small commit and push

## Expected Result

After deployment, visiting your Railway dashboard URL should show:
- ✅ Professional white theme
- ✅ Wallet address displayed (`0x989B7F...ea5A1D`)
- ✅ Portfolio summary cards
- ✅ Bot control panel
- ✅ Active positions table
- ✅ All data from your bot

## Troubleshooting

**If dashboard shows "No data":**
- Check `DATABASE_URL` is set correctly
- Check logs for connection errors
- Verify PostgreSQL service is running

**If dashboard doesn't load:**
- Check Railway logs for errors
- Verify `dashboard_professional_template.py` is in the repo
- Check Python dependencies are installed

**If you see old dark theme:**
- Clear browser cache
- Hard refresh (Ctrl+Shift+R / Cmd+Shift+R)
- Check Railway deployed the latest commit
