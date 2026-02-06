"""
Vig v1 Database — SQLite/PostgreSQL storage for bets, windows, and stats.
Automatically uses PostgreSQL if DATABASE_URL is set, otherwise falls back to SQLite.
"""
import os
import sqlite3
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional

# Try to import PostgreSQL driver
try:
    import psycopg2
    from psycopg2.extras import RealDictRow
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False


@dataclass
class BetRecord:
    id: Optional[int] = None
    window_id: int = 0
    platform: str = "polymarket"
    market_id: str = ""
    condition_id: str = ""  # Added for redemption
    market_question: str = ""
    token_id: str = ""
    side: str = ""
    price: float = 0.0
    amount: float = 0.0
    size: float = 0.0
    order_id: str = ""
    placed_at: str = ""
    resolved_at: str = ""
    result: str = "pending"
    payout: float = 0.0
    profit: float = 0.0
    paper: bool = True


@dataclass
class WindowRecord:
    id: Optional[int] = None
    started_at: str = ""
    ended_at: str = ""
    bets_placed: int = 0
    bets_won: int = 0
    bets_lost: int = 0
    bets_pending: int = 0
    deployed: float = 0.0
    returned: float = 0.0
    profit: float = 0.0
    pocketed: float = 0.0
    clip_size: float = 0.0
    phase: str = "growth"


