# Modern Mobile-Responsive Dashboard UI Plan

## Current State
- ✅ FastAPI backend with good API endpoints
- ✅ Database connection working
- ❌ Old HTML/CSS (not mobile-friendly)
- ❌ No real-time updates
- ❌ No bot control UI

## New UI Requirements

### Core Features
1. **Bot Status & Control**
   - Real-time status (running/stopped/scanning)
   - Start/Stop/Restart buttons
   - Edit strategy settings
   - Live activity feed

2. **Trading Dashboard**
   - Live bets (real-time updates)
   - Scanning markets status
   - Settled bets history
   - Balance breakdown (available, locked, total)

3. **Strategy Settings**
   - Clip size, thresholds
   - Circuit breaker settings
   - Market filters

4. **Mobile-Responsive**
   - Works on phone/tablet
   - Touch-friendly buttons
   - Responsive charts/tables

## Tech Stack Options

### Option 1: Modern HTML + Tailwind CSS (Fastest)
- Keep FastAPI backend
- Replace HTML with Tailwind CSS
- Add WebSocket for real-time
- **Time: 2-3 hours**

### Option 2: React Frontend (Most Modern)
- FastAPI backend (keep as-is)
- React + Vite frontend
- WebSocket for real-time
- **Time: 4-6 hours**

### Option 3: Vue.js Frontend
- FastAPI backend
- Vue 3 + Vite
- WebSocket
- **Time: 4-6 hours**

## Recommendation: Option 1 (Tailwind CSS)

**Why:**
- Fastest to implement
- No build step needed
- Works immediately
- Easy to maintain
- Mobile-responsive by default

**Implementation:**
1. Replace current HTML with Tailwind CSS
2. Add WebSocket endpoint for real-time updates
3. Create mobile-friendly components
4. Add bot control UI

## UI Components Needed

1. **Header**
   - Bot status indicator
   - Balance summary
   - Control buttons

2. **Dashboard Cards**
   - Active bets
   - Recent windows
   - Win rate
   - Total P&L

3. **Bets Table**
   - Live bets (updates via WebSocket)
   - Settled bets
   - Mobile-friendly table

4. **Settings Panel**
   - Strategy config
   - Circuit breaker settings
   - Save/Apply buttons

5. **Activity Feed**
   - Real-time log stream
   - Market scans
   - Bet placements

## Next Steps

1. Create new HTML template with Tailwind CSS
2. Add WebSocket support to FastAPI
3. Build mobile-responsive components
4. Add bot control endpoints
5. Test on mobile devices
