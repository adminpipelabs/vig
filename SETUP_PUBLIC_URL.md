# Setup Public DATABASE_URL

## What We Need

Railway provides **two** connection URLs:

1. **`DATABASE_URL`** - Internal (`.railway.internal`) - For Railway services ✅
2. **`DATABASE_PUBLIC_URL`** - Public (`.railway.app`) - For local bot ⚠️ Need this!

## How to Get DATABASE_PUBLIC_URL

### On Railway Dashboard:

1. Go to **PostgreSQL service**
2. Click **"Variables"** tab
3. Look for **`DATABASE_PUBLIC_URL`** variable
4. Copy that value

**OR**

1. Go to **PostgreSQL service**
2. Click **"Connect"** tab
3. Look for **"Public Network"** or **"External Connection"**
4. Copy the connection string

### Format Should Be:

```
postgresql://postgres:password@postgres.railway.app:PORT/railway
```

**NOT:**
```
postgresql://postgres:password@postgres.railway.internal:5432/railway  ❌
```

## Once You Have DATABASE_PUBLIC_URL:

**Share it here and I'll:**
1. ✅ Update `.env` file with public URL
2. ✅ Run migration
3. ✅ Start bot

**The internal URL (`postgres.railway.internal`) is already set for Railway dashboard - that's correct!**

## Current Status

- ✅ Railway Dashboard: Will use internal URL (already set)
- ⚠️ Local Bot: Needs public URL (need to get from Railway)

**Get the `DATABASE_PUBLIC_URL` from Railway and share it!** 🚀
