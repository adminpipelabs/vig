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
from urllib.parse import urlparse

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
        # Validate URL format
        try:
            parsed = urlparse(proxy_url)
            if not parsed.scheme or not parsed.hostname:
                raise ValueError("Invalid URL format: missing scheme or hostname")
            
            # Check for placeholder values
            placeholder_keywords = ["user", "pass", "host", "port", "username", "password"]
            proxy_lower = proxy_url.lower()
            if any(keyword in proxy_lower and keyword not in ["http", "https"] for keyword in placeholder_keywords):
                # Check if it's actually a placeholder (contains literal "port" or "host" as values)
                if ":port" in proxy_lower or "@host" in proxy_lower or "user:pass" in proxy_lower:
                    raise ValueError(
                        "RESIDENTIAL_PROXY_URL appears to contain placeholder values. "
                        "Please set a real proxy URL in format: http://username:password@proxy-host:port"
                    )
            
            # Validate port if present
            if parsed.port is None and ":" in parsed.netloc and "@" in parsed.netloc:
                # URL has format user:pass@host:port, check if port part exists
                netloc_after_at = parsed.netloc.split("@")[-1]
                if ":" in netloc_after_at:
                    port_part = netloc_after_at.split(":")[-1]
                    if not port_part.isdigit() and port_part.lower() == "port":
                        raise ValueError(
                            "RESIDENTIAL_PROXY_URL has placeholder 'port' instead of actual port number. "
                            "Format should be: http://username:password@proxy-host:22225"
                        )
            
        except ValueError as e:
            logger.error(f"Invalid RESIDENTIAL_PROXY_URL: {e}")
            logger.error("Please set RESIDENTIAL_PROXY_URL to a valid proxy URL in Railway environment variables")
            logger.error("Expected format: http://username:password@proxy-host:port")
            raise
        
        # Set environment variables that httpx will automatically use
        # Only set for this process - won't affect other httpx clients
        os.environ["HTTPS_PROXY"] = proxy_url
        os.environ["HTTP_PROXY"] = proxy_url
        
        # Also set NO_PROXY to empty to ensure proxy is used
        # (some environments have NO_PROXY set which can prevent proxy usage)
        os.environ.pop("NO_PROXY", None)
        
        # Log (without exposing credentials)
        proxy_display = proxy_url.split("@")[0] + "@..." if "@" in proxy_url else proxy_url[:20] + "..."
        logger.info(f"✅ Residential proxy configured: {proxy_display}")
        logger.info("CLOB API calls will route through residential proxy (httpx auto-detects HTTPS_PROXY)")
        
        # Verify proxy URL format
        if parsed.port:
            logger.info(f"Proxy host: {parsed.hostname}, port: {parsed.port}")
        else:
            logger.warning("⚠️  Proxy URL has no explicit port - ensure port is included in URL")
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
    
    # Verify proxy env vars are set
    https_proxy = os.getenv("HTTPS_PROXY")
    if not https_proxy:
        raise RuntimeError("HTTPS_PROXY not set after setup_clob_proxy() - this should not happen")
    
    logger.info(f"HTTPS_PROXY env var is set (length: {len(https_proxy)} chars)")
    
    from py_clob_client.client import ClobClient
    
    # ClobClient uses httpx internally, which will now use the proxy
    # Note: httpx automatically checks HTTPS_PROXY env var
    client = ClobClient(host, key=key, chain_id=chain_id)
    
    # Log that client was created (proxy should be active)
    logger.info("ClobClient created - proxy should be active for all HTTP requests")
    
    return client
