# Pipe Labs MCP Server

Connect Claude to your Pipe Labs trading platform for natural language trading operations.

## What You Can Say to Claude

Once connected, you can use natural language commands like:

- **"Start market making on BitMart for SHARP/USDT with 0.5% spread"**
- **"Generate $50k volume on KuCoin over 24 hours"**
- **"Stop all bots for client John"**
- **"Show P&L for all active strategies"**
- **"List all clients"**
- **"Get portfolio for client ABC"**
- **"Show me the orderbook for BTC/USDT on BitMart"**

## Installation

### 1. Install Dependencies

```bash
cd pipelabs-mcp
pip install -r requirements.txt
```

### 2. Get Your Admin Token

1. Log into your Pipe Labs dashboard as admin
2. Open browser DevTools (F12) → Console
3. Run: `localStorage.getItem('pipelabs_token')`
4. Copy the token

### 3. Configure Claude Desktop

Edit your Claude Desktop config file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Add this configuration:

```json
{
  "mcpServers": {
    "pipelabs-trading": {
      "command": "python",
      "args": ["/full/path/to/pipelabs-mcp/server.py"],
      "env": {
        "PIPELABS_BACKEND_URL": "https://pipelabs-dashboard-production.up.railway.app",
        "PIPELABS_ADMIN_TOKEN": "your-jwt-token-here"
      }
    }
  }
}
```

### 4. Restart Claude Desktop

Close and reopen Claude Desktop. You should see the MCP tools available.

## Available Tools

### Client Management
- `list_clients` - List all clients
- `get_client` - Get client details
- `create_client` - Create new client

### Exchange Connections
- `list_client_exchanges` - View connected exchanges
- `add_exchange_connection` - Add API keys

### Trading Bots
- `start_market_making` - Start market making bot
- `start_volume_generation` - Start volume generation
- `stop_bot` - Stop specific bot
- `stop_all_bots` - Stop all bots for client
- `list_active_bots` - List running bots

### Portfolio & P&L
- `get_portfolio` - Get balances
- `get_pnl` - Get profit/loss
- `get_trade_history` - View trade history

### Market Data
- `get_market_data` - Get price/volume data
- `get_orderbook` - Get orderbook

### Dashboard
- `get_dashboard_overview` - Overall stats
- `get_alerts` - View alerts

## Backend Requirements

For full functionality, your backend needs these endpoints:

### Already Implemented
- `GET /api/admin/clients`
- `GET /api/admin/clients/{id}`
- `POST /api/admin/clients`
- `GET /api/admin/clients/{id}/api-keys`
- `POST /api/admin/clients/{id}/api-keys`
- `GET /api/admin/overview`

### Need to Add (for bot control)
- `POST /api/agent/bots/start`
- `POST /api/agent/bots/{id}/stop`
- `POST /api/agent/clients/{id}/bots/stop-all`
- `GET /api/agent/bots`
- `GET /api/agent/clients/{id}/portfolio`
- `GET /api/agent/pnl`
- `GET /api/agent/trades`
- `GET /api/agent/market/{exchange}/{pair}`
- `GET /api/agent/orderbook/{exchange}/{pair}`

## Hummingbot Integration

To enable actual trading, connect to Hummingbot Gateway:

1. Install Hummingbot Gateway
2. Configure exchange connectors
3. Update backend to proxy commands to Gateway

See: https://docs.hummingbot.org/gateway/

## Troubleshooting

**MCP not connecting:**
- Check the path in `claude_desktop_config.json`
- Verify Python is in your PATH
- Check token is valid

**API errors:**
- Verify backend is running: `curl https://your-backend.railway.app/health`
- Check token hasn't expired
- Look at backend logs in Railway

## Security Notes

- Never commit your admin token to git
- Use environment variables for sensitive data
- Consider token rotation for production
