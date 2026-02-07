# API Security Setup Guide

## Overview

The dashboard APIs are now secured with:
- ✅ **API Key Authentication** - Required for all API endpoints
- ✅ **Rate Limiting** - Prevents abuse (100 requests per 60 seconds)
- ✅ **Security Headers** - XSS protection, frame options, CSP
- ✅ **Input Validation** - Sanitizes all parameters
- ✅ **Error Handling** - Doesn't leak sensitive information

## Setup

### 1. Generate API Key

Generate a secure random API key:

```bash
# Option 1: Using Python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Option 2: Using OpenSSL
openssl rand -hex 32

# Option 3: Using online generator
# Visit: https://randomkeygen.com/
```

**Example:** `kX9mP2qL8nR5tW7vY3zA6bC1dE4fG8hJ0kM2nP5qR8tV1wX4yZ7aB0cD3eF6gH`

### 2. Set API Key on Railway

1. Go to Railway → Your Project → **Dashboard** service
2. Click **Variables** tab
3. Add new variable:
   - **Name:** `DASHBOARD_API_KEY`
   - **Value:** Your generated API key
4. Railway will auto-redeploy

### 3. Set API Key Locally (for development)

Add to your `.env` file:

```bash
DASHBOARD_API_KEY=kX9mP2qL8nR5tW7vY3zA6bC1dE4fG8hJ0kM2nP5qR8tV1wX4yZ7aB0cD3eF6gH
```

### 4. Using the Dashboard

**First Time:**
- When you visit the dashboard, it will prompt for API key
- Enter your API key
- It's stored in browser localStorage

**Subsequent Visits:**
- API key is automatically included in all requests
- No need to re-enter

**To Change API Key:**
- Clear browser localStorage
- Or manually: `localStorage.removeItem('dashboard_api_key')` in browser console

## API Usage

### With Header (Recommended)

```bash
curl -H "X-API-Key: your-api-key-here" https://your-railway-url.railway.app/api/stats
```

### With Query Parameter

```bash
curl "https://your-railway-url.railway.app/api/stats?api_key=your-api-key-here"
```

## Rate Limits

- **Limit:** 100 requests per 60 seconds per client
- **Headers:** Check `X-RateLimit-Remaining` in response
- **Exceeded:** Returns 429 status with retry information

## Security Features

### 1. API Key Authentication
- All `/api/*` endpoints require authentication
- Public endpoints (`/`, `/pnl`) don't require auth (they're HTML pages)
- Health check (`/api/health`) is public

### 2. Rate Limiting
- Prevents abuse and DDoS
- Per-client (API key or IP address)
- Configurable via environment variables

### 3. Security Headers
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Content-Security-Policy` (allows Tailwind CDN)

### 4. Input Validation
- All limit parameters validated
- Maximum limits enforced
- SQL injection protection via parameterized queries

## Configuration

Environment variables:

```bash
# Required: API key for authentication
DASHBOARD_API_KEY=your-secure-api-key

# Optional: Rate limiting
RATE_LIMIT_ENABLED=true          # Enable/disable rate limiting
RATE_LIMIT_REQUESTS=100          # Requests per window
RATE_LIMIT_WINDOW=60             # Window in seconds
```

## Development Mode

If `DASHBOARD_API_KEY` is not set:
- APIs will work without authentication (development mode)
- Warning logged: "API key not configured - allowing all requests"
- **⚠️ Never deploy to production without API key**

## Production Checklist

- [ ] Generate strong API key (32+ characters, random)
- [ ] Set `DASHBOARD_API_KEY` on Railway
- [ ] Verify rate limiting is enabled
- [ ] Test API endpoints require authentication
- [ ] Verify security headers are present
- [ ] Test rate limiting works correctly

## Troubleshooting

**"API key required" error:**
- Check `DASHBOARD_API_KEY` is set on Railway
- Verify API key is correct
- Check browser console for errors

**"Rate limit exceeded":**
- Wait for rate limit window to reset
- Check `X-RateLimit-Remaining` header
- Consider increasing limit for your use case

**Dashboard shows "Loading..." forever:**
- Check browser console for 401 errors
- Verify API key is stored in localStorage
- Try clearing localStorage and re-entering API key
