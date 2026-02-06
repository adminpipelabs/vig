# Dev Help: PostgreSQL Cursor Issue - Need Second Opinion

## Problem

Bot keeps crashing with PostgreSQL cursor errors. Dashboard stuck on "LOADING..." because bot process crashes on startup.

## Error Pattern

```
TypeError: tuple indices must be integers or slices, not str
AttributeError: 'tuple' object has no attribute 'keys'
```

## Root Cause

PostgreSQL (`psycopg2`) returns rows as **tuples** by default, but our code expects **dict-like** objects (like SQLite's `Row` objects).

## What I've Tried

I've been fixing methods one-by-one by adding `RealDictCursor`:

```python
# Current approach - fix each method individually
def get_recent_windows(self, n: int = 20):
    if self.use_postgres:
        from psycopg2.extras import RealDictCursor
        c = self.conn.cursor(cursor_factory=RealDictCursor)  # ← Added this
        c.execute("SELECT * FROM windows ORDER BY id DESC LIMIT %s", (n,))
    else:
        c = self.conn.cursor()
        c.execute("SELECT * FROM windows ORDER BY id DESC LIMIT ?", (n,))
    # ...
```

**Fixed so far:**
- ✅ `get_recent_windows()`
- ✅ `get_consecutive_losses()`
- ✅ `get_window()`
- ✅ `get_pending_bets()`
- ✅ `get_window_bets()`
- ✅ `get_recent_bets()`
- ✅ `get_all_pending_bets()`

**But bot still crashes** - there might be more methods I'm missing, or the approach is wrong.

## Questions for Dev

### 1. Best Pattern for PostgreSQL Cursors?

**Option A: Set cursor factory globally** (recommended?)
```python
# In Database.__init__()
if self.use_postgres:
    self.conn = psycopg2.connect(self.database_url)
    self.conn.set_session(autocommit=False)
    # Set default cursor factory for all cursors
    from psycopg2.extras import RealDictCursor
    self.conn.cursor_factory = RealDictCursor  # ← Set once, use everywhere
```

**Option B: Fix each method individually** (current approach)
- More verbose
- Easy to miss methods
- But explicit and clear

**Option C: Wrapper method**
```python
def _get_cursor(self):
    if self.use_postgres:
        from psycopg2.extras import RealDictCursor
        return self.conn.cursor(cursor_factory=RealDictCursor)
    return self.conn.cursor()
```

### 2. Are There Other Methods I'm Missing?

Methods that might need fixing:
- `get_all_stats()` - uses `dict(row)` but might fail if row is tuple
- `insert_bet()` - uses `c.fetchone()[0]` - might be OK (index access)
- `insert_window()` - uses `c.fetchone()[0]` - might be OK
- Any other methods that access row data?

### 3. Should We Use a Different Pattern?

Maybe we should:
- Use an ORM? (SQLAlchemy?)
- Use a database abstraction layer?
- Standardize on one approach?

### 4. Current Code Structure

```python
class Database:
    def __init__(self, db_path: str = None, database_url: str = None):
        if database_url or os.getenv("DATABASE_URL"):
            self.use_postgres = True
            self.conn = psycopg2.connect(self.database_url)
            self.conn.set_session(autocommit=False)
            # ❓ Should we set cursor_factory here?
        else:
            self.use_postgres = False
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # ← SQLite has this
            
    # Methods that query data need dict-like rows
    def get_recent_windows(self, n: int = 20):
        # Currently fixing individually...
```

## Current Status

- Dashboard API endpoints work (return 200 OK)
- Bot crashes on startup when calling database methods
- Fixed 7+ methods but still crashing
- Need to find remaining issues or change approach

## Your Opinion Needed

1. **What's the best pattern?** Global cursor factory or fix individually?
2. **Are there other methods** I'm missing that need fixing?
3. **Should we refactor** to use a different approach entirely?
4. **How to debug** - what's the best way to find all methods that need fixing?

## Suggested Next Steps

1. **Set cursor factory globally** in `__init__` - would fix all methods at once
2. **Or audit all methods** - find every place that accesses row data
3. **Add better error handling** - catch and log which method is failing
4. **Consider refactoring** - use a consistent pattern throughout

Thanks for reviewing! The bot is currently down because of this issue. 🙏
