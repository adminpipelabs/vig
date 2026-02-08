"""
Vig v2 — Always-on Agent. Continuously watches markets, places bets, redeems winners.
No sleep cycles, no circuit breakers, just reactive trading.
"""
import os
import sys
import time
import signal
import logging
import random
from datetime import datetime, timezone
from typing import Set

# Set up logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("vig")

from config import Config
from db import Database
from scanner import Scanner
from snowball import Snowball
from risk_manager import RiskManager
from bet_manager import BetManager
from notifier import Notifier

# Suppress verbose HTTP/2 and HPACK debug logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)

running = True


def signal_handler(sig, frame):
    global running
    logger.info("Shutdown signal received. Finishing current operations...")
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class VigAgent:
    """Always-on trading agent - watches markets continuously"""
    
    def __init__(self, config: Config, db: Database, scanner: Scanner, 
                 bet_mgr: BetManager, snowball: Snowball, risk_mgr: RiskManager,
                 notifier: Notifier, clob_client=None):
        self.config = config
        self.db = db
        self.scanner = scanner
        self.bet_mgr = bet_mgr
        self.snowball = snowball
        self.risk_mgr = risk_mgr
        self.notifier = notifier
        self.clob_client = clob_client
        
        # Track open positions to avoid duplicate bets
        self.open_positions: Set[str] = set()
        self._load_open_positions()
        
        # Stats
        self.cycle_count = 0
        self.last_scan_time = 0
        
    def _load_open_positions(self):
        """Load open positions from database on startup"""
        pending = self.db.get_all_pending_bets()
        self.open_positions = {bet.market_id for bet in pending}
        logger.info(f"Loaded {len(self.open_positions)} open positions from database")
    
    def run(self):
        """Main agent loop - runs continuously"""
        global running
        
        mode = "PAPER" if self.config.paper_mode else "LIVE"
        logger.info(f"=== Vig v2 Agent Starting ({mode} mode) ===")
        logger.info(f"Poll interval: {self.config.poll_interval_seconds}s")
        logger.info(f"Filters: favorite > {self.config.min_favorite_price:.0%}, no volume filter")
        
        self.notifier.startup(mode, self.snowball.state.clip_size, self.snowball.state.phase)
        
        while running:
            try:
                self.cycle_count += 1
                
                # Update heartbeat
                self.db.update_bot_status("main", "running", f"Cycle {self.cycle_count}")
                
                # 1. Check and settle resolved positions
                self._check_and_settle_positions()
                
                # 2. Check and redeem winners (if live mode)
                if not self.config.paper_mode:
                    self._check_and_redeem_winners()
                
                # 3. Scan for new opportunities
                self._scan_and_bet()
                
                # 4. Short pause (not sleep - agent is always watching)
                if running:
                    time.sleep(self.config.poll_interval_seconds)
                    
            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                break
            except Exception as e:
                logger.error(f"[ERROR] Agent cycle error: {e}")
                import traceback
                logger.error(traceback.format_exc())
                self.db.update_bot_status("main", "error", None, str(e)[:200])
                # Continue running - agent never stops
                time.sleep(self.config.poll_interval_seconds)
        
        logger.info("Vig Agent shutting down.")
        self.db.update_bot_status("main", "stopped", None, "Agent stopped")
        self.scanner.close()
        self.db.close()
    
    def _check_and_settle_positions(self):
        """Check all pending bets and settle resolved ones"""
        pending = self.db.get_all_pending_bets()
        if not pending:
            return
        
        logger.debug(f"Checking {len(pending)} pending positions for settlement...")
        settled_count = 0
        
        for bet in pending:
            try:
                if self.config.paper_mode:
                    result_check, payout = self.bet_mgr._simulate_settlement(bet)
                else:
                    result_check, payout = self.bet_mgr._check_live_settlement(bet)
                
                if result_check != "pending":
                    profit = payout - bet.amount if result_check == "won" else -bet.amount
                    self.db.update_bet_result(bet.id, result_check, payout, profit)
                    
                    # Remove from open positions
                    self.open_positions.discard(bet.market_id)
                    
                    emoji = "✅" if result_check == "won" else "❌"
                    logger.info(f"{emoji} Settled: {bet.market_question[:50]} -> {result_check} (${profit:+.2f})")
                    settled_count += 1
            except Exception as e:
                logger.error(f"Error settling bet {bet.id}: {e}")
        
        if settled_count > 0:
            logger.info(f"Settled {settled_count} positions")
    
    def _check_and_redeem_winners(self):
        """Check for won bets that need redemption"""
        try:
            # Get won bets with condition_ids
            if hasattr(self.db, 'conn'):
                conn = self.db.conn
                is_postgres = hasattr(conn, 'server_version')
                
                if is_postgres:
                    from psycopg2.extras import RealDictCursor
                    c = conn.cursor(cursor_factory=RealDictCursor)
                    c.execute("""
                        SELECT COUNT(*) as cnt FROM bets 
                        WHERE paper=false AND result='won' 
                        AND condition_id IS NOT NULL AND condition_id != ''
                    """)
                else:
                    c = conn.cursor()
                    c.execute("""
                        SELECT COUNT(*) as cnt FROM bets 
                        WHERE paper=0 AND result='won' 
                        AND condition_id IS NOT NULL AND condition_id != ''
                    """)
                
                row = c.fetchone()
                won_count = dict(row).get('cnt', 0) if is_postgres else row[0]
                
                if won_count > 0:
                    logger.info(f"💰 {won_count} winning bet(s) ready for redemption")
                    # Note: Actual redemption happens via cron or can be triggered manually
                    # This is just a status check
        except Exception as e:
            logger.debug(f"Could not check redemption status: {e}")
    
    def _scan_and_bet(self):
        """Scan for new markets and place bets"""
        try:
            # Scan for markets
            candidates = self.scanner.scan()
            
            if not candidates:
                return
            
            logger.info(f"Found {len(candidates)} market candidates")
            
            # Filter out markets we already have positions in
            new_candidates = [m for m in candidates if m.market_id not in self.open_positions]
            
            if len(new_candidates) < len(candidates):
                logger.info(f"Filtered out {len(candidates) - len(new_candidates)} markets (already have positions)")
            
            if not new_candidates:
                return
            
            # Limit to max_bets_per_window (but this is now 100, so rarely hits)
            to_bet = new_candidates[:self.config.max_bets_per_window]
            
            # Place bets
            logger.info(f"Placing bets on {len(to_bet)} new markets...")
            bets = self.bet_mgr.place_bets(to_bet, self.cycle_count, 1.0)  # clip_multiplier always 1.0
            
            if bets:
                # Add to open positions
                for bet in bets:
                    self.open_positions.add(bet.market_id)
                
                total_deployed = sum(b.amount for b in bets)
                logger.info(f"✅ Placed {len(bets)} bets, ${total_deployed:.2f} deployed")
                
                # Update snowball (but don't wait for settlement)
                # Settlement happens in next cycle
                self.snowball.process_window(0, len(bets))  # Profit calculated later
        except Exception as e:
            logger.error(f"Error in scan_and_bet: {e}")
            import traceback
            logger.error(traceback.format_exc())


