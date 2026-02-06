# Dev Help: Dashboard Stuck on "LOADING..."

## Problem

Dashboard is stuck showing "LOADING..." status and won't update. Bot status shows "LOADING..." indefinitely.

## What We've Done

1. **Fixed PostgreSQL cursor issue** in `db.py`:
   - Changed `get_recent_windows()` to use `RealDictCursor` for PostgreSQL
   - Fixed `AttributeError: 'tuple' object has no attribute 'keys'`
   - Same fix pattern as dashboard.py

2. **Deployed fix** - Railway auto-deployed the change

3. **Still showing "LOADING..."** after deployment

## Current Status

- Dashboard API endpoints are returning 200 OK (from logs)
- Bot process may be crashing on startup
- Dashboard JavaScript might be stuck waiting for bot status

## Possible Causes

### 1. Bot Still Crashing
- There might be other PostgreSQL cursor issues in `db.py`
- Other methods might also need `RealDictCursor`
- Check if `_row_to_bet()` or `get_window()` have similar issues

### 2. Dashboard JavaScript Issue
- The `refresh()` function might be failing silently
- API calls might be timing out
- Error handling might be swallowing errors

### 3. Database Connection Issues
- PostgreSQL connection might be slow/timing out
- Connection pool might be exhausted
- Database queries might be hanging

## Code to Check

### db.py - Other methods that might need RealDictCursor:

```python
def get_window(self, window_id: int) -> Optional[WindowRecord]:
    c = self.conn.cursor()  # ⚠️ Might need RealDictCursor for PostgreSQL
    # ...
    return WindowRecord(**{k: row[k] for k in row.keys()}) if row else None

def _row_to_bet(self, row) -> BetRecord:
    return BetRecord(**{k: row[k] for k in row.keys()})  # ⚠️ Assumes dict-like

def get_pending_bets(self, window_id: int) -> list[BetRecord]:
    c = self.conn.cursor()  # ⚠️ Might need RealDictCursor
    # Uses _row_to_bet which expects dict-like rows
```

### dashboard.py - JavaScript refresh function:

```javascript
async function refresh(){
  const[stats,windows,bets,curve,pending,botStatus]=await Promise.all([
    fetchJSON('/api/stats'),fetchJSON('/api/windows?limit=20'),
    fetchJSON('/api/bets?limit=30'),fetchJSON('/api/equity-curve'),
    fetchJSON('/api/pending'),fetchJSON('/api/bot-status'),
  ]);
  // If any of these fail, refresh() might not complete
}
```

## Questions for Dev

1. **Should we use RealDictCursor globally for PostgreSQL?**
   - Set `conn.cursor_factory = RealDictCursor` in `__init__`?
   - Or fix each method individually?

2. **How to debug dashboard "LOADING..." issue?**
   - Check browser console for JavaScript errors?
   - Add more logging to API endpoints?
   - Check if bot process is actually running?

3. **Database connection pattern:**
   - Should we reuse connections or create new ones?
   - Are we properly handling connection timeouts?
   - Should we add connection pooling?

4. **Error handling:**
   - Should dashboard show errors instead of "LOADING..."?
   - How to handle API timeouts gracefully?
   - Should we add retry logic?

## Debugging Steps Needed

1. **Check browser console** - Are there JavaScript errors?
2. **Check Railway logs** - Is bot process running or crashing?
3. **Test API endpoints directly** - Do they return data?
4. **Check database queries** - Are they timing out?
5. **Check bot status file** - Is it being written?

## Suggested Fixes

### Option 1: Set RealDictCursor globally
```python
# In Database.__init__()
if self.use_postgres:
    self.conn = psycopg2.connect(self.database_url)
    self.conn.set_session(autocommit=False)
    self.conn.cursor_factory = RealDictCursor  # Set globally
```

### Option 2: Fix all methods individually
- Go through each method that uses `row.keys()`
- Add `RealDictCursor` where needed

### Option 3: Add better error handling
- Dashboard should show errors instead of "LOADING..."
- Add timeout handling for API calls
- Add retry logic

## Your Opinion Needed

1. **What's the best approach** - global cursor factory or fix individually?
2. **How to debug** - what logs/debugging should we add?
3. **Error handling** - how should dashboard handle failures?
4. **Is there a better pattern** for PostgreSQL row handling?

Thanks for reviewing! 🙏
