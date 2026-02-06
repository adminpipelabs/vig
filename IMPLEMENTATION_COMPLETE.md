# Implementation Complete: Service Split Architecture

**Date:** 2026-02-05  
**Status:** ✅ Ready for Railway setup

---

## ✅ **What Was Implemented**

### **1. Database Heartbeat System**
- ✅ Added `bot_status` table to database schema (`db.py`)
- ✅ Bot writes heartbeat every scan cycle (`main.py`)
- ✅ Dashboard reads status from database (`dashboard.py`)
- ✅ Status includes: `running`, `scanning`, `idle`, `error`, `stopped`, `offline`

### **2. Split Services Support**
- ✅ Updated `Procfile` to support both `web` and `worker` targets
- ✅ Dashboard uses `BOT_SERVICE_ID` to restart bot service (not itself)
- ✅ Bot restart API works for split services

### **3. Code Changes**

**Files Modified:**
- `db.py` - Added `bot_status` table and heartbeat methods
- `main.py` - Replaced file-based status with database heartbeat
- `dashboard.py` - Reads bot status from database, uses `BOT_SERVICE_ID`
- `Procfile` - Split into `web` and `worker` targets

---

## 📋 **Next Steps: Railway Setup**

### **Step 1: Create Bot Service**

1. **Railway Dashboard** → **New** → **Empty Service**
2. **Name:** `vig-bot`
3. **Connect:** Same GitHub repo (`adminpipelabs/vig`)
4. **Start Command:** `python3 main.py` (or Railway will use `worker` from Procfile)

### **Step 2: Copy Environment Variables**

**From `vig-dashboard` service, copy to `vig-bot`:**

```
DATABASE_URL          (shared PostgreSQL - use "Add Reference")
POLYGON_PRIVATE_KEY
RESIDENTIAL_PROXY_URL
PAPER_MODE
LOG_LEVEL
```

**Service-Specific:**
- `vig-dashboard`: `RAILWAY_TOKEN`, `BOT_SERVICE_ID` (bot's service ID)
- `vig-bot`: No Railway API vars needed

### **Step 3: Update Dashboard Service**

**In `vig-dashboard` service:**
1. **Settings** → **Deploy**
2. **Start Command:** `uvicorn dashboard:app --host 0.0.0.0 --port ${PORT:-8080}`
   - OR Railway will auto-use `web` from Procfile

### **Step 4: Set Bot Service ID**

**In `vig-dashboard` service Variables:**
1. Get bot service ID from Railway (`vig-bot` → Settings)
2. Add: `BOT_SERVICE_ID` = `<bot-service-id>`
3. Add: `RAILWAY_TOKEN` = `<project-scoped-token>`

### **Step 5: Verify**

1. **Check Dashboard:** `https://vig-production.up.railway.app/api/health`
2. **Check Bot Logs:** Railway → `vig-bot` → Logs
3. **Check Bot Status:** Dashboard → Bot Control Panel → Should show "running" with heartbeat

---

## 🎯 **How It Works Now**

### **Bot Service (`vig-bot`):**
- Runs `python3 main.py` continuously
- Writes heartbeat to `bot_status` table every scan cycle
- Status: `scanning`, `idle`, `error`, `stopped`

### **Dashboard Service (`vig-dashboard`):**
- Runs FastAPI web server
- Reads bot status from `bot_status` table
- Can restart bot service via Railway API (using `BOT_SERVICE_ID`)

### **Shared Database:**
- Both services connect to same PostgreSQL
- Bot writes heartbeat → Dashboard reads it
- No file-based status needed

---

## ✅ **Benefits**

✅ **Independent Restarts:** Restart bot without affecting dashboard  
✅ **Better Monitoring:** Database heartbeat more reliable than files  
✅ **Cleaner Logs:** Separate logs per service  
✅ **Scalability:** Can scale dashboard horizontally  
✅ **Resilience:** Bot crash doesn't take down dashboard  

---

## 📝 **Environment Variables Summary**

### **Shared (Both Services):**
```
DATABASE_URL          (PostgreSQL connection)
POLYGON_PRIVATE_KEY   (Wallet private key)
RESIDENTIAL_PROXY_URL (Proxy for CLOB API)
PAPER_MODE            (true/false)
LOG_LEVEL             (DEBUG/INFO/WARNING)
```

### **Dashboard Only:**
```
RAILWAY_TOKEN         (Project-scoped token)
BOT_SERVICE_ID        (Bot service ID for restart API)
```

### **Bot Only:**
```
(None - bot doesn't call Railway API)
```

---

## 🚀 **Ready to Deploy**

All code changes are complete and pushed to GitHub. Follow the steps above to set up the split services in Railway.

**Questions?** Check `SPLIT_SERVICES_GUIDE.md` for detailed instructions.
