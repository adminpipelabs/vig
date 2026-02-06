# Dev Help: Proxy Connection Failing

**Date:** 2026-02-05  
**Issue:** Proxy is configured but CLOB API requests are failing with generic "Request exception!"

---

## 🔍 **Current Situation**

### **What's Working:**
- ✅ Proxy URL is correctly formatted and set in Railway
- ✅ Environment variables (`HTTPS_PROXY`, `HTTP_PROXY`) are set
- ✅ Proxy validation passes (host, port, format all correct)
- ✅ Bot starts successfully
- ✅ Markets are being scanned

### **What's Failing:**
- ❌ CLOB client initialization fails when calling `create_or_derive_api_creds()`
- ❌ Error is generic: `PolyApiException[status_code=None, error_message=Request exception!]`
- ❌ Both proxy and direct connection fail with same error

---

## 📋 **Error Details**

**From Railway logs:**
```
05:11:27 [vig.clob_proxy] INFO: ✅ Residential proxy configured: http://brd-customer-hl_b4689439-zone-residential_proxy1:5teowbs6s9c9@...
05:11:27 [vig.clob_proxy] INFO: Proxy host: brd.superproxy.io, port: 33335
05:11:27 [vig.clob_proxy] INFO: HTTPS_PROXY env var is set (length: 92 chars)
05:11:27 [vig.clob_proxy] INFO: ClobClient created - proxy should be active for all HTTP requests
05:11:27 [vig] INFO: Testing proxy connection by creating API credentials...
05:11:30 [vig] WARNING: ⚠️  Proxy initialization failed: PolyApiException[status_code=None, error_message=Request exception!]
```

**Proxy URL format:**
```
http://brd-customer-hl_b4689439-zone-residential_proxy1:5teowbs6s9c9@brd.superproxy.io:33335
```

**Proxy test (manual curl) works:**
```bash
curl -x "http://brd-customer-hl_b4689439-zone-residential_proxy1:5teowbs6s9c9@brd.superproxy.io:33335" \
  "https://geo.brdtest.com/welcome.txt?product=resi&method=native"
# Returns: HTTP/1.1 200 OK (proxy works!)
```

---

## 🤔 **Questions for Dev**

### **1. How does py_clob_client use httpx?**

**Question:** Does `py_clob_client` create its own `httpx.Client()` instance, or does it use a shared one?

**Why:** If it creates its own client, it might not respect `HTTPS_PROXY` environment variables. We're setting env vars before importing `ClobClient`, but if it creates a new httpx client internally, it might not pick them up.

**Code location:** `clob_proxy.py` sets env vars, then imports `ClobClient`. But we don't know if `ClobClient.__init__()` creates httpx client at import time or at request time.

### **2. How to get detailed error information?**

**Question:** `PolyApiException` only shows `error_message=Request exception!` - how can we see the underlying exception (timeout, connection refused, SSL error, etc.)?

**Why:** We need to know if it's:
- Connection timeout (proxy not reachable)
- SSL/TLS error (proxy needs different SSL settings)
- Authentication error (wrong credentials)
- DNS error (can't resolve proxy hostname)
- Something else

**Current code:**
```python
except Exception as e:
    logger.warning(f"⚠️  Proxy initialization failed: {e}")
    # e is PolyApiException, but error_message is generic
```

**What we need:** Access to the underlying `httpx` exception or `requests` exception.

### **3. Can we pass proxy explicitly to py_clob_client?**

**Question:** Is there a way to configure `ClobClient` to use a proxy directly, instead of relying on environment variables?

**Why:** Environment variables might not work if:
- `py_clob_client` creates httpx client before env vars are set
- httpx client doesn't have `trust_env=True`
- Multiple httpx clients are created and some don't respect env vars

**Possible solutions:**
- Pass proxy to `ClobClient` constructor (if supported)
- Monkey-patch httpx to always use proxy
- Create custom httpx client and pass to `ClobClient` (if supported)

### **4. Bright Data proxy specifics**

**Question:** Do Bright Data residential proxies need any special configuration?

**Known facts:**
- Proxy works with curl (tested manually)
- Port 33335 is correct (from Bright Data dashboard)
- Username format: `brd-customer-XXXXX-zone-ZONE_NAME`
- Password is correct

**Possible issues:**
- SSL verification (might need `verify=False` or custom CA)
- HTTP/2 vs HTTP/1.1 (httpx uses HTTP/2 by default, proxy might only support HTTP/1.1)
- Connection pooling (httpx might reuse connections that don't go through proxy)
- Timeout settings (proxy might be slower than direct connection)

### **5. Why does direct connection also fail?**

**Question:** If proxy fails, why does direct connection also fail with same error?

**Observation:** Both proxy and direct connection fail with `Request exception!`. This suggests:
- Either both are hitting the same issue (Cloudflare blocking direct, proxy not working)
- Or there's a different issue (network, DNS, SSL, etc.)

**What we need:** More detailed error to distinguish between:
- Cloudflare blocking (403, HTML response)
- Network error (connection refused, timeout)
- SSL error (certificate validation)
- Other errors

---

## 💡 **Possible Solutions to Try**

### **Option 1: Explicit httpx client with proxy**

```python
import httpx
from py_clob_client.client import ClobClient

# Create httpx client with explicit proxy
proxy_url = "http://brd-customer-XXXXX:password@brd.superproxy.io:33335"
client = httpx.Client(
    proxies={"http://": proxy_url, "https://": proxy_url},
    verify=False,  # If SSL issues
    timeout=30.0
)

# Pass to ClobClient? (need to check if this is supported)
clob_client = ClobClient(host, key=key, chain_id=chain_id, http_client=client)
```

**Question:** Does `ClobClient` accept a custom httpx client?

### **Option 2: Monkey-patch httpx**

```python
import httpx
original_client_init = httpx.Client.__init__

def patched_init(self, *args, **kwargs):
    proxy_url = os.getenv("RESIDENTIAL_PROXY_URL")
    if proxy_url:
        kwargs.setdefault("proxies", {})["http://"] = proxy_url
        kwargs.setdefault("proxies", {})["https://"] = proxy_url
    return original_client_init(self, *args, **kwargs)

httpx.Client.__init__ = patched_init
```

**Question:** Is this safe/recommended, or will it break other things?

### **Option 3: Check py_clob_client source**

**Question:** Can we look at `py_clob_client` source code to see how it creates httpx clients? Or is there documentation on proxy support?

---

## 🎯 **What We Need**

1. **Detailed error information** - underlying exception, not generic "Request exception!"
2. **Proxy configuration method** - explicit way to pass proxy to `ClobClient`
3. **Debugging approach** - how to verify proxy is actually being used
4. **Bright Data specifics** - any special requirements for Bright Data proxies

---

## 📝 **Current Code**

**File: `clob_proxy.py`**
- Sets `HTTPS_PROXY` and `HTTP_PROXY` environment variables
- Sets `HTTPX_TRUST_ENV=1` to ensure httpx respects env vars
- Clears `NO_PROXY` to prevent interference
- Validates proxy URL format

**File: `main.py`**
- Calls `get_clob_client_with_proxy()` if `RESIDENTIAL_PROXY_URL` is set
- Falls back to direct connection if proxy fails
- Falls back to scan-only mode if both fail

**Issue:** Proxy env vars are set, but requests still fail. Need to understand why.

---

**Thanks for your help!** 🙏
