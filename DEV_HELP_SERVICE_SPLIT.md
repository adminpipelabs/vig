# Dev Help: Should We Split Bot and Dashboard into Separate Services?

**Date:** 2026-02-05  
**Context:** User noticed bot stopped working after restart attempts, questioning if bot should be on separate instance/server.

---

## 🎯 **Current Situation**

### **Current Architecture:**
- **Single Railway Service:** Both `main.py` (bot) and `dashboard.py` (FastAPI) run together
- **Start Command:** `uvicorn dashboard:app & python3 main.py & wait`
- **Shared:** Same container, same resources, same restart cycle

### **Problems Observed:**
1. ❌ Restarting bot restarts dashboard (dashboard goes down)
2. ❌ Restarting dashboard restarts bot (bot loses state)
3. ❌ Mixed logs (harder to debug)
4. ❌ Resource conflicts (memory, CPU, database connections)
5. ❌ Health checks affect both processes
6. ❌ User reports: "it kind of worked in localhost and then worked in production on railway then it stopped when tried to restart the bot"

---

## 💡 **Proposed Solution**

### **Split into Two Railway Services:**

**Service 1: `vig-dashboard`** (Web UI)
- **Type:** Web service (stateless)
- **Start:** `uvicorn dashboard:app --host 0.0.0.0 --port ${PORT:-8080}`
- **Restart Policy:** Can restart anytime (no state)
- **Health Check:** `/api/health`

**Service 2: `vig-bot`** (Trading Bot)
- **Type:** Worker service (stateful)
- **Start:** `python3 main.py`
- **Restart Policy:** Only restart on failure
- **Health Check:** None (or check bot status file)

### **Benefits:**
✅ Independent restarts (restart bot without affecting dashboard)  
✅ Better resource management (dashboard small footprint, bot can use more)  
✅ Separate logs (easier debugging)  
✅ Scalability (can scale dashboard horizontally)  
✅ Health checks don't interfere with each other  

### **Shared Resources:**
- ✅ Same `DATABASE_URL` (PostgreSQL) - both services connect to same DB
- ✅ Bot writes status to database (dashboard reads from DB)
- ✅ Environment variables must be set in BOTH services

---

## 🤔 **Questions for Dev**

### **1. Architecture Decision:**
**Should we split the services, or is there a better approach?**

**Option A: Split Services (Proposed)**
- Pros: Independent restarts, better separation, easier debugging
- Cons: More services to manage, duplicate env vars

**Option B: Keep Together, Fix Restart Logic**
- Pros: Simpler deployment, single service
- Cons: Still have restart coupling issues

**Option C: Use Railway Workers**
- Pros: Railway-native worker pattern
- Cons: Need to check Railway worker support

### **2. If We Split:**

**Question 2a:** Should bot restart API (`/api/bot-control`) restart:
- A) Only the bot service (via `BOT_RAILWAY_SERVICE_ID`)
- B) Both services (current behavior)
- C) Something else?

**Question 2b:** How should we handle bot status?
- A) Bot writes to database (current approach - works across services)
- B) Bot writes to file (ephemeral, service-specific)
- C) Both (database + file for redundancy)

**Question 2c:** Should dashboard be able to restart itself?
- A) Yes (add self-restart endpoint)
- B) No (only restart bot)
- C) Via Railway dashboard only

### **3. Environment Variables:**

**Question 3:** For split services, should we:
- A) Copy all env vars to both services (simple, but duplicates)
- B) Use Railway shared variables (if supported)
- C) Dashboard reads from DB, bot uses env vars (different sources)

### **4. Current Issues:**

**Question 4:** The user says "it stopped when tried to restart the bot" - do you think:
- A) Restart is causing state loss (bot needs separate service)
- B) Restart is causing database connection issues (needs better connection handling)
- C) Restart is causing CLOB client reinit issues (needs better error handling)
- D) Something else?

---

## 📋 **What I've Prepared**

I've created these files (ready to use if approved):

1. **`ARCHITECTURE_SPLIT.md`** - Full architecture explanation
2. **`SPLIT_SERVICES_GUIDE.md`** - Step-by-step setup guide
3. **`Procfile.dashboard`** - Dashboard-only Procfile
4. **`Procfile.bot`** - Bot-only Procfile
5. **Updated `dashboard.py`** - Supports `BOT_RAILWAY_SERVICE_ID` for split services

**Status:** Ready to implement, but waiting for dev approval/feedback.

---

## 🎯 **Recommendation**

**I recommend Option A (Split Services)** because:

1. **User's observation is valid:** Restarting bot shouldn't take down dashboard
2. **Best practice:** Stateless web services should be separate from stateful workers
3. **Railway supports this:** Can create multiple services from same repo
4. **Minimal code changes:** Already prepared, just need to configure Railway
5. **Better long-term:** Easier to scale, debug, and maintain

**But:** Open to dev's expert opinion - maybe there's a simpler solution I'm missing?

---

## ⏳ **Next Steps**

**Waiting for dev feedback on:**
1. ✅ Proceed with split? (Yes/No/Alternative approach)
2. ✅ If yes, any changes needed to the proposed architecture?
3. ✅ Any concerns about shared database or environment variables?

**After approval:** Will guide user through Railway setup step-by-step.

---

**Thanks for your input!** 🙏
