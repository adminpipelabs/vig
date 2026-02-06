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
            kwargs.setdefault('proxy', PROXY_URL)
            super().__init__(*args, **kwargs)
    
    class ProxiedAsyncClient(_OriginalAsyncClient):
        """httpx.AsyncClient with automatic proxy injection"""
        def __init__(self, *args, **kwargs):
            # Always inject proxy if not already set
            kwargs.setdefault('proxy', PROXY_URL)
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