def main():
    global running
    
    # ── Init ──
    config = Config()
    issues = config.validate()
    if issues:
        for i in issues:
            logger.error(f"Config issue: {i}")
        if not config.paper_mode:
            sys.exit(1)
    
    # Use PostgreSQL if DATABASE_URL is set, otherwise SQLite
    database_url = os.getenv("DATABASE_URL")
    db = Database(config.db_path, database_url=database_url)
    scanner = Scanner(config)
    snowball = Snowball(config)
    risk_mgr = RiskManager(config, db)
    notifier = Notifier(config)
    
    # CLOB client only for live mode
    clob_client = None
    if not config.paper_mode:
        try:
            logger.info("Initializing CLOB client...")
            from py_clob_client.client import ClobClient
            
            host = config.clob_url
            key = config.private_key
            chain_id = config.chain_id
            
            clob_client = ClobClient(host, key=key, chain_id=chain_id)
            creds = clob_client.create_or_derive_api_creds()
            clob_client.set_api_creds(creds)
            
            logger.info(f"✅ CLOB client initialized")
        except Exception as e:
            logger.error(f"❌ CLOB client initialization failed: {e}")
            logger.error("Bot will run in SCAN-ONLY mode")
            clob_client = None
    
    bet_mgr = BetManager(config, db, snowball, clob_client)
    
    # ── Restore state ──
    recent_windows = db.get_recent_windows(1)
    if recent_windows:
        last = recent_windows[0]
        snowball.load_state(
            clip_size=last.clip_size,
            phase=last.phase,
            total_pocketed=sum(w.pocketed for w in db.get_recent_windows(999)),
            bankroll=0,
            windows_completed=len(db.get_recent_windows(999)),
        )
        logger.info(f"Restored: clip=${last.clip_size:.2f} phase={last.phase}")
    else:
        logger.info(f"Fresh start: clip=${config.starting_clip:.2f}")
    
    # ── Start agent ──
    agent = VigAgent(config, db, scanner, bet_mgr, snowball, risk_mgr, notifier, clob_client)
    agent.run()


if __name__ == "__main__":
    main()
