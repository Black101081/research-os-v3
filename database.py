"""
Persistence layer — SQLite via /data/research.db
HuggingFace Persistent Storage mounts at /data (Space must have it enabled).
Falls back to ./research.db locally.
"""
from __future__ import annotations
import sqlite3
import json
import os
import logging
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = "/data/research.db" if os.path.isdir("/data") else "./research.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if not exist. Safe to call on every startup."""
    conn = get_connection()
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS paper_broker_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            balance REAL NOT NULL DEFAULT 10000.0,
            equity  REAL NOT NULL DEFAULT 10000.0,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS paper_positions (
            symbol        TEXT PRIMARY KEY,
            direction     TEXT NOT NULL,
            quantity      REAL NOT NULL,
            entry_price   REAL NOT NULL,
            current_price REAL NOT NULL,
            stop_loss     REAL,
            take_profit   REAL,
            entry_time    TEXT NOT NULL,
            entry_fee     REAL NOT NULL DEFAULT 0.0,
            unrealized_pnl REAL NOT NULL DEFAULT 0.0,
            signal_source TEXT NOT NULL DEFAULT 'unknown'
        );

        CREATE TABLE IF NOT EXISTS trade_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol       TEXT NOT NULL,
            direction    TEXT NOT NULL,
            quantity     REAL NOT NULL,
            entry_price  REAL NOT NULL,
            exit_price   REAL NOT NULL,
            entry_time   TEXT NOT NULL,
            exit_time    TEXT NOT NULL,
            pnl          REAL NOT NULL,
            fees         REAL NOT NULL DEFAULT 0.0,
            reason       TEXT NOT NULL DEFAULT 'Market Close',
            signal_source TEXT NOT NULL DEFAULT 'unknown'
        );

        CREATE TABLE IF NOT EXISTS signal_snapshots (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol     TEXT NOT NULL,
            signal_id  TEXT NOT NULL,
            snapshot   TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_signal_snapshots_symbol 
            ON signal_snapshots(symbol, signal_id);
        CREATE INDEX IF NOT EXISTS idx_trade_history_symbol 
            ON trade_history(symbol);
        """)
    conn.close()
    logger.info(f"[DB] Initialized SQLite at {DB_PATH}")


# ── PaperBroker persistence helpers ──────────────────────────────────────────

def save_broker_state(balance: float, equity: float):
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO paper_broker_state (id, balance, equity, updated_at)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                balance=excluded.balance,
                equity=excluded.equity,
                updated_at=excluded.updated_at
        """, (balance, equity, datetime.now(UTC).isoformat()))
    conn.close()


def load_broker_state() -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute(
        "SELECT balance, equity FROM paper_broker_state WHERE id=1"
    ).fetchone()
    conn.close()
    if row:
        return {"balance": row["balance"], "equity": row["equity"]}
    return None


def save_position(pos: Dict[str, Any]):
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO paper_positions
                (symbol, direction, quantity, entry_price, current_price,
                 stop_loss, take_profit, entry_time, entry_fee,
                 unrealized_pnl, signal_source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(symbol) DO UPDATE SET
                direction=excluded.direction,
                quantity=excluded.quantity,
                entry_price=excluded.entry_price,
                current_price=excluded.current_price,
                stop_loss=excluded.stop_loss,
                take_profit=excluded.take_profit,
                entry_time=excluded.entry_time,
                entry_fee=excluded.entry_fee,
                unrealized_pnl=excluded.unrealized_pnl,
                signal_source=excluded.signal_source
        """, (
            pos["symbol"], pos["direction"], pos["quantity"],
            pos["entry_price"], pos["current_price"],
            pos.get("stop_loss"), pos.get("take_profit"),
            pos["entry_time"], pos.get("entry_fee", 0.0),
            pos.get("unrealized_pnl", 0.0), pos.get("signal_source", "unknown")
        ))
    conn.close()


def delete_position(symbol: str):
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM paper_positions WHERE symbol=?", (symbol,))
    conn.close()


def load_positions() -> Dict[str, Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM paper_positions").fetchall()
    conn.close()
    return {row["symbol"]: dict(row) for row in rows}


def save_trade(trade: Dict[str, Any]):
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO trade_history
                (symbol, direction, quantity, entry_price, exit_price,
                 entry_time, exit_time, pnl, fees, reason, signal_source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            trade["symbol"], trade["direction"], trade["quantity"],
            trade["entry_price"], trade["exit_price"],
            trade["entry_time"], trade["exit_time"],
            trade["pnl"], trade.get("fees", 0.0),
            trade.get("reason", "Market Close"),
            trade.get("signal_source", "unknown")
        ))
    conn.close()


def load_trade_history(limit: int = 200) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM trade_history ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
