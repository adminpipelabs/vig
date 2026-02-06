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

PROXY_URL = os.getenv("RESIDENTIAL_PROXY_URL", "").strip()


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
            if 'proxy' not in kwargs and 'proxies' not in kwargs:
                kwargs['proxy'] = PROXY_URL
            elif 'proxies' in kwargs and not kwargs['proxies']:
                # If proxies dict is empty, use our proxy
                kwargs['proxy'] = PROXY_URL
                kwargs.pop('proxies', None)
            elif 'proxy' not in kwargs:
                # If proxies dict exists but proxy doesn't, add it
                kwargs['proxy'] = PROXY_URL
            
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
