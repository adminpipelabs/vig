"""
API Security Module - Authentication, Rate Limiting, and Security Headers
"""
import os
import time
import hashlib
import hmac
from functools import wraps
from typing import Optional
from fastapi import HTTPException, Request, Security, Depends
from fastapi.security import APIKeyHeader, APIKeyQuery
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging

logger = logging.getLogger("vig.security")

# API Key Configuration
API_KEY_HEADER_NAME = "X-API-Key"
API_KEY_QUERY_NAME = "api_key"
API_KEY_ENV_VAR = "DASHBOARD_API_KEY"

# Rate Limiting Configuration
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))  # requests per window
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds

# Rate limit storage (in-memory, use Redis for production)
_rate_limit_store: dict[str, list[float]] = {}


def get_api_key() -> Optional[str]:
    """Get API key from environment variable"""
    return os.getenv(API_KEY_ENV_VAR)


def verify_api_key(api_key: str) -> bool:
    """Verify API key against configured key"""
    expected_key = get_api_key()
    if not expected_key:
        # If no API key configured, allow access (for development)
        # In production, always require API key
        return True
    
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(api_key.encode(), expected_key.encode())


# FastAPI security schemes
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)
api_key_query = APIKeyQuery(name=API_KEY_QUERY_NAME, auto_error=False)


def get_api_key_from_request(
    header_key: Optional[str] = Security(api_key_header),
    query_key: Optional[str] = Security(api_key_query),
) -> Optional[str]:
    """Extract API key from request (header or query param)"""
    return header_key or query_key


def require_api_key(
    api_key: Optional[str] = Depends(get_api_key_from_request)
) -> bool:
    """Dependency to require API key authentication"""
    configured_key = get_api_key()
    
    # If no API key configured, allow access (development mode)
    if not configured_key:
        logger.warning("API key not configured - allowing all requests (development mode)")
        return True
    
    # Require API key in production
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide via X-API-Key header or api_key query parameter."
        )
    
    if not verify_api_key(api_key):
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )
    
    return True


def check_rate_limit(client_id: str) -> bool:
    """Check if client has exceeded rate limit"""
    if not RATE_LIMIT_ENABLED:
        return True
    
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    
    # Clean old entries
    if client_id in _rate_limit_store:
        _rate_limit_store[client_id] = [
            timestamp for timestamp in _rate_limit_store[client_id]
            if timestamp > window_start
        ]
    else:
        _rate_limit_store[client_id] = []
    
    # Check limit
    request_count = len(_rate_limit_store[client_id])
    if request_count >= RATE_LIMIT_REQUESTS:
        return False
    
    # Record this request
    _rate_limit_store[client_id].append(now)
    return True


def get_client_id(request: Request) -> str:
    """Get client identifier for rate limiting"""
    # Use API key if available, otherwise use IP address
    api_key = request.headers.get(API_KEY_HEADER_NAME) or request.query_params.get(API_KEY_QUERY_NAME)
    if api_key:
        # Hash API key for privacy
        return hashlib.sha256(api_key.encode()).hexdigest()[:16]
    
    # Fallback to IP address
    client_ip = request.client.host if request.client else "unknown"
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take first IP if multiple (proxy chain)
        client_ip = forwarded_for.split(",")[0].strip()
    
    return client_ip


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Only add CSP if not already set
        if "Content-Security-Policy" not in response.headers:
            # Allow Tailwind CDN and fonts for dashboard
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data:; "
                "connect-src 'self';"
            )
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware"""
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for HTML pages
        if request.url.path == "/" or request.url.path.startswith("/pnl"):
            return await call_next(request)
        
        # Skip rate limiting for health check
        if request.url.path == "/api/health":
            return await call_next(request)
        
        client_id = get_client_id(request)
        
        if not check_rate_limit(client_id):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds",
                    "retry_after": RATE_LIMIT_WINDOW
                }
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        if client_id in _rate_limit_store:
            remaining = RATE_LIMIT_REQUESTS - len(_rate_limit_store[client_id])
            response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_REQUESTS)
            response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
            response.headers["X-RateLimit-Window"] = str(RATE_LIMIT_WINDOW)
        
        return response


def secure_endpoint(func):
    """Decorator to secure API endpoints with authentication"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Check if API key is required
        configured_key = get_api_key()
        if configured_key:
            # Extract request from kwargs (FastAPI dependency injection)
            request = kwargs.get('request') or kwargs.get('_request')
            if request:
                api_key = get_api_key_from_request(
                    request.headers.get(API_KEY_HEADER_NAME),
                    request.query_params.get(API_KEY_QUERY_NAME)
                )
                if not api_key or not verify_api_key(api_key):
                    raise HTTPException(
                        status_code=401,
                        detail="Authentication required"
                    )
        
        return await func(*args, **kwargs)
    return wrapper


def validate_limit(limit: Optional[int] = None, max_limit: int = 1000) -> int:
    """Validate and sanitize limit parameter"""
    if limit is None:
        return 100  # Default
    
    if not isinstance(limit, int):
        raise HTTPException(status_code=400, detail="Invalid limit parameter")
    
    if limit < 1:
        raise HTTPException(status_code=400, detail="Limit must be positive")
    
    if limit > max_limit:
        raise HTTPException(status_code=400, detail=f"Limit exceeds maximum of {max_limit}")
    
    return limit
