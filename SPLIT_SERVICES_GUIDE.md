# Quick Guide: Split Bot and Dashboard into Separate Services

## 🎯 **Why Split?**

**Current Problem:**
- Both bot and dashboard run in same service
- Restarting one restarts both
- Mixed logs, resource conflicts

**Solution:**
- **Dashboard Service:** Web UI (stateless, can restart anytime)
- **Bot Service:** Trading bot (stateful, runs continuously)

---

## 📋 **Step-by-Step Setup**

### **Step 1: Create Bot Service in Railway**

1. **Railway Dashboard** → Click **"New"** → **"Empty Service"**
2. **Name:** `vig-bot`
3. **Connect GitHub:** Same repo (`adminpipelabs/vig`)
4. **Root Directory:** `/` (same as dashboard)

### **Step 2: Copy Environment Variables**

**From `vig-dashboard` service, copy these to `vig-bot`:**

```
DATABASE_URL          (shared PostgreSQL)
POLYGON_PRIVATE_KEY
RESIDENTIAL_PROXY_URL
PAPER_MODE
LOG_LEVEL
RAILWAY_TOKEN         (for bot restart API)
RAILWAY_SERVICE_ID    (bot's own service ID)
```

**How to copy:**
1. Go to `vig-dashboard` → **Variables** tab
2. Copy each variable value
3. Go to `vig-bot` → **Variables** tab
4. Add each variable

### **Step 3: Set Start Command for Bot**

**In `vig-bot` service:**
1. Go to **Settings** → **Deploy**
2. **Start Command:** `python3 main.py`
3. **OR** rename `Procfile.bot` → `Procfile` in repo

### **Step 4: Update Dashboard Service**

**In `vig-dashboard` service:**
1. Go to **Settings** → **Deploy**
2. **Start Command:** `uvicorn dashboard:app --host 0.0.0.0 --port ${PORT:-8080}`
3. **OR** rename `Procfile.dashboard` → `Procfile` in repo

### **Step 5: Update Bot Control API**

The dashboard's `/api/bot-control` endpoint needs to know the bot's service ID:

**In `vig-bot` service Variables:**
- Add: `RAILWAY_SERVICE_ID` = (bot service's ID from Railway)

**In `vig-dashboard` service Variables:**
- Update: `RAILWAY_SERVICE_ID` = (bot service's ID, not dashboard's)

**OR** update `dashboard.py` to use a different env var:
- `BOT_RAILWAY_SERVICE_ID` = bot service ID
- `RAILWAY_SERVICE_ID` = dashboard service ID (for self-restart if needed)

---

## 🔄 **After Setup**

### **Verify Dashboard:**
```bash
curl https://vig-production.up.railway.app/api/health
```

### **Check Bot Logs:**
- Railway → `vig-bot` service → **Logs**
- Should see: `=== Vig v1 Starting (LIVE mode) ===`

### **Test Independent Restart:**
1. Dashboard → Bot Control Panel → **Restart**
2. Only `vig-bot` restarts (dashboard stays up ✅)

---

## 📁 **File Changes**

I've created:
- `Procfile.dashboard` - For dashboard service
- `Procfile.bot` - For bot service

**To use them:**

**Option A: Rename in repo (recommended)**
```bash
# For dashboard service
cp Procfile.dashboard Procfile
git add Procfile
git commit -m "Split: Dashboard-only Procfile"
git push

# For bot service (after creating it)
cp Procfile.bot Procfile
git add Procfile
git commit -m "Split: Bot-only Procfile"
git push
```

**Option B: Use Railway start commands**
- Set start commands directly in Railway (no Procfile needed)

---

## ⚠️ **Important**

- **Both services share same `DATABASE_URL`** (PostgreSQL)
- **Bot writes status to database** (dashboard reads from DB)
- **Environment variables must be set in BOTH services**
- **Bot service ID** goes in dashboard's `RAILWAY_SERVICE_ID` (for restart API)

---

## ✅ **Benefits**

✅ Restart bot independently  
✅ Restart dashboard independently  
✅ Separate logs  
✅ Better resource management  
✅ Easier debugging  
✅ Can scale dashboard horizontally  
