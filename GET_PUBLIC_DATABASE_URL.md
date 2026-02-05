# Get Public DATABASE_URL for Local Bot

## Issue

The `DATABASE_URL` you provided uses `postgres.railway.internal` which is an **internal Railway hostname**. This only works for services **inside Railway**.

For your **local bot** to connect, we need the **public URL**.

## How to Get Public DATABASE_URL

### Option 1: Railway UI (Easiest)

1. Go to Railway → PostgreSQL service
2. Click **"Connect"** or **"Public Network"** tab
3. Look for **"Public Connection String"** or **"External Connection"**
4. Copy that URL (should have a public hostname, not `.railway.internal`)

### Option 2: Railway CLI

```bash
railway connect postgres
```

### Option 3: Check Variables Tab

1. PostgreSQL service → Variables tab
2. Look for `DATABASE_URL` or `POSTGRES_URL`
3. There might be two versions:
   - Internal: `postgres.railway.internal` (for Railway services)
   - Public: `postgres.railway.app` or similar (for external connections)

## What We Need

**Public DATABASE_URL format:**
```
postgresql://postgres:password@postgres.railway.app:5432/railway
```

**NOT:**
```
postgresql://postgres:password@postgres.railway.internal:5432/railway  ❌
```

## Current Setup

**For Railway Dashboard:**
- ✅ Use `postgres.railway.internal` (works inside Railway)
- Set `DATABASE_URL` on Dashboard service Variables tab

**For Local Bot:**
- ⚠️ Need public URL (with `.railway.app` or public IP)
- Add to local `.env` file

## Next Steps

1. **Get public DATABASE_URL** from Railway
2. **Share it here** and I'll:
   - Update `.env` file
   - Run migration
   - Start bot

**Or if you can't find public URL:**
- We can use Railway's public network feature
- Or set up Railway VPN/tunnel
- Or keep bot on Railway (but needs residential IP workaround)
