# Architecture: Split Bot and Dashboard into Separate Services

## 🎯 **Problem**

Currently, both the bot (`main.py`) and dashboard (`dashboard.py`) run in the same Railway service:

```
Procfile: web: uvicorn dashboard:app & python3 main.py & wait
```

**Issues:**
1. ❌ Restarting bot restarts dashboard (dashboard goes down)
2. ❌ Restarting dashboard restarts bot (bot loses state)
3. ❌ Can't scale independently
4. ❌ Resource conflicts (memory, CPU, database connections)
5. ❌ Harder to debug (logs mixed together)
6. ❌ Health checks affect both processes

---

## ✅ **Solution: Two Separate Railway Services**

### **Service 1: `vig-dashboard`** (Web UI)
- **Purpose:** FastAPI dashboard for monitoring
- **Start Command:** `uvicorn dashboard:app --host 0.0.0.0 --port ${PORT:-8080}`
- **Type:** Web service (stateless)
- **Restart Policy:** Can restart anytime (no state)
- **Health Check:** `/api/health`

### **Service 2: `vig-bot`** (Trading Bot)
- **Purpose:** Long-running trading bot loop
- **Start Command:** `python3 main.py`
- **Type:** Worker service (stateful)
- **Restart Policy:** Only restart on failure
- **Health Check:** None (or check bot status file)

---

## 📋 **Migration Steps**

### **Step 1: Create New Bot Service**

1. **In Railway Dashboard:**
   - Click **"New"** → **"Empty Service"**
   - Name it: `vig-bot`
   - Connect to same GitHub repo (`adminpipelabs/vig`)
   - Same root directory

2. **Set Environment Variables:**
   - Copy ALL env vars from `vig-dashboard` service:
     - `DATABASE_URL` (shared PostgreSQL)
     - `POLYGON_PRIVATE_KEY`
     - `RESIDENTIAL_PROXY_URL`
     - `PAPER_MODE`
     - `LOG_LEVEL`
     - etc.

3. **Set Start Command:**
   - Go to **Settings** → **Deploy**
   - Set **Start Command:** `python3 main.py`
   - (Or create `Procfile` with: `worker: python3 main.py`)

### **Step 2: Update Dashboard Service**

1. **Update Start Command:**
   - Go to `vig-dashboard` service → **Settings** → **Deploy**
   - Set **Start Command:** `uvicorn dashboard:app --host 0.0.0.0 --port ${PORT:-8080}`
   - (Or update `Procfile` to: `web: uvicorn dashboard:app --host 0.0.0.0 --port ${PORT:-8080}`)

2. **Remove Bot from Dashboard:**
   - Dashboard no longer runs `main.py`
   - Only serves FastAPI endpoints

### **Step 3: Update Bot Control (Optional)**

The `/api/bot-control` endpoint in dashboard can still restart the bot service via Railway API, but now it restarts ONLY the bot service, not the dashboard.

---

## 🎯 **Benefits**

✅ **Independent Restarts:**
- Restart bot without affecting dashboard
- Restart dashboard without affecting bot

✅ **Better Resource Management:**
- Dashboard: Small memory footprint (just FastAPI)
- Bot: Can use more resources for trading logic

✅ **Easier Debugging:**
- Separate logs for bot vs dashboard
- Clear separation of concerns

✅ **Scalability:**
- Can scale dashboard horizontally (multiple instances)
- Bot runs as single instance (stateful)

✅ **Health Checks:**
- Dashboard health check doesn't affect bot
- Bot failures don't take down dashboard

---

## 📁 **File Changes Needed**

### **1. Create `Procfile` for Bot Service:**
```procfile
worker: python3 main.py
```

### **2. Update `Procfile` for Dashboard Service:**
```procfile
web: uvicorn dashboard:app --host 0.0.0.0 --port ${PORT:-8080}
```

### **3. Update `railway.toml` (if used):**
```toml
[build]
builder = "nixpacks"
buildCommand = "pip install -r requirements.txt"

[deploy]
# Dashboard service
startCommand = "uvicorn dashboard:app --host 0.0.0.0 --port ${PORT:-8080}"
healthcheckPath = "/api/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

**Note:** Railway will use `Procfile` if it exists, otherwise `railway.toml`.

---

## 🔄 **After Migration**

1. **Verify Dashboard:**
   ```bash
   curl https://vig-production.up.railway.app/api/health
   ```

2. **Check Bot Logs:**
   - Railway Dashboard → `vig-bot` service → Logs
   - Should see: `=== Vig v1 Starting (LIVE mode) ===`

3. **Test Bot Restart:**
   - Dashboard → Bot Control Panel → Restart
   - Only `vig-bot` service restarts (dashboard stays up)

---

## ⚠️ **Important Notes**

- **Shared Database:** Both services use same `DATABASE_URL` (PostgreSQL)
- **Bot Status File:** Bot writes `/tmp/vig_bot_status.json` (ephemeral)
- **Dashboard Reads:** Dashboard reads bot status from database (more reliable)
- **Environment Variables:** Must be set in BOTH services

---

## 🚀 **Quick Start**

1. Create `vig-bot` service in Railway
2. Copy env vars from dashboard service
3. Set start command: `python3 main.py`
4. Update dashboard service start command (remove `main.py`)
5. Deploy both services
6. Verify both are running independently
