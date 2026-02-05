"""
Vig v1 Database — PostgreSQL storage for bets, windows, and stats.
Migration from SQLite to PostgreSQL for production deployment.
"""
import os
import psycopg2
from psycopg2.extras import RealDictRow
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional

from db import BetRecord, WindowRecord  # Reuse dataclasses


class Database:
    def __init__(self, database_url: str = None):
        """
        Initialize PostgreSQL database connection.
        
        Args:
            database_url: PostgreSQL connection string (postgresql://user:pass@host:port/dbname)
                         If None, falls back to DATABASE_URL env var or SQLite for backward compat
        """
        # Try PostgreSQL first
        if database_url:
            self.database_url = database_url
            self.use_postgres = True
        elif os.getenv("DATABASE_URL"):
            self.database_url = os.getenv("DATABASE_URL")
            self.use_postgres = True
        else:
            # Fallback to SQLite for backward compatibility
            import sqlite3
            self.db_path = os.getenv("DB_PATH", "vig.db")
            self.use_postgres = False
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self._create_tables()
            return
        
        # PostgreSQL connection
        self.conn = psycopg2.connect(self.database_url)
        self.conn.set_session(autocommit=False)
        self._create_tables()

    def _create_tables(self):
        """Create tables if they don't exist (PostgreSQL compatible)"""
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
            
            c.execute("""
                CREATE TABLE IF NOT EXISTS windows (
                    id SERIAL PRIMARY KEY,
                    started_at TEXT,
                    ended_at TEXT,
                    bets_placed INTEGER DEFAULT 0,
                    bets_won INTEGER DEFAULT 0,
                    bets_lost INTEGER DEFAULT 0,
                    bets_pending INTEGER DEFAULT 0,
                    deployed REAL DEFAULT 0,
                    returned REAL DEFAULT 0,
                    profit REAL DEFAULT 0,
                    pocketed REAL DEFAULT 0,
                    clip_size REAL DEFAULT 0,
                    phase TEXT DEFAULT 'growth'
                )
            """)
            
            c.execute("""
                CREATE TABLE IF NOT EXISTS circuit_breaker_log (
                    id SERIAL PRIMARY KEY,
                    triggered_at TEXT,
                    reason TEXT,
                    clip_at_trigger REAL,
                    resolved_at TEXT,
                    action_taken TEXT
                )
            """)
        else:
            # SQLite schema (backward compatibility)
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
            try:
                c.execute("ALTER TABLE bets ADD COLUMN condition_id TEXT")
            except:
                pass
            
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
            c.execute("""
                SELECT * FROM bets 
                WHERE window_id=%s AND result='pending'
                ORDER BY placed_at
            """, (window_id,))
        else:
            c.execute("""
                SELECT * FROM bets 
                WHERE window_id=? AND result='pending'
                ORDER BY placed_at
            """, (window_id,))
        
        rows = c.fetchall()
        return [self._row_to_bet(row) for row in rows]

    def get_all_pending_bets(self) -> list[BetRecord]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM bets WHERE result='pending' ORDER BY placed_at")
        rows = c.fetchall()
        return [self._row_to_bet(row) for row in rows]

    def _row_to_bet(self, row) -> BetRecord:
        """Convert database row to BetRecord"""
        if self.use_postgres:
            return BetRecord(
                id=row['id'],
                window_id=row['window_id'],
                platform=row['platform'],
                market_id=row['market_id'],
                condition_id=row.get('condition_id', ''),
                market_question=row['market_question'],
                token_id=row['token_id'],
                side=row['side'],
                price=row['price'],
                amount=row['amount'],
                size=row['size'],
                order_id=row['order_id'],
                placed_at=row['placed_at'],
                resolved_at=row.get('resolved_at'),
                result=row['result'],
                payout=row['payout'],
                profit=row['profit'],
                paper=bool(row['paper'])
            )
        else:
            return BetRecord(
                id=row['id'],
                window_id=row['window_id'],
                platform=row['platform'],
                market_id=row['market_id'],
                condition_id=row.get('condition_id', ''),
                market_question=row['market_question'],
                token_id=row['token_id'],
                side=row['side'],
                price=row['price'],
                amount=row['amount'],
                size=row['size'],
                order_id=row['order_id'],
                placed_at=row['placed_at'],
                resolved_at=row.get('resolved_at'),
                result=row['result'],
                payout=row['payout'],
                profit=row['profit'],
                paper=bool(row['paper'])
            )

    def get_window_bets(self, window_id: int) -> list[BetRecord]:
        c = self.conn.cursor()
        if self.use_postgres:
            c.execute("SELECT * FROM bets WHERE window_id=%s", (window_id,))
        else:
            c.execute("SELECT * FROM bets WHERE window_id=?", (window_id,))
        rows = c.fetchall()
        return [self._row_to_bet(row) for row in rows]

    def get_recent_bets(self, n: int = 100) -> list[BetRecord]:
        c = self.conn.cursor()
        if self.use_postgres:
            c.execute("SELECT * FROM bets WHERE result!='pending' ORDER BY id DESC LIMIT %s", (n,))
        else:
            c.execute("SELECT * FROM bets WHERE result!='pending' ORDER BY id DESC LIMIT ?", (n,))
        rows = c.fetchall()
        return [self._row_to_bet(row) for row in rows]

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
        if self.use_postgres:
            return dict(row) if row else {}
        else:
            return dict(row) if row else {}

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
        if not row:
            return None
        if self.use_postgres:
            return WindowRecord(**{k: row[k] for k in row.keys()})
        else:
            return WindowRecord(**{k: row[k] for k in row.keys()})

    def get_recent_windows(self, n: int = 20) -> list[WindowRecord]:
        c = self.conn.cursor()
        if self.use_postgres:
            c.execute("SELECT * FROM windows ORDER BY id DESC LIMIT %s", (n,))
        else:
            c.execute("SELECT * FROM windows ORDER BY id DESC LIMIT ?", (n,))
        rows = c.fetchall()
        return [WindowRecord(**{k: row[k] for k in row.keys()}) for row in rows]

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
