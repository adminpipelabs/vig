"""
Professional Dashboard HTML Template
This will replace the dashboard() function in dashboard.py
"""
PROFESSIONAL_DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vig Trading Platform</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
                    colors: { primary: '#2563eb', success: '#10b981', danger: '#ef4444', warning: '#f59e0b' }
                }
            }
        }
    </script>
    <style>
        body { font-family: 'Inter', sans-serif; }
        @keyframes pulse-dot { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .pulse-dot { animation: pulse-dot 2s ease-in-out infinite; }
        .wallet-address { font-family: 'Courier New', monospace; font-size: 0.75rem; }
    </style>
</head>
<body class="bg-gray-50 text-gray-900">
    <header class="bg-white border-b border-gray-200 sticky top-0 z-50 shadow-sm">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex items-center justify-between h-16">
                <div class="flex items-center gap-8">
                    <div>
                        <h1 class="text-lg font-semibold text-gray-900">Vig Trading</h1>
                        <p class="text-xs text-gray-500">Automated Market Making</p>
                    </div>
                    <nav class="hidden md:flex gap-6">
                        <a href="#" class="text-sm font-medium text-gray-900 border-b-2 border-primary pb-4 -mb-px">Dashboard</a>
                        <a href="#" class="text-sm font-medium text-gray-500 hover:text-gray-900">Bets</a>
                        <a href="#" class="text-sm font-medium text-gray-500 hover:text-gray-900">Analytics</a>
                    </nav>
                </div>
                <div class="flex items-center gap-4">
                    <div class="flex items-center gap-2 px-3 py-1.5 bg-green-50 rounded-lg" id="statusBadge">
                        <span class="w-1.5 h-1.5 bg-success rounded-full pulse-dot"></span>
                        <span class="text-xs font-medium text-success">Active</span>
                    </div>
                </div>
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <!-- Exchange Selector -->
        <div class="mb-6">
            <div class="flex items-center gap-3">
                <label class="text-sm font-medium text-gray-700">Exchange:</label>
                <select class="text-sm border border-gray-300 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-primary" id="exchangeSelect">
                    <option>Polymarket</option>
                    <option disabled>Kalshi (Coming Soon)</option>
                    <option disabled>PredictIt (Coming Soon)</option>
                </select>
            </div>
        </div>

        <!-- Multi-Wallet Overview -->
        <div class="mb-6">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-sm font-semibold text-gray-900">Wallets</h2>
                <button class="text-xs text-primary font-medium hover:underline" onclick="alert('Wallet management coming soon')">+ Add Wallet</button>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4" id="walletsContainer">
                <!-- Wallet cards will be populated by JavaScript -->
            </div>
        </div>

        <!-- Portfolio Summary -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div class="bg-white rounded-lg border border-gray-200 p-4">
                <div class="text-xs text-gray-500 mb-1">Total Portfolio Value</div>
                <div class="text-xl font-semibold text-gray-900" id="totalPortfolio">--</div>
                <div class="text-xs text-success mt-1" id="netPnl">--</div>
            </div>
            <div class="bg-white rounded-lg border border-gray-200 p-4">
                <div class="text-xs text-gray-500 mb-1">Win Rate</div>
                <div class="text-xl font-semibold text-gray-900" id="winRate">--</div>
                <div class="text-xs text-gray-500 mt-1" id="winRateSub">--</div>
            </div>
            <div class="bg-white rounded-lg border border-gray-200 p-4">
                <div class="text-xs text-gray-500 mb-1">Active Positions</div>
                <div class="text-xl font-semibold text-gray-900" id="activePositions">--</div>
                <div class="text-xs text-gray-500 mt-1" id="lockedFunds">--</div>
            </div>
            <div class="bg-white rounded-lg border border-gray-200 p-4">
                <div class="text-xs text-gray-500 mb-1">Next Scan</div>
                <div class="text-xl font-semibold text-gray-900" id="nextScan">--</div>
                <div class="text-xs text-gray-500 mt-1">Polymarket</div>
            </div>
        </div>

        <!-- Bot Control Panel -->
        <div class="bg-white rounded-lg border border-gray-200 p-5 mb-6">
            <div class="flex items-center justify-between mb-4">
                <div>
                    <h3 class="text-sm font-semibold text-gray-900 mb-1">Bot Control</h3>
                    <p class="text-xs text-gray-500">Manage your trading bot</p>
                </div>
                <div class="flex gap-2">
                    <button onclick="controlBot('start')" class="px-3 py-1.5 bg-success text-white text-xs font-medium rounded-lg hover:bg-green-700" id="startBtn">Start</button>
                    <button onclick="controlBot('stop')" class="px-3 py-1.5 bg-gray-200 text-gray-700 text-xs font-medium rounded-lg hover:bg-gray-300" id="stopBtn">Stop</button>
                    <button onclick="controlBot('restart')" class="px-3 py-1.5 bg-primary text-white text-xs font-medium rounded-lg hover:bg-blue-700" id="restartBtn">Restart</button>
                </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-gray-100">
                <div>
                    <div class="text-xs text-gray-500 mb-1">Status</div>
                    <div class="flex items-center gap-2">
                        <span class="w-1.5 h-1.5 bg-success rounded-full pulse-dot" id="statusDot"></span>
                        <span class="text-sm font-medium text-gray-900" id="botStatus">Loading...</span>
                    </div>
                </div>
                <div>
                    <div class="text-xs text-gray-500 mb-1">Current Activity</div>
                    <div class="text-sm font-medium text-gray-900" id="botActivity">--</div>
                </div>
                <div>
                    <div class="text-xs text-gray-500 mb-1">Last Window</div>
                    <div class="text-sm font-medium text-gray-900" id="lastWindow">--</div>
                </div>
            </div>
        </div>

        <!-- Active Positions -->
        <div class="bg-white rounded-lg border border-gray-200 mb-6">
            <div class="px-5 py-4 border-b border-gray-200">
                <div class="flex items-center justify-between">
                    <div>
                        <h3 class="text-sm font-semibold text-gray-900">Active Positions</h3>
                        <p class="text-xs text-gray-500 mt-0.5" id="activePositionsCount">0 open positions</p>
                    </div>
                    <button class="text-xs text-primary font-medium hover:underline" onclick="loadBets()">View All</button>
                </div>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-5 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Market</th>
                            <th class="px-5 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Position</th>
                            <th class="px-5 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">Size</th>
                            <th class="px-5 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Status</th>
                            <th class="px-5 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Time</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-100" id="activePositionsTable">
                        <tr><td colspan="5" class="px-5 py-8 text-center text-sm text-gray-500">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Recent Activity -->
        <div class="bg-white rounded-lg border border-gray-200">
            <div class="px-5 py-4 border-b border-gray-200">
                <h3 class="text-sm font-semibold text-gray-900">Recent Activity</h3>
            </div>
            <div class="divide-y divide-gray-100" id="activityFeed">
                <div class="px-5 py-3 text-center text-sm text-gray-500">Loading...</div>
            </div>
        </div>
    </main>

    <script>
        let walletAddress = '{{WALLET_ADDRESS}}';
        let refreshInterval = null;

        function formatCurrency(n) {
            if (n == null || n === undefined) return '--';
            const sign = n >= 0 ? '+' : '';
            return sign + '$' + Math.abs(n).toFixed(2);
        }

        function formatAddress(addr) {
            if (!addr) return 'Not configured';
            return addr.substring(0, 10) + '...' + addr.substring(addr.length - 6);
        }

        function timeAgo(iso) {
            if (!iso) return '--';
            const d = new Date(iso);
            const s = (Date.now() - d.getTime()) / 1000;
            if (s < 60) return Math.floor(s) + 's ago';
            if (s < 3600) return Math.floor(s / 60) + 'm ago';
            if (s < 86400) return Math.floor(s / 3600) + 'h ago';
            return Math.floor(s / 86400) + 'd ago';
        }

        // Get API key from localStorage or prompt user
        function getApiKey() {
            let apiKey = localStorage.getItem('dashboard_api_key');
            if (!apiKey) {
                // Prompt for API key on first load
                apiKey = prompt('Enter Dashboard API Key (or leave empty if not configured):');
                if (apiKey) {
                    localStorage.setItem('dashboard_api_key', apiKey);
                }
            }
            return apiKey;
        }

        async function fetchJSON(url) {
            try {
                const apiKey = getApiKey();
                const headers = {};
                if (apiKey) {
                    headers['X-API-Key'] = apiKey;
                }
                
                const r = await fetch(url, { headers });
                
                // Handle 401 Unauthorized
                if (r.status === 401) {
                    localStorage.removeItem('dashboard_api_key');
                    const newKey = prompt('API key required. Enter Dashboard API Key:');
                    if (newKey) {
                        localStorage.setItem('dashboard_api_key', newKey);
                        // Retry with new key
                        headers['X-API-Key'] = newKey;
                        const retry = await fetch(url, { headers });
                        if (!retry.ok) return null;
                        return await retry.json();
                    }
                    return null;
                }
                
                // Handle 429 Rate Limit
                if (r.status === 429) {
                    const data = await r.json();
                    console.warn('Rate limit exceeded:', data.message);
                    return null;
                }
                
                if (!r.ok) {
                    console.error(`API error ${r.status} for ${url}`);
                    return null;
                }
                return await r.json();
            } catch (e) {
                console.error(`Fetch error for ${url}:`, e);
                return null;
            }
        }

        async function refreshDashboard() {
            console.log('Refreshing dashboard...');
            const [stats, balance, pending, botStatus] = await Promise.all([
                fetchJSON('/api/stats'),
                fetchJSON('/api/wallet/balance'),
                fetchJSON('/api/pending'),
                fetchJSON('/api/bot-status')
            ]);

            console.log('API Results:', { stats: !!stats, balance: !!balance, pending: !!pending, botStatus: !!botStatus });

            // Show connection status
            const connected = stats || balance || pending || botStatus;
            if (!connected) {
                document.getElementById('statusBadge').innerHTML = `
                    <span class="w-1.5 h-1.5 bg-danger rounded-full"></span>
                    <span class="text-xs font-medium text-danger">Not Connected</span>
                `;
                console.error('No API data received - check DATABASE_URL on Railway');
            }

            // Update portfolio summary
            if (stats) {
                document.getElementById('totalPortfolio').textContent = formatCurrency(stats.total_portfolio || 0);
                const netPnl = stats.net_pnl || 0;
                const pnlEl = document.getElementById('netPnl');
                pnlEl.textContent = formatCurrency(netPnl) + ' (' + ((netPnl / (stats.starting_balance || 90)) * 100).toFixed(0) + '%)';
                pnlEl.className = 'text-xs mt-1 ' + (netPnl >= 0 ? 'text-success' : 'text-danger');

                document.getElementById('winRate').textContent = (stats.win_rate || 0).toFixed(1) + '%';
                document.getElementById('winRateSub').textContent = (stats.wins || 0) + 'W ' + (stats.losses || 0) + 'L ' + (stats.pending || 0) + 'P';
            }

            // Update balance
            if (balance) {
                document.getElementById('lockedFunds').textContent = '$' + (balance.locked_funds || 0).toFixed(2) + ' locked';
            }

            // Update wallets
            updateWallets(balance, walletAddress);

            // Update active positions
            if (pending && pending.length > 0) {
                document.getElementById('activePositions').textContent = pending.length;
                document.getElementById('activePositionsCount').textContent = pending.length + ' open positions';
                updateActivePositions(pending);
            } else {
                document.getElementById('activePositions').textContent = '0';
                document.getElementById('activePositionsCount').textContent = '0 open positions';
                document.getElementById('activePositionsTable').innerHTML = '<tr><td colspan="5" class="px-5 py-8 text-center text-sm text-gray-500">No active positions</td></tr>';
            }

            // Update bot status
            if (botStatus) {
                updateBotStatus(botStatus);
            } else {
                // Show error if bot status not available
                document.getElementById('botStatus').textContent = 'Not Connected';
                document.getElementById('botActivity').textContent = 'Check DATABASE_URL';
                document.getElementById('statusDot').className = 'w-1.5 h-1.5 bg-danger rounded-full';
            }

            // Update next scan countdown
            if (stats && stats.last_window_at) {
                const nextScan = new Date(stats.last_window_at);
                nextScan.setHours(nextScan.getHours() + 1);
                const diff = nextScan - new Date();
                const minutes = Math.floor(diff / 60000);
                document.getElementById('nextScan').textContent = minutes > 0 ? minutes + 'm' : 'Now';
            } else {
                document.getElementById('nextScan').textContent = '--';
            }
        }

        function updateWallets(balance, address) {
            const container = document.getElementById('walletsContainer');
            const available = balance?.available_balance || 0;
            const locked = balance?.locked_funds || 0;
            const total = available + locked;

            container.innerHTML = `
                <div class="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow">
                    <div class="flex items-start justify-between mb-3">
                        <div>
                            <div class="text-xs font-medium text-gray-500 mb-1">Wallet 1</div>
                            <div class="wallet-address text-gray-700">${formatAddress(address)}</div>
                        </div>
                        <span class="w-2 h-2 bg-success rounded-full pulse-dot"></span>
                    </div>
                    <div class="space-y-2">
                        <div class="flex justify-between text-xs">
                            <span class="text-gray-500">Available</span>
                            <span class="font-semibold text-gray-900">${formatCurrency(available)}</span>
                        </div>
                        <div class="flex justify-between text-xs">
                            <span class="text-gray-500">Locked</span>
                            <span class="font-semibold text-gray-900">${formatCurrency(locked)}</span>
                        </div>
                        <div class="flex justify-between text-xs pt-2 border-t border-gray-100">
                            <span class="text-gray-500">Total</span>
                            <span class="font-semibold text-gray-900">${formatCurrency(total)}</span>
                        </div>
                    </div>
                </div>
                <div class="bg-gray-50 rounded-lg border-2 border-dashed border-gray-300 p-4 flex items-center justify-center hover:border-primary cursor-pointer transition-colors" onclick="alert('Multi-wallet support coming soon')">
                    <div class="text-center">
                        <div class="text-2xl mb-1">+</div>
                        <div class="text-xs font-medium text-gray-500">Add Wallet</div>
                    </div>
                </div>
            `;
        }

        function updateActivePositions(pending) {
            const tbody = document.getElementById('activePositionsTable');
            if (!pending || pending.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="px-5 py-8 text-center text-sm text-gray-500">No active positions</td></tr>';
                return;
            }

            let html = '';
            for (const bet of pending.slice(0, 10)) {
                const market = (bet.market_question || '').substring(0, 50) + ((bet.market_question || '').length > 50 ? '...' : '');
                const side = bet.side || '--';
                const sideClass = side === 'YES' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800';
                html += `
                    <tr class="hover:bg-gray-50">
                        <td class="px-5 py-3">
                            <div class="text-sm font-medium text-gray-900">${market}</div>
                            <div class="text-xs text-gray-500 mt-0.5">Polymarket</div>
                        </td>
                        <td class="px-5 py-3">
                            <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${sideClass}">${side}</span>
                        </td>
                        <td class="px-5 py-3 text-right text-sm font-medium text-gray-900">${formatCurrency(bet.amount)}</td>
                        <td class="px-5 py-3">
                            <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">Pending</span>
                        </td>
                        <td class="px-5 py-3 text-xs text-gray-500">${timeAgo(bet.placed_at)}</td>
                    </tr>
                `;
            }
            tbody.innerHTML = html;
        }

        function updateBotStatus(status) {
            const statusMap = {
                'running': { dot: 'bg-success', text: 'Running', activity: 'Active' },
                'stopped': { dot: 'bg-gray-400', text: 'Stopped', activity: 'Inactive' },
                'idle': { dot: 'bg-yellow-400', text: 'Idle', activity: 'Waiting' },
                'error': { dot: 'bg-danger', text: 'Error', activity: 'Error' },
                'scanning': { dot: 'bg-primary', text: 'Scanning', activity: 'Scanning markets' }
            };

            const s = statusMap[status.status] || statusMap['stopped'];
            const dotEl = document.getElementById('statusDot');
            if (dotEl) {
                dotEl.className = 'w-1.5 h-1.5 ' + s.dot + ' rounded-full' + (status.status === 'running' ? ' pulse-dot' : '');
            }
            const statusEl = document.getElementById('botStatus');
            if (statusEl) statusEl.textContent = s.text;
            const activityEl = document.getElementById('botActivity');
            if (activityEl) activityEl.textContent = status.current_window || status.activity || s.activity;
            const windowEl = document.getElementById('lastWindow');
            if (windowEl) windowEl.textContent = status.current_window || '--';
        }

        async function controlBot(action) {
            const btn = event.target;
            const originalText = btn.textContent;
            btn.disabled = true;
            btn.textContent = 'Processing...';

            try {
                const apiKey = getApiKey();
                const headers = { 'Content-Type': 'application/x-www-form-urlencoded' };
                if (apiKey) {
                    headers['X-API-Key'] = apiKey;
                }
                
                const formData = new URLSearchParams();
                formData.append('action', action);
                
                const response = await fetch('/api/bot-control', {
                    method: 'POST',
                    headers: headers,
                    body: formData
                });
                
                if (response.status === 401) {
                    alert('Authentication required. Please refresh and enter API key.');
                    return;
                }
                
                const result = await response.json();
                alert(result.message || 'Action completed');
                if (action === 'restart') {
                    setTimeout(() => location.reload(), 3000);
                }
            } catch (e) {
                alert('Error: ' + e.message);
            } finally {
                btn.disabled = false;
                btn.textContent = originalText;
            }
        }

        async function loadBets() {
            const bets = await fetchJSON('/api/bets?limit=100');
            // Could open a modal or navigate to bets page
            console.log('Bets loaded:', bets);
        }

        // Initialize
        refreshDashboard();
        refreshInterval = setInterval(refreshDashboard, 15000);
    </script>
</body>
</html>'''
