# Railway Debug Checklist

## Current Configuration

**railway.json:**
```json
{
  "deploy": {
    "startCommand": "uvicorn dashboard:app --host 0.0.0.0 --port $PORT"
  }
}
```

**Dockerfile CMD:**
```dockerfile
CMD uvicorn dashboard:app --host 0.0.0.0 --port ${PORT}
```

**Procfile:**
```
web: uvicorn dashboard:app --host 0.0.0.0 --port $PORT
worker: python3 main.py
```

## Railway Behavior with Dockerfile Builder

When using Dockerfile builder:
- Railway **ignores Procfile** by default
- Railway uses `startCommand` from `railway.json` if set
- If no `startCommand`, Railway uses Dockerfile `CMD`
- Railway automatically sets `$PORT` environment variable

## What to Check in Railway Dashboard

1. **Service Settings → Start Command**
   - Should show: `uvicorn dashboard:app --host 0.0.0.0 --port $PORT`
   - If empty or wrong, Railway is using Dockerfile CMD

2. **Deployment Logs → Build**
   - Check if `fastapi` and `uvicorn` are installed
   - Look for: `Successfully installed fastapi-... uvicorn-...`

3. **Deployment Logs → Deploy**
   - Look for: `Uvicorn running on http://0.0.0.0:XXXX`
   - Check for port binding errors
   - Check for import errors

4. **Environment Variables**
   - `PORT` should be automatically set by Railway
   - `DATABASE_URL` should be set if using PostgreSQL

## Common Issues

### Issue 1: Wrong Start Command
**Symptom**: Bot starts instead of dashboard
**Fix**: Ensure `railway.json` has correct `startCommand`

### Issue 2: Port Binding Error
**Symptom**: `Address already in use` or `Cannot bind to port`
**Fix**: Ensure using `$PORT` variable, not hardcoded port

### Issue 3: Missing Dependencies
**Symptom**: `ModuleNotFoundError: No module named 'fastapi'`
**Fix**: Verify `requirements.txt` includes `fastapi` and `uvicorn`

### Issue 4: Import Error
**Symptom**: `ImportError: cannot import name 'app' from 'dashboard'`
**Fix**: Verify `dashboard.py` exports `app` object

## Manual Fix in Railway Dashboard

If automatic deployment isn't working:

1. Go to Railway → Your Service → Settings
2. Scroll to "Start Command"
3. Set it to: `uvicorn dashboard:app --host 0.0.0.0 --port $PORT`
4. Save and redeploy

## Test Locally

```bash
# Test exact Railway command
PORT=8080 uvicorn dashboard:app --host 0.0.0.0 --port 8080

# Should see:
# INFO:     Uvicorn running on http://0.0.0.0:8080
# INFO:     Application startup complete.
```

## Next Steps

1. Check Railway deployment logs (most important)
2. Verify startCommand in Railway dashboard matches railway.json
3. If still failing, manually set startCommand in Railway dashboard
4. Check if PORT environment variable is being set correctly
