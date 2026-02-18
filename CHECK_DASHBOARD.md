# Dashboard Not Loading - Check This

## The Issue
The logs you showed are from the **worker service** (bot), not the **web service** (dashboard).

## What to Check in Railway

### 1. Check if Dashboard Service Exists
In Railway dashboard:
- Do you see **TWO services**?
  - One called "web" or "dashboard" 
  - One called "worker" or "vig"

If you only see ONE service, Railway might not be splitting the Procfile.

### 2. Check Dashboard Service Logs
If dashboard service exists:
- Click on the **dashboard/web service**
- Go to **Deployments** → Latest → **View Logs**
- Look for:
  - `INFO:     Uvicorn running on...`
  - `INFO:     Application startup complete.`
  - Any errors about imports or port binding

### 3. If Only One Service Exists
Railway might be running only the worker. You need to:
- Create a **separate service** for the dashboard
- OR configure Railway to run both from Procfile

### 4. Quick Fix: Create Separate Dashboard Service
1. In Railway → Your Project
2. Click **"+ New"** → **"Service"**
3. Connect to same GitHub repo
4. In **Settings** → **Start Command**: `uvicorn dashboard:app --host 0.0.0.0 --port $PORT`
5. Deploy

## Current Status from Logs
- ✅ **Worker (bot)**: Running, scanning markets every 6 seconds
- ❌ **Web (dashboard)**: Status unknown - need to check Railway

## Next Steps
1. Check Railway dashboard for dashboard/web service
2. If missing, create it with startCommand: `uvicorn dashboard:app --host 0.0.0.0 --port $PORT`
3. Check its logs to see why it's not responding
