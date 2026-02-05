# Enable Railway PostgreSQL TCP Proxy for Public Access

## 🎯 Goal
Enable public access to PostgreSQL so your local bot can connect.

---

## ✅ Step 1: Enable TCP Proxy

1. **Go to Railway Dashboard:** https://railway.app/dashboard
2. **Click on PostgreSQL service** (the database, not your dashboard service)
3. **Click "Settings" tab** (top menu)
4. **Scroll to "Networking" section**
5. **Find "TCP Proxy"** or **"Public Network"**
6. **Enable TCP Proxy** (toggle switch or button)
   - **Port:** `5432` (PostgreSQL default)
   - **Click "Enable"** or **"Add TCP Proxy"**

---

## ✅ Step 2: Redeploy PostgreSQL (IMPORTANT!)

**After enabling TCP Proxy:**
1. **PostgreSQL service** → **Deployments** tab
2. **Click "Redeploy"** (or Railway may auto-redeploy)
3. **Wait 1-2 minutes** for deployment

**⚠️ Important:** TCP Proxy variables won't appear until you redeploy!

---

## ✅ Step 3: Get Public Connection String

**After redeployment:**

### Option A: Variables Tab (Recommended)

1. **PostgreSQL service** → **Variables** tab
2. **Look for these NEW variables:**
   - `RAILWAY_TCP_PROXY_DOMAIN` (e.g., `roundhouse.proxy.rlwy.net`)
   - `RAILWAY_TCP_PROXY_PORT` (e.g., `11105`)
   - `PGUSER` (usually `postgres`)
   - `POSTGRES_PASSWORD` (long string)
   - `PGDATABASE` (usually `railway`)

3. **Copy all 5 values** and share them here

### Option B: Connect Tab

1. **PostgreSQL service** → **Connect** tab
2. **Look for "Public Network"** section
3. **Copy the connection string** shown there
4. **Share it here**

---

## 🔧 Constructing the URL

**Once you have the 5 values, the URL format is:**
```
postgresql://PGUSER:POSTGRES_PASSWORD@RAILWAY_TCP_PROXY_DOMAIN:RAILWAY_TCP_PROXY_PORT/PGDATABASE
```

**Example:**
```
postgresql://postgres:abc123xyz@roundhouse.proxy.rlwy.net:11105/railway
```

---

## 📋 Checklist

- [ ] Enabled TCP Proxy in PostgreSQL Settings → Networking
- [ ] Redeployed PostgreSQL service
- [ ] Found `RAILWAY_TCP_PROXY_DOMAIN` in Variables tab
- [ ] Found `RAILWAY_TCP_PROXY_PORT` in Variables tab
- [ ] Copied all 5 variable values OR public connection string
- [ ] Shared values here

---

## 🚀 Next Steps

**Once you share the public connection string or the 5 variable values, I'll:**
1. ✅ Update `.env` file
2. ✅ Run migration script
3. ✅ Start the bot

**Let me know what you find after enabling TCP Proxy!** 🚀
