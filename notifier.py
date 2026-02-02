"""
Vig v1 Notifier — Telegram alerts.
"""
import logging
import httpx
from config import Config

logger = logging.getLogger("vig.notifier")


class Notifier:
    def __init__(self, config: Config):
        self.config = config
        self.enabled = bool(config.telegram_bot_token and config.telegram_chat_id)
        if not self.enabled:
            logger.info("Telegram not configured -- notifications disabled")

    def send(self, message):
        if not self.enabled:
            return
        url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
        try:
            httpx.post(url, json={"chat_id": self.config.telegram_chat_id,
                                   "text": message, "parse_mode": "HTML"}, timeout=10)
        except Exception as e:
            logger.warning(f"Telegram error: {e}")

    def window_summary(self, window_num, bets, wins, losses, profit,
                       pocketed, clip, phase, total_pocketed, win_rate):
        p = f"+${profit:.2f}" if profit >= 0 else f"-${abs(profit):.2f}"
        e = "G" if profit >= 0 else "R"
        self.send(f"[{e}] Window {window_num}\n{bets} bets | {wins}W {losses}L\n"
                  f"Profit: {p}\nClip: ${clip:.2f} ({phase})\n"
                  f"Win Rate: {win_rate:.1f}%\nTotal: ${total_pocketed:.2f}")

    def circuit_breaker(self, reason, action):
        self.send(f"!! CIRCUIT BREAKER\nReason: {reason}\nAction: {action}")

    def milestone(self, message):
        self.send(f"MILESTONE: {message}")

    def startup(self, mode, clip, phase):
        self.send(f"Vig Started | {mode} | ${clip:.2f} | {phase}")
