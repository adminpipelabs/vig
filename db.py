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
            self.conn = psycopg2.connect(self.database_url)
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
            bet_id = c.fetchone()[0]
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
        c = self.conn.cursor()
        if self.use_postgres:
            c.execute("SELECT * FROM bets WHERE window_id=%s AND result='pending'", (window_id,))
        else:
            c.execute("SELECT * FROM bets WHERE window_id=? AND result='pending'", (window_id,))
        return [self._row_to_bet(r) for r in c.fetchall()]

    def get_window_bets(self, window_id: int) -> list[BetRecord]:
        c = self.conn.cursor()
        if self.use_postgres:
            c.execute("SELECT * FROM bets WHERE window_id=%s", (window_id,))
        else:
            c.execute("SELECT * FROM bets WHERE window_id=?", (window_id,))
        return [self._row_to_bet(r) for r in c.fetchall()]

    def get_recent_bets(self, n: int = 100) -> list[BetRecord]:
        c = self.conn.cursor()
        if self.use_postgres:
            c.execute("SELECT * FROM bets WHERE result!='pending' ORDER BY id DESC LIMIT %s", (n,))
        else:
            c.execute("SELECT * FROM bets WHERE result!='pending' ORDER BY id DESC LIMIT ?", (n,))
        return [self._row_to_bet(r) for r in c.fetchall()]
    
    def get_all_pending_bets(self) -> list[BetRecord]:
        """Get all pending bets regardless of window_id"""
        c = self.conn.cursor()
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
        return BetRecord(**{k: row[k] for k in row.keys()})

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
            window_id = c.fetchone()[0]
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
        c = self.conn.cursor()
        if self.use_postgres:
            c.execute("SELECT * FROM windows WHERE id=%s", (window_id,))
        else:
            c.execute("SELECT * FROM windows WHERE id=?", (window_id,))
        row = c.fetchone()
        return WindowRecord(**{k: row[k] for k in row.keys()}) if row else None

    def get_recent_windows(self, n: int = 20) -> list[WindowRecord]:
        if self.use_postgres:
            from psycopg2.extras import RealDictCursor
            c = self.conn.cursor(cursor_factory=RealDictCursor)
            c.execute("SELECT * FROM windows ORDER BY id DESC LIMIT %s", (n,))
        else:
            c = self.conn.cursor()
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
        c = self.conn.cursor()
        c.execute("SELECT result FROM bets WHERE result!='pending' ORDER BY id DESC")
        streak = 0
        for row in c.fetchall():
            if row["result"] == "lost":
                streak += 1
            else:
                break
        return streak

    def close(self):
        self.conn.close()
