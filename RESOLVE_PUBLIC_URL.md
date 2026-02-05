# Resolve Railway Public DATABASE_URL

## Template You Provided

```
postgresql://${{PGUSER}}:${{POSTGRES_PASSWORD}}@${{RAILWAY_TCP_PROXY_DOMAIN}}:${{RAILWAY_TCP_PROXY_PORT}}/${{PGDATABASE}}
```

## What We Need

This is a **template** - Railway resolves these variables. We need the **actual resolved values**:

1. `${{PGUSER}}` → Usually `postgres`
2. `${{POSTGRES_PASSWORD}}` → The actual password
3. `${{RAILWAY_TCP_PROXY_DOMAIN}}` → Public domain (like `postgres.railway.app`)
4. `${{RAILWAY_TCP_PROXY_PORT}}` → Port number
5. `${{PGDATABASE}}` → Database name (usually `railway`)

## How to Get Resolved Values

### Option 1: Railway Dashboard (Easiest)

1. **Go to Railway Dashboard** → PostgreSQL service
2. **Click "Connect" tab**
3. **Look for "Public Network"** section
4. **Copy the FULL connection string** (already resolved)

**OR**

1. **PostgreSQL service** → **Variables tab**
2. **Look for `DATABASE_PUBLIC_URL`** - this should be the resolved public URL
3. **Copy that value**

### Option 2: Railway CLI

```bash
railway connect postgres --print
```

This should print the resolved connection string.

### Option 3: Manual Construction

If you can see the individual variables in Railway:
- Copy each value
- Construct: `postgresql://USER:PASSWORD@DOMAIN:PORT/DATABASE`

## Expected Format

```
postgresql://postgres:ABC123xyz@postgres.railway.app:5432/railway
```

**NOT:**
```
postgresql://${{PGUSER}}:${{POSTGRES_PASSWORD}}@...  ❌ (template)
postgresql://postgres:password@postgres.railway.internal:5432/railway  ❌ (internal)
```

## Next Steps

**Once you have the resolved public URL, share it and I'll:**
1. ✅ Update `.env` file
2. ✅ Run migration
3. ✅ Start bot
