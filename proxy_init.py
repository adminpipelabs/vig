"""
proxy_init.py
MUST be imported BEFORE py_clob_client or any other module that uses httpx.
Patches httpx.Client and httpx.AsyncClient to always use residential proxy.

This file must be imported first in main.py:
    import proxy_init  # FIRST import
    from py_clob_client.client import ClobClient  # Then other imports
"""
import os
import httpx

# Debug: Check ALL environment variables that might contain proxy info
print("=" * 70)
print("🔍 DEBUG: Checking for proxy environment variables...")
proxy_env_vars = [
    "RESIDENTIAL_PROXY_URL",
    " RESIDENTIAL_PROXY_URL",  # Check for leading space (Railway quirk)
    "RESIDENTIAL_PROXY_URL ",   # Check for trailing space
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "https_proxy",
    "http_proxy",
]

found_vars = {}
for var_name in proxy_env_vars:
    value = os.getenv(var_name, None)
    if value:
        found_vars[var_name] = value.strip()

if found_vars:
    print(f"✅ Found {len(found_vars)} proxy-related environment variable(s):")
    for var_name, value in found_vars.items():
        # Redact password for logging
        if "@" in value:
            parts = value.split("@")
            if ":" in parts[0]:
                user_pass = parts[0].split(":")
                if len(user_pass) == 2:
                    redacted = f"{user_pass[0]}:****@{parts[1]}"
                    print(f"   {var_name} = {redacted}")
                else:
                    print(f"   {var_name} = {value[:50]}...")
            else:
                print(f"   {var_name} = {value[:50]}...")
        else:
            print(f"   {var_name} = {value[:50]}...")
else:
    print("❌ NO proxy environment variables found!")
    print("   Checked: RESIDENTIAL_PROXY_URL, HTTPS_PROXY, HTTP_PROXY")
print("=" * 70)

# Get the proxy URL - prefer RESIDENTIAL_PROXY_URL, fallback to HTTPS_PROXY
PROXY_URL = os.getenv("RESIDENTIAL_PROXY_URL", "").strip()
if not PROXY_URL:
    # Try with leading/trailing spaces (Railway quirk)
    PROXY_URL = os.getenv(" RESIDENTIAL_PROXY_URL", "").strip()
if not PROXY_URL:
    PROXY_URL = os.getenv("RESIDENTIAL_PROXY_URL ", "").strip()
if not PROXY_URL:
    # Fallback to HTTPS_PROXY
    PROXY_URL = os.getenv("HTTPS_PROXY", "").strip()

if PROXY_URL:
    print(f"✅ Using proxy URL: {PROXY_URL.split('@')[-1] if '@' in PROXY_URL else PROXY_URL[:50]}...")
else:
    print("⚠️  PROXY_URL is empty - no proxy will be used")


def is_valid_proxy():
    """Check if proxy URL is valid (not a placeholder)"""
    if not PROXY_URL:
        return False
    # Check for placeholder patterns
    placeholder_patterns = [
        "your-username", "your-proxy", "placeholder", 
        "user:pass", "username:password", "@host", ":port"
    ]
    proxy_lower = PROXY_URL.lower()
    if any(pattern in proxy_lower for pattern in placeholder_patterns):
        return False
    
    # Warn if using wrong port for Bright Data residential proxy
    if "brd.superproxy.io" in PROXY_URL:
        if ":22225" in PROXY_URL:
            print("⚠️  WARNING: Bright Data residential proxy should use port 33335, not 22225")
            print("   Update RESIDENTIAL_PROXY_URL to use port 33335")
        elif ":33335" not in PROXY_URL:
            print(f"⚠️  WARNING: Unexpected port in Bright Data proxy URL: {PROXY_URL}")
    
    return True


if is_valid_proxy():
    # Store original classes
    _OriginalClient = httpx.Client
    _OriginalAsyncClient = httpx.AsyncClient
    
    # Create proxied versions
    class ProxiedClient(_OriginalClient):
        """httpx.Client with automatic proxy injection"""
        def __init__(self, *args, **kwargs):
            # Always inject proxy if not already set
            # httpx prefers 'proxy' parameter (single string) over 'proxies' dict
            # IMPORTANT: httpx expects proxy URL in format: http://user:pass@host:port
            # Bright Data format: http://brd-customer-XXXXX-zone-ZONE:PASSWORD@brd.superproxy.io:33335
            
            if 'proxy' not in kwargs and 'proxies' not in kwargs:
                kwargs['proxy'] = PROXY_URL
            elif 'proxies' in kwargs and not kwargs['proxies']:
                # If proxies dict is empty, use our proxy
                kwargs['proxy'] = PROXY_URL
                kwargs.pop('proxies', None)
            elif 'proxy' not in kwargs:
                # If proxies dict exists but proxy doesn't, add it
                kwargs['proxy'] = PROXY_URL
            
            # Verify proxy URL format is correct
            proxy_to_use = kwargs.get('proxy', PROXY_URL)
            if proxy_to_use and not proxy_to_use.startswith('http://') and not proxy_to_use.startswith('https://'):
                print(f"⚠️  WARNING: Proxy URL doesn't start with http:// or https://: {proxy_to_use[:50]}")
            if proxy_to_use and '@' not in proxy_to_use:
                print(f"⚠️  WARNING: Proxy URL missing @ separator (no auth?): {proxy_to_use[:50]}")
            
            # Add browser-like headers to help bypass Cloudflare
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            headers = kwargs['headers']
            headers.setdefault('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            headers.setdefault('Accept', 'application/json')
            headers.setdefault('Accept-Language', 'en-US,en;q=0.9')
            headers.setdefault('Accept-Encoding', 'gzip, deflate, br')
            headers.setdefault('Connection', 'keep-alive')
            
            super().__init__(*args, **kwargs)
    
    class ProxiedAsyncClient(_OriginalAsyncClient):
        """httpx.AsyncClient with automatic proxy injection"""
        def __init__(self, *args, **kwargs):
            # Always inject proxy if not already set
            if 'proxy' not in kwargs and 'proxies' not in kwargs:
                kwargs['proxy'] = PROXY_URL
            elif 'proxies' in kwargs and not kwargs['proxies']:
                kwargs['proxy'] = PROXY_URL
                kwargs.pop('proxies', None)
            elif 'proxy' not in kwargs:
                kwargs['proxy'] = PROXY_URL
            
            # Add browser-like headers
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            headers = kwargs['headers']
            headers.setdefault('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            headers.setdefault('Accept', 'application/json')
            headers.setdefault('Accept-Language', 'en-US,en;q=0.9')
            
            super().__init__(*args, **kwargs)
    
    # Replace httpx classes
    httpx.Client = ProxiedClient
    httpx.AsyncClient = ProxiedAsyncClient
    
    # Also patch internal module references
    try:
        import httpx._client
        httpx._client.Client = ProxiedClient
        httpx._client.AsyncClient = ProxiedAsyncClient
    except:
        pass
    
    proxy_display = PROXY_URL.split("@")[-1] if "@" in PROXY_URL else PROXY_URL[:30] + "..."
    print(f"✅ PROXY ACTIVE: httpx patched with {proxy_display}")
else:
    print(f"⚠️  NO PROXY: RESIDENTIAL_PROXY_URL not set or invalid")
