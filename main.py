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

    mode = "PAPER" if config.paper_mode else "LIVE"
    logger.info(f"=== Vig v1 Starting ({mode} mode) ===")

    # Use PostgreSQL if DATABASE_URL is set, otherwise SQLite
    database_url = os.getenv("DATABASE_URL")
    db = Database(config.db_path, database_url=database_url)
    scanner = Scanner(config)
    snowball = Snowball(config)
    risk_mgr = RiskManager(config, db)
    notifier = Notifier(config)

    # CLOB client only for live mode
    # Initialize CLOB client for live trading
    clob_client = None
    if not config.paper_mode:
        try:
            logger.info("Initializing CLOB client...")
            from py_clob_client.client import ClobClient
            
            host = config.clob_url
            key = config.private_key
            chain_id = config.chain_id
            
            # Create client
            clob_client = ClobClient(host, key=key, chain_id=chain_id)
            
            # Test the connection by creating API creds (this makes an HTTP request)
            logger.info("Testing CLOB connection by creating API credentials...")
            creds = clob_client.create_or_derive_api_creds()
            clob_client.set_api_creds(creds)
            
            logger.info(f"✅ CLOB client initialized (direct connection)")
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"❌ CLOB client initialization failed: {e}")
            logger.error(f"Full error traceback:\n{error_details}")
            
            # Check for specific error types
            error_str = str(e).lower()
            if "timeout" in error_str or "connection" in error_str:
                logger.error("Connection failed - check network connectivity")
            elif "ssl" in error_str or "certificate" in error_str:
                logger.error("SSL/TLS error - check network configuration")
            elif "403" in error_str or "401" in error_str or "cloudflare" in error_str:
                logger.error("Request blocked - check CLOB API access")
            else:
                logger.error(f"Unknown error: {e}")
            
            logger.error("=" * 60)
            logger.error("⚠️  CLOB CLIENT NOT AVAILABLE")
            logger.error("Bot will run in SCAN-ONLY mode:")
            logger.error("  - ✅ Will scan markets and log candidates")
            logger.error("  - ❌ Will NOT place bets")
            logger.error("  - ✅ Dashboard will show scanning activity")
            logger.error("=" * 60)
            logger.error("To enable betting:")
            logger.error("  1. Verify network connectivity to CLOB API")
            logger.error("  2. Check CLOB API credentials and access")
            logger.error("  3. Review error details above for specific issue")
            logger.error("=" * 60)
            clob_client = None

    bet_mgr = BetManager(config, db, snowball, clob_client)

    # ── Restore state from last window ──
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

    notifier.startup(mode, snowball.state.clip_size, snowball.state.phase)

    window_count = len(db.get_recent_windows(999))

    # ── Main loop ──
    while running:
        try:
            window_count += 1
            logger.info(f"\n{'='*50}")
            logger.info(f"WINDOW {window_count}")
            logger.info(f"{'='*50}")
            
            # Update bot heartbeat: starting window
            db.update_bot_status("main", "scanning", f"Window {window_count}")

            # 0. Settle pending bets FIRST (before circuit breaker check)
            # This allows win rate to improve even if bot was stopped
            all_pending = db.get_all_pending_bets()
            if all_pending:
                logger.info(f"Settling {len(all_pending)} pending bets before risk check...")
                db.update_bot_status("main", "scanning", f"Window {window_count} - Settling {len(all_pending)} pending bets")
                settled_count = 0
                for bet in all_pending:
                    try:
                        logger.debug(f"[SETTLEMENT] Checking bet {bet.id}: {bet.market_question[:50]}")
                        if config.paper_mode:
                            result_check, payout = bet_mgr._simulate_settlement(bet)
                        else:
                            result_check, payout = bet_mgr._check_live_settlement(bet)
                        logger.debug(f"[SETTLEMENT] Bet {bet.id} result: {result_check}, payout: {payout}")
                        
                        if result_check != "pending":
                            profit = payout - bet.amount if result_check == "won" else -bet.amount
                            db.update_bet_result(bet.id, result_check, payout, profit)
                            emoji = "W" if result_check == "won" else "L"
                            logger.info(f"  [{emoji}] Settled pending bet: {bet.market_question[:40]} -> {result_check}")
                            settled_count += 1
                        else:
                            logger.debug(f"[SETTLEMENT] Bet {bet.id} still pending")
                    except Exception as e:
                        logger.error(f"[SETTLEMENT] ERROR on bet {bet.id} ({bet.market_question[:40]}): {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                if settled_count > 0:
                    logger.info(f"✅ Settled {settled_count} pending bets before risk check")

            # 1. Pre-window risk check (circuit breaker removed - bot continues trading)
            alerts = risk_mgr.check_pre_window()
            # Circuit breaker removed - bot will continue trading regardless of win rate

            clip_multiplier = risk_mgr.get_clip_multiplier(alerts)
            if clip_multiplier < 1.0:
                logger.warning(f"Risk: clip reduced to {clip_multiplier:.0%}")

            # 2. Scan markets
            logger.info("Scanning Polymarket for expiring markets...")
            db.update_bot_status("main", "scanning", f"Window {window_count}")
            candidates = scanner.scan()
            db.update_bot_status("main", "scanning", f"Window {window_count} - Found {len(candidates)} markets")

            if not candidates:
                logger.info("No qualifying markets found. Waiting for next window.")
                db.update_bot_status("main", "idle", f"Window {window_count} - No markets found")
                # Continue to finally block for sleep
                continue

            # 3. Place bets FIRST (before creating window record)
            logger.info(f"Placing bets on {len(candidates)} markets...")
            db.update_bot_status("main", "scanning", f"Window {window_count} - Placing bets")
            # Use window_count as temporary ID - will update after window creation
            bets = bet_mgr.place_bets(candidates, window_count, clip_multiplier)

            if not bets:
                logger.info("No bets placed (all filtered out).")
                db.update_bot_status("main", "idle", f"Window {window_count} - No bets placed")
                # Continue to finally block for sleep
                continue

            # 4. Create window record ONLY after confirming bets will be placed
            now = datetime.now(timezone.utc).isoformat()
            window = WindowRecord(
                started_at=now,
                clip_size=snowball.state.clip_size,
                phase=snowball.state.phase,
            )
            window_id = db.insert_window(window)
            
            # Update bets with correct window_id
            for bet in bets:
                db.conn.execute("UPDATE bets SET window_id = ? WHERE id = ?", (window_id, bet.id))
            db.conn.commit()

            total_deployed = sum(b.amount for b in bets)
            db.update_window(window_id, bets_placed=len(bets), deployed=total_deployed)
            logger.info(f"Placed {len(bets)} bets, ${total_deployed:.2f} deployed")
            db.update_bot_status("main", "scanning", f"Window {window_id} - {len(bets)} bets placed, waiting for settlement")

            # 5. Wait for settlement
            if config.paper_mode:
                logger.info("Paper mode: settling immediately...")
                time.sleep(2)
            else:
                logger.info("Waiting for markets to resolve...")
                timeout = config.settle_timeout_seconds
                check_interval = config.settle_check_interval_seconds
                elapsed = 0
                while elapsed < timeout and running:
                    pending = db.get_pending_bets(window_id)
                    if not pending:
                        break
                    db.update_bot_status("main", "scanning", f"Window {window_id} - Waiting for {len(pending)} bets to settle")
                    time.sleep(check_interval)
                    elapsed += check_interval
                    if elapsed % 300 == 0:
                        logger.info(f"  Still waiting... {len(pending)} pending, {elapsed}s elapsed")

            # 6. Settle bets from current window
            logger.info("Settling bets from current window...")
            db.update_bot_status("main", "scanning", f"Window {window_id} - Settling bets")
            # Settle bets from current window (old pending bets already settled upfront)
            result = bet_mgr.settle_bets(window_id)

            wins = result["wins"]
            losses = result["losses"]
            window_profit = result["profit"]
            returned = result.get("returned", 0)

            logger.info(f"Results: {wins}W {losses}L | Profit: ${window_profit:.2f}")
            db.update_bot_status("main", "idle", f"Window {window_id} complete: {wins}W {losses}L")
            
            # Check if there are winnings to redeem (non-blocking, just log)
            if wins > 0 and not config.paper_mode:
                try:
                    won_bets = db.conn.execute(
                        "SELECT COUNT(*) FROM bets WHERE paper=? AND result='won' AND condition_id IS NOT NULL AND condition_id != ''",
                        (0 if not config.paper_mode else 1,)
                    ).fetchone()[0]
                    if won_bets > 0:
                        logger.info(f"💰 {won_bets} winning bet(s) ready for redemption. Auto-redemption runs every 2 hours via cron.")
                except Exception as e:
                    logger.debug(f"Could not check redemption status: {e}")

            # 7. Snowball
            sb_result = snowball.process_window(window_profit, len(bets))
            pocketed = sb_result["pocketed"]

            # 8. Update window record
            db.update_window(window_id,
                ended_at=datetime.now(timezone.utc).isoformat(),
                bets_won=wins, bets_lost=losses, bets_pending=result.get("still_pending", 0),
                returned=returned, profit=window_profit,
                pocketed=pocketed, clip_size=sb_result["new_clip"],
                phase=sb_result["phase"],
            )

            # 9. Post-window risk check
            post_alerts = risk_mgr.check_post_window(losses)
            for a in post_alerts:
                logger.warning(str(a))

            # 10. Report
            stats = db.get_all_stats()
            total_resolved = (stats.get("wins") or 0) + (stats.get("losses") or 0)
            win_rate = ((stats.get("wins") or 0) / total_resolved * 100) if total_resolved > 0 else 0

            logger.info(f"")
            logger.info(f"  Window {window_count}: {wins}W {losses}L")
            logger.info(f"  Profit: ${window_profit:.2f} | Pocketed: ${pocketed:.2f}")
            logger.info(f"  Clip: ${sb_result['new_clip']:.2f} ({sb_result['phase']})")
            logger.info(f"  Win Rate: {win_rate:.1f}% over {total_resolved} bets")
            logger.info(f"  Total Pocketed: ${snowball.state.total_pocketed:.2f}")

            notifier.window_summary(
                window_count, len(bets), wins, losses,
                window_profit, pocketed, sb_result["new_clip"],
                sb_result["phase"], snowball.state.total_pocketed, win_rate,
            )

            if sb_result.get("hit_max"):
                notifier.milestone(f"Hit ${config.max_clip:.0f} max clip! Switching to HARVEST mode.")

        except Exception as e:
            logger.error(f"[ERROR] Main loop error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            db.update_bot_status("main", "error", None, str(e)[:200])
        finally:
            # 11. Sleep until next window (guaranteed to run even on errors)
            if running:
                sleep_start = datetime.now(timezone.utc)
                # Add random jitter to scan interval (±30 seconds) to avoid predictable patterns
                import random
                jitter = random.uniform(-30, 30)
                sleep_time = max(60, config.scan_interval_seconds + jitter)  # Minimum 60 seconds
                logger.info(f"[SLEEP] Sleeping {sleep_time:.0f}s (base: {config.scan_interval_seconds}s + {jitter:+.0f}s jitter) at {sleep_start.strftime('%H:%M:%S')} UTC")
                db.update_bot_status("main", "idle", f"Sleeping {sleep_time:.0f}s until next scan")
                # Sleep in chunks to allow graceful shutdown
                remaining = int(sleep_time)
                while remaining > 0 and running:
                    sleep_chunk = min(remaining, 60)  # Check every 60 seconds
                    time.sleep(sleep_chunk)
                    remaining -= sleep_chunk
                sleep_end = datetime.now(timezone.utc)
                sleep_duration = (sleep_end - sleep_start).total_seconds()
                logger.info(f"[SLEEP] Woke up at {sleep_end.strftime('%H:%M:%S')} UTC (slept {sleep_duration:.0f}s)")

    # Cleanup
    logger.info("Vig shutting down.")
    db.update_bot_status("main", "stopped", None, "Bot stopped")
    scanner.close()
    db.close()


if __name__ == "__main__":
    main()
