# Proxy Setup for Cloudflare Bypass

## ProxyScrape Setup Steps

### 1. Get Proxy Details
- Go to **"Proxy list"** in ProxyScrape dashboard
- Copy a proxy (format: `ip:port` or `username:password@ip:port`)
- Example: `123.45.67.89:8080` or `user:pass@123.45.67.89:8080`

### 2. Set Up Authentication
- Go to **"IP authentication"** 
- Add your Hetzner server IP: `5.161.64.209`
- OR use username/password from proxy list

### 3. Configure Bot
Add to `/root/vig/.env` on Hetzner:

```bash
# Proxy configuration (for Cloudflare bypass)
HTTP_PROXY=http://username:password@proxy-ip:port
HTTPS_PROXY=http://username:password@proxy-ip:port
```

**Note:** Use `http://` scheme even for HTTPS_PROXY (most proxies use HTTP for initial connection)

### 4. Restart Bot
```bash
systemctl restart vigbot
```

## How It Works

- `httpx` (used by py-clob-client) automatically respects `HTTP_PROXY`/`HTTPS_PROXY` environment variables
- All CLOB API requests will route through the proxy
- This should bypass Cloudflare geoblocking

## Testing

After setup, check logs:
```bash
tail -50 /root/vig/bot.log | grep -E 'order|Placed|ERROR|Cloudflare'
```

If orders start placing successfully, proxy is working!
