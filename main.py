"""
Vig v1 — Main loop. Scan → Bet → Settle → Snowball → Repeat.
"""

import os
import sys
import time
import signal
import logging
import random
from datetime import datetime, timezone

from datetime import datetime, timezone

# Set up logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("vig")

from config import Config
from db import Database, WindowRecord
from scanner import Scanner
from snowball import Snowball
from risk_manager import RiskManager
from bet_manager import BetManager
from notifier import Notifier
# Bot status now handled via database heartbeat (db.update_bot_status)

# Suppress verbose HTTP/2 and HPACK debug logs from httpx/httpcore
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)

running = True


def signal_handler(sig, frame):
    global running
    logger.info("Shutdown signal received. Finishing current window...")
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


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
