# Resolve Railway Template Variables

## Template You Have

```
postgresql://${{PGUSER}}:${{POSTGRES_PASSWORD}}@${{RAILWAY_TCP_PROXY_DOMAIN}}:${{RAILWAY_TCP_PROXY_PORT}}/${{PGDATABASE}}
```

## Step-by-Step: Get Each Variable Value

### In Railway Dashboard:

1. **Go to:** Railway Dashboard → **PostgreSQL** service
2. **Click:** **"Variables"** tab
3. **Find and copy these 5 values:**

   **Variable 1:** `PGUSER`
   - Value: Usually `postgres`
   - Copy: `postgres` (or whatever it shows)

   **Variable 2:** `POSTGRES_PASSWORD`  
   - Value: Long random string
   - Copy: The entire password string

   **Variable 3:** `RAILWAY_TCP_PROXY_DOMAIN`
   - Value: Something like `postgres.railway.app` or `monorail.proxy.rlwy.net`
   - Copy: The domain name

   **Variable 4:** `RAILWAY_TCP_PROXY_PORT`
   - Value: A port number like `5432` or `12345`
   - Copy: Just the number

   **Variable 5:** `PGDATABASE`
   - Value: Usually `railway` or `postgres`
   - Copy: The database name

---

## Share All 5 Values

**Format:**
```
PGUSER = postgres
POSTGRES_PASSWORD = abc123xyz...
RAILWAY_TCP_PROXY_DOMAIN = postgres.railway.app
RAILWAY_TCP_PROXY_PORT = 5432
PGDATABASE = railway
```

**Once you share these, I'll construct:**
```
postgresql://postgres:abc123xyz...@postgres.railway.app:5432/railway
```

---

## ⚠️ If TCP Proxy Variables Are Missing

If you don't see `RAILWAY_TCP_PROXY_DOMAIN` or `RAILWAY_TCP_PROXY_PORT`:

1. **PostgreSQL service** → **Settings** tab
2. **Networking** section
3. **Enable TCP Proxy** (if not enabled)
4. **Wait 1-2 minutes** for Railway to provision
5. **Check Variables tab again** - TCP Proxy variables should appear

---

## Alternative: Check Connect Tab

**PostgreSQL service** → **Connect** tab:
- Look for **"Public Network"** section
- Should show resolved connection string directly
- Copy that entire string

---

**Share the 5 variable values or the resolved connection string from Connect tab!** 🚀
