"""
CLOB Proxy Wrapper
Routes CLOB API calls through residential proxy to bypass Cloudflare blocking.

Uses environment variables that httpx automatically respects:
- HTTPS_PROXY for HTTPS requests (CLOB API uses HTTPS)
- HTTP_PROXY for HTTP requests

This works because py_clob_client uses httpx internally, and httpx
automatically checks these environment variables.
"""
import os
import logging

logger = logging.getLogger("vig.clob_proxy")


def setup_clob_proxy():
    """
    Setup proxy for CLOB API calls using environment variables.
    
    httpx (used by py_clob_client) automatically respects HTTPS_PROXY
    and HTTP_PROXY environment variables. We set these only for CLOB
    API calls by setting them before ClobClient initialization.
    """
    proxy_url = os.getenv("RESIDENTIAL_PROXY_URL", "").strip()
    
    if proxy_url:
        # Set environment variables that httpx will automatically use
        # Only set for this process - won't affect other httpx clients
        os.environ["HTTPS_PROXY"] = proxy_url
        os.environ["HTTP_PROXY"] = proxy_url
        
        # Log (without exposing credentials)
        proxy_display = proxy_url.split("@")[0] + "@..." if "@" in proxy_url else proxy_url[:20] + "..."
        logger.info(f"Residential proxy configured: {proxy_display}")
        logger.info("CLOB API calls will route through residential proxy (httpx auto-detects HTTPS_PROXY)")
    else:
        logger.info("No RESIDENTIAL_PROXY_URL set - CLOB API calls will use direct connection")
        logger.warning("⚠️  CLOB API may be blocked by Cloudflare if running from datacenter IP")
        
        # Clear proxy env vars if they were set before
        os.environ.pop("HTTPS_PROXY", None)
        os.environ.pop("HTTP_PROXY", None)


def get_clob_client_with_proxy(host: str, key: str, chain_id: int):
    """
    Create ClobClient with proxy support.
    
    Sets HTTPS_PROXY/HTTP_PROXY environment variables before importing
    ClobClient, so httpx (used internally) will automatically use the proxy.
    """
    # Setup proxy environment variables before importing ClobClient
    setup_clob_proxy()
    
    from py_clob_client.client import ClobClient
    
    # ClobClient uses httpx internally, which will now use the proxy
    client = ClobClient(host, key=key, chain_id=chain_id)
    return client
