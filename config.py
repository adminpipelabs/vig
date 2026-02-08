"""
Vig v1 Configuration
"""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    gamma_url: str = "https://gamma-api.polymarket.com"
    clob_url: str = "https://clob.polymarket.com"
    chain_id: int = 137

    private_key: str = field(default_factory=lambda: os.getenv("POLYGON_PRIVATE_KEY", ""))
    funder_address: str = field(default_factory=lambda: os.getenv("POLYGON_FUNDER_ADDRESS", ""))
    signature_type: int = int(os.getenv("SIGNATURE_TYPE", "0"))

    # Vig v2: Agent-based approach - relaxed filters for high volume
    min_favorite_price: float = float(os.getenv("MIN_FAVORITE_PRICE", "0.50"))  # Was 0.70
    max_favorite_price: float = float(os.getenv("MAX_FAVORITE_PRICE", "0.99"))  # Was 0.90
    expiry_window_minutes: int = int(os.getenv("EXPIRY_WINDOW_MINUTES", "1440"))  # 24 hours - no expiry filter
    max_bets_per_window: int = int(os.getenv("MAX_BETS_PER_WINDOW", "100"))  # Was 10
    starting_clip: float = float(os.getenv("STARTING_CLIP", "10.0"))
    max_clip: float = float(os.getenv("MAX_CLIP", "100.0"))
    snowball_reinvest_pct: float = 0.50

    max_volume_pct: float = 0.02
    min_volume_abs: float = float(os.getenv("MIN_VOLUME_ABS", "0"))  # Was 100 - no volume filter

    # Circuit breaker removed - agent never stops itself
    circuit_breaker_consecutive_losses: int = 999  # Disabled
    circuit_breaker_daily_loss_pct: float = 1.0  # Disabled (100% loss allowed)
    circuit_breaker_win_rate_threshold: float = 0.0  # Disabled
    circuit_breaker_win_rate_lookback: int = 100
    circuit_breaker_window_max_losses: int = 999  # Disabled

    # Agent always-on polling (not scheduled scans)
    poll_interval_seconds: int = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))  # Was 3600 (60 min)
    scan_interval_seconds: int = int(os.getenv("SCAN_INTERVAL_SECONDS", "10"))  # Keep for backward compat
    settle_check_interval_seconds: int = 30
    settle_timeout_seconds: int = 60 * 90

    paper_mode: bool = bool(os.getenv("PAPER_MODE", "true").lower() in ("true", "1", "yes"))
    dry_run: bool = bool(os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes"))

    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))

    db_path: str = os.getenv("DB_PATH", "vig.db")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    def validate(self) -> list[str]:
        issues = []
        if not self.paper_mode:
            if not self.private_key:
                issues.append("POLYGON_PRIVATE_KEY required for live trading")
        if self.min_favorite_price >= self.max_favorite_price:
            issues.append("min_favorite_price must be < max_favorite_price")
        if self.max_clip < self.starting_clip:
            issues.append("max_clip must be >= starting_clip")
        return issues
