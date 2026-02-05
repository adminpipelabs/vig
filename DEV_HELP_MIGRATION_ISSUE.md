# 🚨 DEV HELP NEEDED: Migration Script Not Working

## Problem

The `migrate_to_postgres.py` script is **not working** - it gets stuck and never completes.

## What Happened

1. **Started migration**: Ran `python migrate_to_postgres.py`
2. **Process got stuck**: Ran for 8+ hours with no progress
3. **Had to kill it**: Process was consuming resources but not completing
4. **PostgreSQL connection issues**: Can't even connect to check if any data was migrated

## Current Situation

### SQLite Database (Source)
- ✅ **23 bets** - ready to migrate
- ⚠️ **33,160 windows** - large dataset, migration gets stuck here
- ✅ **0 circuit_breaker_log entries** - nothing to migrate

### PostgreSQL Database (Destination)
- ❓ **Unknown status** - can't connect to check what was migrated
- ❌ **Connection keeps timing out** - suggests database connectivity issue

## Root Cause Analysis

### Issue 1: PostgreSQL Connection Timeout
```python
# Connection attempt times out after 5 seconds
conn = psycopg2.connect(POSTGRES_URL, connect_timeout=5)
```
- Connection to PostgreSQL database is slow or unreachable
- This causes the migration to hang indefinitely

### Issue 2: Large Dataset Without Progress Tracking
The migration script processes 33,160 windows in batches:
```python
batch_size = 1000
for i in range(0, len(window_data), batch_size):
    # Only prints progress every 5000 rows
    if i % 5000 == 0:
        print(f"  Migrated {total_inserted}/{len(windows)} windows...")
```
- No progress feedback for first 5 batches (0-4999 rows)
- If connection is slow, even small batches can hang
- No timeout or retry logic

### Issue 3: No Error Handling
- Script doesn't handle connection failures gracefully
- No way to resume migration if it fails partway through
- No check for existing data (not idempotent)

## What We Need Help With

### 1. **Database Connectivity Check**
- Is the PostgreSQL database accessible?
- What's the connection string format? (Current: `DATABASE_URL` env var)
- Are there firewall/network restrictions?
- Is the database on Railway/cloud service that might have connection limits?

### 2. **Migration Script Improvements**
We need the migration script to:
- ✅ Handle connection timeouts gracefully
- ✅ Show progress for every batch (not just every 5000 rows)
- ✅ Retry failed batches automatically
- ✅ Check if data already exists before migrating (idempotent)
- ✅ Use faster method for large datasets (maybe PostgreSQL `COPY`?)

### 3. **Alternative Approach**
For 33,160 rows, should we:
- Use PostgreSQL `COPY` command instead of `INSERT`? (much faster)
- Migrate in smaller chunks with checkpoints?
- Use a different migration tool/library?

## Questions for Dev

1. **Database Access**: How should we connect to PostgreSQL? Is `DATABASE_URL` the right env var?
2. **Connection Timeout**: Why is the connection timing out? Is the database accessible?
3. **Migration Strategy**: For 33k+ rows, what's the best approach?
4. **Error Recovery**: How should we handle partial migrations if script fails partway?

## Current Migration Script Location

`/Users/mikaelo/vig/migrate_to_postgres.py`

## What We've Tried

1. ✅ Killed stuck process
2. ✅ Analyzed the code to find bottlenecks
3. ✅ Identified connection timeout as main issue
4. ❌ Can't test PostgreSQL connection (keeps timing out)

## Next Steps Needed

1. **Fix database connectivity** - figure out why PostgreSQL connection times out
2. **Improve migration script** - add error handling, progress tracking, retry logic
3. **Test with small dataset first** - maybe migrate just bets (23 rows) to verify connection works
4. **Then migrate windows** - once connection is stable, migrate the 33k windows

## Code Snippet: Current Problem Area

```python
# Lines 143-159 in migrate_to_postgres.py
batch_size = 1000
total_inserted = 0
for i in range(0, len(window_data), batch_size):
    batch = window_data[i:i+batch_size]
    pg_cur.executemany("""
        INSERT INTO windows (...)
        VALUES (...)
    """, batch)
    total_inserted += len(batch)
    if i % 5000 == 0:  # ⚠️ Only logs every 5000 rows
        print(f"  Migrated {total_inserted}/{len(windows)} windows...")
        pg_conn.commit()
```

**Problem**: If connection is slow, even `executemany` with 1000 rows can hang, and we won't see any progress until 5000 rows are done.

---

**Status**: 🔴 **BLOCKED** - Need dev help to fix database connectivity and improve migration script.