class Database:
    def __init__(self, db_path: str = None, database_url: str = None):
        """
        Initialize database connection.
        
        Args:
            db_path: SQLite database path (for backward compatibility)
            database_url: PostgreSQL connection string (postgresql://user:pass@host:port/dbname)
        
        Priority:
        1. database_url parameter
        2. DATABASE_URL environment variable
        3. db_path parameter or DB_PATH env var
        4. Default: "vig.db" (SQLite)
        """
        # Check for PostgreSQL
        if database_url or os.getenv("DATABASE_URL"):
            if not POSTGRES_AVAILABLE:
                raise ImportError("PostgreSQL requested but psycopg2 not installed. Run: pip install psycopg2-binary")
            self.use_postgres = True
            self.database_url = database_url or os.getenv("DATABASE_URL")
            # Set RealDictCursor at connection time (matches SQLite Row behavior)
            from psycopg2.extras import RealDictCursor
            self.conn = psycopg2.connect(self.database_url, cursor_factory=RealDictCursor)
            self.conn.set_session(autocommit=False)
        else:
            # Use SQLite (backward compatibility)
            self.use_postgres = False
            self.db_path = db_path or os.getenv("DB_PATH", "vig.db")
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        
        self._create_tables()

    def _create_tables(self):
        c = self.conn.cursor()
        
        if self.use_postgres:
            # PostgreSQL schema
            c.execute("""
                CREATE TABLE IF NOT EXISTS bets (
                    id SERIAL PRIMARY KEY,
                    window_id INTEGER,
                    platform TEXT,
                    market_id TEXT,
                    condition_id TEXT,
                    market_question TEXT,
                    token_id TEXT,
                    side TEXT,
                    price REAL,
                    amount REAL,
                    size REAL,
                    order_id TEXT,
                    placed_at TEXT,
                    resolved_at TEXT,
                    result TEXT DEFAULT 'pending',
                    payout REAL DEFAULT 0,
                    profit REAL DEFAULT 0,
                    paper BOOLEAN DEFAULT TRUE
                )
            """)
        else:
            # SQLite schema
            c.execute("""
                CREATE TABLE IF NOT EXISTS bets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    window_id INTEGER, platform TEXT, market_id TEXT,
                    condition_id TEXT, market_question TEXT, token_id TEXT, side TEXT,
                    price REAL, amount REAL, size REAL, order_id TEXT,
                    placed_at TEXT, resolved_at TEXT,
                    result TEXT DEFAULT 'pending',
                    payout REAL DEFAULT 0, profit REAL DEFAULT 0,
                    paper INTEGER DEFAULT 1
                )
            """)
            # Add condition_id column if it doesn't exist (for existing databases)
            try:
                c.execute("ALTER TABLE bets ADD COLUMN condition_id TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
        if self.use_postgres:
            c.execute("""
                CREATE TABLE IF NOT EXISTS windows (
                    id SERIAL PRIMARY KEY,
                    started_at TEXT, ended_at TEXT,
                    bets_placed INTEGER DEFAULT 0, bets_won INTEGER DEFAULT 0,
                    bets_lost INTEGER DEFAULT 0, bets_pending INTEGER DEFAULT 0,
                    deployed REAL DEFAULT 0, returned REAL DEFAULT 0,
                    profit REAL DEFAULT 0, pocketed REAL DEFAULT 0,
                    clip_size REAL DEFAULT 0, phase TEXT DEFAULT 'growth'
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS circuit_breaker_log (
                    id SERIAL PRIMARY KEY,
                    triggered_at TEXT, reason TEXT, clip_at_trigger REAL,
                    resolved_at TEXT, action_taken TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS bot_status (
                    id TEXT PRIMARY KEY,
                    last_heartbeat TIMESTAMP,
                    status TEXT,
                    current_window TEXT,
                    error_message TEXT,
                    scan_count INTEGER DEFAULT 0
                )
            """)
        else:
            c.execute("""
                CREATE TABLE IF NOT EXISTS windows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT, ended_at TEXT,
                    bets_placed INTEGER DEFAULT 0, bets_won INTEGER DEFAULT 0,
                    bets_lost INTEGER DEFAULT 0, bets_pending INTEGER DEFAULT 0,
                    deployed REAL DEFAULT 0, returned REAL DEFAULT 0,
                    profit REAL DEFAULT 0, pocketed REAL DEFAULT 0,
                    clip_size REAL DEFAULT 0, phase TEXT DEFAULT 'growth'
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS circuit_breaker_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    triggered_at TEXT, reason TEXT, clip_at_trigger REAL,
                    resolved_at TEXT, action_taken TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS bot_status (
                    id TEXT PRIMARY KEY,
                    last_heartbeat TEXT,
                    status TEXT,
                    current_window TEXT,
                    error_message TEXT,
                    scan_count INTEGER DEFAULT 0
                )
            """)
        self.conn.commit()

    def insert_bet(self, bet: BetRecord) -> int:
        c = self.conn.cursor()
        if self.use_postgres:
            c.execute("""
                INSERT INTO bets (window_id, platform, market_id, condition_id, market_question, token_id,
                                  side, price, amount, size, order_id, placed_at, resolved_at,
                                  result, payout, profit, paper)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (bet.window_id, bet.platform, bet.market_id, bet.condition_id, bet.market_question,
                  bet.token_id, bet.side, bet.price, bet.amount, bet.size,
                  bet.order_id, bet.placed_at, bet.resolved_at, bet.result,
                  bet.payout, bet.profit, bet.paper))
            row = c.fetchone()
            bet_id = row['id'] if row else None
        else:
            c.execute("""
                INSERT INTO bets (window_id, platform, market_id, condition_id, market_question, token_id,
                                  side, price, amount, size, order_id, placed_at, resolved_at,
                                  result, payout, profit, paper)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (bet.window_id, bet.platform, bet.market_id, bet.condition_id, bet.market_question,
                  bet.token_id, bet.side, bet.price, bet.amount, bet.size,
                  bet.order_id, bet.placed_at, bet.resolved_at, bet.result,
                  bet.payout, bet.profit, int(bet.paper)))
            bet_id = c.lastrowid
        self.conn.commit()
        return bet_id

    def update_bet_result(self, bet_id: int, result: str, payout: float, profit: float):
        now = datetime.now(timezone.utc).isoformat()
        c = self.conn.cursor()
        if self.use_postgres:
            c.execute("UPDATE bets SET result=%s, payout=%s, profit=%s, resolved_at=%s WHERE id=%s",
                     (result, payout, profit, now, bet_id))
        else:
            c.execute("UPDATE bets SET result=?, payout=?, profit=?, resolved_at=? WHERE id=?",
                     (result, payout, profit, now, bet_id))
        self.conn.commit()

    def get_pending_bets(self, window_id: int) -> list[BetRecord]:
        c = self.conn.cursor()  # cursor_factory already set globally for PostgreSQL
        if self.use_postgres:
            c.execute("SELECT * FROM bets WHERE window_id=%s AND result='pending'", (window_id,))
        else:
            c.execute("SELECT * FROM bets WHERE window_id=? AND result='pending'", (window_id,))
        return [self._row_to_bet(r) for r in c.fetchall()]

    def get_window_bets(self, window_id: int) -> list[BetRecord]:
        c = self.conn.cursor()  # cursor_factory already set globally for PostgreSQL
        if self.use_postgres:
            c.execute("SELECT * FROM bets WHERE window_id=%s", (window_id,))
        else:
            c.execute("SELECT * FROM bets WHERE window_id=?", (window_id,))
        return [self._row_to_bet(r) for r in c.fetchall()]

    def get_recent_bets(self, n: int = 100) -> list[BetRecord]:
        c = self.conn.cursor()  # cursor_factory already set globally for PostgreSQL
        if self.use_postgres:
            c.execute("SELECT * FROM bets WHERE result!='pending' ORDER BY id DESC LIMIT %s", (n,))
        else:
            c.execute("SELECT * FROM bets WHERE result!='pending' ORDER BY id DESC LIMIT ?", (n,))
        return [self._row_to_bet(r) for r in c.fetchall()]
    
    def get_all_pending_bets(self) -> list[BetRecord]:
        """Get all pending bets regardless of window_id"""
        c = self.conn.cursor()  # cursor_factory already set globally for PostgreSQL
        if self.use_postgres:
            c.execute("SELECT * FROM bets WHERE result='pending' ORDER BY id ASC")
        else:
            c.execute("SELECT * FROM bets WHERE result='pending' ORDER BY id ASC")
        return [self._row_to_bet(r) for r in c.fetchall()]

    def get_all_stats(self) -> dict:
        c = self.conn.cursor()
        c.execute("""
            SELECT COUNT(*) as total_bets,
                SUM(CASE WHEN result='won' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result='lost' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN result='pending' THEN 1 ELSE 0 END) as pending,
                SUM(profit) as total_profit, SUM(payout) as total_payout,
                SUM(amount) as total_deployed
            FROM bets
        """)
        row = c.fetchone()
        return dict(row) if row else {}

    def _row_to_bet(self, row) -> BetRecord:
        # Convert to dict if needed (PostgreSQL RealDictRow is already dict-like, SQLite Row is dict-like, but tuples need conversion)
        if isinstance(row, dict):
            return BetRecord(**row)
        elif hasattr(row, 'keys'):
            return BetRecord(**{k: row[k] for k in row.keys()})
        else:
            # Fallback for tuple rows (shouldn't happen with RealDictCursor, but safe fallback)
            # This assumes standard column order - not ideal but prevents crashes
            return BetRecord(
                id=row[0] if len(row) > 0 else None,
                window_id=row[1] if len(row) > 1 else 0,
                platform=row[2] if len(row) > 2 else "polymarket",
                market_id=row[3] if len(row) > 3 else "",
                condition_id=row[4] if len(row) > 4 else "",
                market_question=row[5] if len(row) > 5 else "",
                token_id=row[6] if len(row) > 6 else "",
                side=row[7] if len(row) > 7 else "",
                price=row[8] if len(row) > 8 else 0.0,
                amount=row[9] if len(row) > 9 else 0.0,
                size=row[10] if len(row) > 10 else 0.0,
                order_id=row[11] if len(row) > 11 else "",
                placed_at=row[12] if len(row) > 12 else "",
                resolved_at=row[13] if len(row) > 13 else "",
                result=row[14] if len(row) > 14 else "pending",
                payout=row[15] if len(row) > 15 else 0.0,
                profit=row[16] if len(row) > 16 else 0.0,
                paper=bool(row[17]) if len(row) > 17 else True
            )

    def insert_window(self, window: WindowRecord) -> int:
        c = self.conn.cursor()
        if self.use_postgres:
            c.execute("""
                INSERT INTO windows (started_at, ended_at, bets_placed, bets_won, bets_lost,
                                     bets_pending, deployed, returned, profit, pocketed,
                                     clip_size, phase)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (window.started_at, window.ended_at, window.bets_placed,
                  window.bets_won, window.bets_lost, window.bets_pending,
                  window.deployed, window.returned, window.profit,
                  window.pocketed, window.clip_size, window.phase))
            row = c.fetchone()
            window_id = row['id'] if row else None
        else:
            c.execute("""
                INSERT INTO windows (started_at, ended_at, bets_placed, bets_won, bets_lost,
                                     bets_pending, deployed, returned, profit, pocketed,
                                     clip_size, phase)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (window.started_at, window.ended_at, window.bets_placed,
                  window.bets_won, window.bets_lost, window.bets_pending,
                  window.deployed, window.returned, window.profit,
                  window.pocketed, window.clip_size, window.phase))
            window_id = c.lastrowid
        self.conn.commit()
        return window_id

    def update_window(self, window_id: int, **kwargs):
        if self.use_postgres:
            sets = ", ".join(f"{k}=%s" for k in kwargs)
            vals = list(kwargs.values()) + [window_id]
            c = self.conn.cursor()
            c.execute(f"UPDATE windows SET {sets} WHERE id=%s", vals)
        else:
            sets = ", ".join(f"{k}=?" for k in kwargs)
            vals = list(kwargs.values()) + [window_id]
            c = self.conn.cursor()
            c.execute(f"UPDATE windows SET {sets} WHERE id=?", vals)
        self.conn.commit()

    def get_window(self, window_id: int) -> Optional[WindowRecord]:
        c = self.conn.cursor()  # cursor_factory already set globally for PostgreSQL
        if self.use_postgres:
            c.execute("SELECT * FROM windows WHERE id=%s", (window_id,))
        else:
            c.execute("SELECT * FROM windows WHERE id=?", (window_id,))
        row = c.fetchone()
        if row:
            row_dict = dict(row) if not isinstance(row, dict) else row
            return WindowRecord(**row_dict)
        return None

    def get_recent_windows(self, n: int = 20) -> list[WindowRecord]:
        c = self.conn.cursor()  # cursor_factory already set globally for PostgreSQL
        if self.use_postgres:
            c.execute("SELECT * FROM windows ORDER BY id DESC LIMIT %s", (n,))
        else:
            c.execute("SELECT * FROM windows ORDER BY id DESC LIMIT ?", (n,))
        rows = c.fetchall()
        # Convert to dict if needed (PostgreSQL RealDictRow is already dict-like, SQLite Row is dict-like)
        return [WindowRecord(**dict(row)) for row in rows]

    def log_circuit_breaker(self, reason: str, clip: float, action: str):
        now = datetime.now(timezone.utc).isoformat()
        c = self.conn.cursor()
        if self.use_postgres:
            c.execute("INSERT INTO circuit_breaker_log (triggered_at, reason, clip_at_trigger, action_taken) VALUES (%s,%s,%s,%s)",
                     (now, reason, clip, action))
        else:
            c.execute("INSERT INTO circuit_breaker_log (triggered_at, reason, clip_at_trigger, action_taken) VALUES (?,?,?,?)",
                     (now, reason, clip, action))
        self.conn.commit()

    def get_consecutive_losses(self) -> int:
        c = self.conn.cursor()  # cursor_factory already set globally for PostgreSQL
        c.execute("SELECT result FROM bets WHERE result!='pending' ORDER BY id DESC")
        streak = 0
        for row in c.fetchall():
            row_dict = dict(row) if not isinstance(row, dict) else row
            if row_dict.get("result") == "lost":
                streak += 1
            else:
                break
        return streak

    def update_bot_status(self, bot_id: str = "main", status: str = "running", 
                         current_window: str = None, error_message: str = None, 
                         scan_count: int = None):
        """
        Update bot heartbeat/status in database.
        
        Args:
            bot_id: Bot identifier (default: "main")
            status: Current status ("running", "scanning", "idle", "error")
            current_window: Current window ID or description
            error_message: Error message if status is "error"
            scan_count: Number of scans completed
        """
        c = self.conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        
        if self.use_postgres:
            # PostgreSQL: Use NOW() for timestamp
            c.execute("""
                INSERT INTO bot_status (id, last_heartbeat, status, current_window, error_message, scan_count)
                VALUES (%s, NOW(), %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    last_heartbeat = NOW(),
                    status = EXCLUDED.status,
                    current_window = EXCLUDED.current_window,
                    error_message = EXCLUDED.error_message,
                    scan_count = COALESCE(EXCLUDED.scan_count, bot_status.scan_count)
            """, (bot_id, status, current_window, error_message, scan_count))
        else:
            # SQLite: Use ISO string
            c.execute("""
                INSERT INTO bot_status (id, last_heartbeat, status, current_window, error_message, scan_count)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    last_heartbeat = excluded.last_heartbeat,
                    status = excluded.status,
                    current_window = excluded.current_window,
                    error_message = excluded.error_message,
                    scan_count = COALESCE(excluded.scan_count, bot_status.scan_count)
            """, (bot_id, now, status, current_window, error_message, scan_count))
        
        self.conn.commit()

    def get_bot_status(self, bot_id: str = "main"):
        """
        Get bot status from database.
        
        Returns:
            dict with status, last_heartbeat, current_window, error_message, scan_count
            or None if bot never started
        """
        c = self.conn.cursor()
        
        if self.use_postgres:
            c.execute("SELECT * FROM bot_status WHERE id = %s", (bot_id,))
        else:
            c.execute("SELECT * FROM bot_status WHERE id = ?", (bot_id,))
        
        row = c.fetchone()
        if row:
            return dict(row) if not isinstance(row, dict) else row
        return None

    def close(self):
        self.conn.close()
