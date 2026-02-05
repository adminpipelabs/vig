# DATABASE_URL Setup Guide

## ⚠️ Important: Internal vs Public URL

You provided: `postgresql://postgres:tcYZJUFgoyysWHEjAAKdBlLLPpoFCbDn@postgres.railway.internal:5432/railway`

**This is an INTERNAL Railway URL:**
- ✅ Works for: Dashboard service on Railway
- ❌ Won't work for: Bot running locally on your Mac

## Solution: Get Public URL

### For Railway Dashboard (Internal URL - Already Works):
1. Go to Dashboard service on Railway
2. Variables tab
3. Add: `DATABASE_URL` = `postgresql://postgres:tcYZJUFgoyysWHEjAAKdBlLLPpoFCbDn@postgres.railway.internal:5432/railway`
4. Dashboard will connect ✅

### For Local Bot (Need Public URL):

**Option 1: Get Public URL from Railway**
1. Go to PostgreSQL service on Railway
2. Click **"Connect"** tab
3. Look for **"Public Network"** section
4. Copy the **public DATABASE_URL** (different hostname, not `.internal`)
5. Format: `postgresql://postgres:password@public-hostname:5432/railway`

**Option 2: Use Railway's Public Proxy**
- Railway may provide a public proxy URL
- Check PostgreSQL service → Connect → Public Network

**Option 3: Use Railway's Connection Pooling**
- Some Railway plans include connection pooling
- Check if available in PostgreSQL service settings

## Quick Setup

### Step 1: Set Internal URL for Dashboard (Railway)
- Already have the URL ✅
- Add to Dashboard service Variables

### Step 2: Get Public URL for Bot
- Check Railway PostgreSQL → Connect → Public Network
- Or check if there's a "Public URL" in Variables

### Step 3: Add Public URL to Local .env
```bash
DATABASE_URL=postgresql://postgres:password@public-host:5432/railway
```

## Alternative: Keep Bot on Railway

If you can't get public URL, you could:
- Run bot on Railway too (but Cloudflare will block CLOB API)
- Use Railway's internal networking
- But bot needs residential IP for CLOB API...

**Best solution:** Get public DATABASE_URL from Railway PostgreSQL service!
