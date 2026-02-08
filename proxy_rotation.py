"""
Proxy rotation utility for Cloudflare bypass
Rotates through ProxyScrape proxy list to avoid detection
"""
import random
import os
from typing import List

# ProxyScrape proxy list
PROXY_LIST = [
    "216.26.237.15:3129",
    "65.111.27.115:3129",
    "216.26.243.1:3129",
    "209.50.172.174:3129",
    "65.111.0.165:3129",
    "216.26.244.34:3129",
    "104.207.55.214:3129",
    "104.207.56.103:3129",
    "45.3.49.45:3129",
    "45.3.44.34:3129",
    # ... add more as needed
]

def get_random_proxy() -> str:
    """Get a random proxy from the list"""
    return random.choice(PROXY_LIST)

def set_proxy_env(proxy: str):
    """Set HTTP_PROXY and HTTPS_PROXY environment variables"""
    proxy_url = f"http://{proxy}"
    os.environ['HTTP_PROXY'] = proxy_url
    os.environ['HTTPS_PROXY'] = proxy_url
    return proxy_url

def rotate_proxy():
    """Rotate to a new random proxy"""
    proxy = get_random_proxy()
    proxy_url = set_proxy_env(proxy)
    return proxy_url
