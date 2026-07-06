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
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    except sqlite3.DatabaseError as e:
        if "malformed" in str(e).lower():
            logger.error(f"Database at {DB_PATH} is malformed: {e}. Attempting self-healing by deletion.")
            for suffix in ["", "-wal", "-shm"]:
                path = DB_PATH + suffix
                if os.path.exists(path):
                    try:
                        os.remove(path)
                        logger.info(f"Deleted malformed database file: {path}")
                    except Exception as rm_err:
                        logger.error(f"Failed to delete {path}: {rm_err}")
            # Retry connection once
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn
        else:
            raise


def migrate_schema(conn):
    """
    Thêm các columns mới vào bảng cũ nếu chưa có.
    SQLite không hỗ trợ ADD COLUMN IF NOT EXISTS nên phải try/except.
    """
    migrations = [
        "ALTER TABLE trade_history ADD COLUMN position_size_pct REAL DEFAULT 0.0",
        "ALTER TABLE trade_history ADD COLUMN risk_amount_usd    REAL DEFAULT 0.0",
        "ALTER TABLE trade_history ADD COLUMN expected_value_r   REAL DEFAULT 0.0",
        "ALTER TABLE trade_history ADD COLUMN market_regime      TEXT DEFAULT 'unknown'",
        "ALTER TABLE trade_history ADD COLUMN btc_structure      TEXT DEFAULT 'neutral'",
        "ALTER TABLE trade_history ADD COLUMN session_name       TEXT DEFAULT 'unknown'",
        "ALTER TABLE trade_history ADD COLUMN family             TEXT DEFAULT 'unknown'",
        "ALTER TABLE trade_history ADD COLUMN confidence_score   REAL DEFAULT 0.0",
        "ALTER TABLE trade_history ADD COLUMN signal_id          TEXT DEFAULT ''",
        # paper_positions table cũng cần migrate tương tự
        "ALTER TABLE paper_positions ADD COLUMN position_size_pct  REAL DEFAULT 0.0",
        "ALTER TABLE paper_positions ADD COLUMN position_size_usd  REAL DEFAULT 0.0",
        "ALTER TABLE paper_positions ADD COLUMN risk_amount_usd    REAL DEFAULT 0.0",
        "ALTER TABLE paper_positions ADD COLUMN expected_value_r   REAL DEFAULT 0.0",
        "ALTER TABLE paper_positions ADD COLUMN market_regime      TEXT DEFAULT 'unknown'",
        "ALTER TABLE paper_positions ADD COLUMN btc_structure      TEXT DEFAULT 'neutral'",
        "ALTER TABLE paper_positions ADD COLUMN session_name       TEXT DEFAULT 'unknown'",
        "ALTER TABLE paper_positions ADD COLUMN confidence_score   REAL DEFAULT 0.0",
        "ALTER TABLE paper_positions ADD COLUMN risk_reward_ratio  REAL DEFAULT 0.0",
        "ALTER TABLE paper_positions ADD COLUMN family             TEXT DEFAULT 'unknown'",
        "ALTER TABLE paper_positions ADD COLUMN interval           TEXT DEFAULT 'unknown'",
        "ALTER TABLE paper_positions ADD COLUMN cooldown_key       TEXT DEFAULT ''",
        "ALTER TABLE paper_positions ADD COLUMN signal_id          TEXT DEFAULT ''",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except Exception:
            pass   # Column đã tồn tại → bỏ qua
    conn.commit()


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
            signal_source TEXT NOT NULL DEFAULT 'unknown',
            position_size_pct  REAL DEFAULT 0.0,
            position_size_usd  REAL DEFAULT 0.0,
            risk_amount_usd    REAL DEFAULT 0.0,
            expected_value_r   REAL DEFAULT 0.0,
            market_regime      TEXT DEFAULT 'unknown',
            btc_structure      TEXT DEFAULT 'neutral',
            session_name       TEXT DEFAULT 'unknown',
            confidence_score   REAL DEFAULT 0.0,
            risk_reward_ratio  REAL DEFAULT 0.0,
            family             TEXT DEFAULT 'unknown',
            interval           TEXT DEFAULT 'unknown',
            cooldown_key       TEXT DEFAULT '',
            signal_id          TEXT DEFAULT ''
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
            signal_source TEXT NOT NULL DEFAULT 'unknown',
            position_size_pct  REAL DEFAULT 0.0,
            risk_amount_usd    REAL DEFAULT 0.0,
            expected_value_r   REAL DEFAULT 0.0,
            market_regime      TEXT DEFAULT 'unknown',
            btc_structure      TEXT DEFAULT 'neutral',
            session_name       TEXT DEFAULT 'unknown',
            family             TEXT DEFAULT 'unknown',
            confidence_score   REAL DEFAULT 0.0,
            signal_id          TEXT DEFAULT '',
            created_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS signal_snapshots (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol     TEXT NOT NULL,
            signal_id  TEXT NOT NULL,
            snapshot   TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS strategy_specs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol      TEXT NOT NULL,
            strategy    TEXT NOT NULL,
            spec_json   TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_strategy_specs_symbol
            ON strategy_specs(symbol, strategy);

        CREATE TABLE IF NOT EXISTS playbook_packets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol      TEXT NOT NULL,
            strategy    TEXT NOT NULL,
            packet_json TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_playbook_symbol
            ON playbook_packets(symbol, strategy);

        CREATE TABLE IF NOT EXISTS ranking_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol          TEXT NOT NULL,
            strategy_name   TEXT NOT NULL,
            composite_score REAL NOT NULL,
            perf_score      REAL NOT NULL,
            robust_score    REAL NOT NULL,
            decay_score     REAL NOT NULL,
            complexity_score REAL NOT NULL,
            decision        TEXT NOT NULL,
            net_pnl         REAL NOT NULL DEFAULT 0.0,
            win_rate        REAL NOT NULL DEFAULT 0.0,
            recorded_at     TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ranking_history_symbol
            ON ranking_history(symbol, strategy_name);

        CREATE TABLE IF NOT EXISTS validation_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol          TEXT NOT NULL,
            decay_detected  INTEGER NOT NULL DEFAULT 0,
            code_valid      INTEGER NOT NULL DEFAULT 1,
            validation_json TEXT NOT NULL,
            recorded_at     TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_validation_history_symbol
            ON validation_history(symbol);

        CREATE TABLE IF NOT EXISTS equity_curve (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            balance    REAL NOT NULL,
            equity     REAL NOT NULL,
            open_positions INTEGER NOT NULL DEFAULT 0,
            unrealized_pnl REAL NOT NULL DEFAULT 0.0,
            recorded_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_equity_curve_time
            ON equity_curve(recorded_at);

        CREATE TABLE IF NOT EXISTS system_events (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type   TEXT NOT NULL,
            value        TEXT NOT NULL,
            triggered_by TEXT NOT NULL DEFAULT 'system',
            recorded_at  TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_system_events_type
            ON system_events(event_type);

        CREATE TABLE IF NOT EXISTS order_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol       TEXT NOT NULL,
            direction    TEXT NOT NULL,
            quantity     REAL NOT NULL,
            price        REAL NOT NULL,
            stop_loss    REAL,
            take_profit  REAL,
            signal_source TEXT NOT NULL DEFAULT 'unknown',
            accepted     INTEGER NOT NULL DEFAULT 0,
            reject_reason TEXT,
            attempted_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_order_log_symbol
            ON order_log(symbol);

        CREATE INDEX IF NOT EXISTS idx_signal_snapshots_symbol 
            ON signal_snapshots(symbol, signal_id);
        CREATE INDEX IF NOT EXISTS idx_trade_history_symbol 
            ON trade_history(symbol);
        """)
        migrate_schema(conn)
    conn.close()
    import os
    env = os.getenv("APP_ENV", "production")
    if "SPACE_ID" in os.environ:
        env = "production"
    persistent = os.path.isdir("/data")
    logger.info(f"[DB] Initialized SQLite at {DB_PATH} | Env: {env.upper()} | Persistent: {persistent}")


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
                 unrealized_pnl, signal_source,
                 position_size_pct, position_size_usd, risk_amount_usd, expected_value_r,
                 market_regime, btc_structure, session_name, confidence_score,
                 risk_reward_ratio, family, interval, cooldown_key, signal_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                signal_source=excluded.signal_source,
                position_size_pct=excluded.position_size_pct,
                position_size_usd=excluded.position_size_usd,
                risk_amount_usd=excluded.risk_amount_usd,
                expected_value_r=excluded.expected_value_r,
                market_regime=excluded.market_regime,
                btc_structure=excluded.btc_structure,
                session_name=excluded.session_name,
                confidence_score=excluded.confidence_score,
                risk_reward_ratio=excluded.risk_reward_ratio,
                family=excluded.family,
                interval=excluded.interval,
                cooldown_key=excluded.cooldown_key,
                signal_id=excluded.signal_id
        """, (
            pos["symbol"], pos["direction"], pos["quantity"],
            pos["entry_price"], pos["current_price"],
            pos.get("stop_loss"), pos.get("take_profit"),
            pos["entry_time"], pos.get("entry_fee", 0.0),
            pos.get("unrealized_pnl", 0.0), pos.get("signal_source", "unknown"),
            pos.get("position_size_pct", 0.0), pos.get("position_size_usd", 0.0),
            pos.get("risk_amount_usd", 0.0), pos.get("expected_value_r", 0.0),
            pos.get("market_regime", "unknown"), pos.get("btc_structure", "neutral"),
            pos.get("session_name", "unknown"), pos.get("confidence_score", 0.0),
            pos.get("risk_reward_ratio", 0.0), pos.get("family", "unknown"),
            pos.get("interval", "unknown"), pos.get("cooldown_key", ""),
            pos.get("signal_id", "")
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
                 entry_time, exit_time, pnl, fees, reason, signal_source,
                 position_size_pct, risk_amount_usd, expected_value_r,
                 market_regime, btc_structure, session_name, family, confidence_score, signal_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            trade["symbol"], trade["direction"], trade["quantity"],
            trade["entry_price"], trade["exit_price"],
            trade["entry_time"], trade["exit_time"],
            trade["pnl"], trade.get("fees", 0.0),
            trade.get("reason", "Market Close"),
            trade.get("signal_source", "unknown"),
            trade.get("position_size_pct", 0.0),
            trade.get("risk_amount_usd", 0.0),
            trade.get("expected_value_r", 0.0),
            trade.get("market_regime", "unknown"),
            trade.get("btc_structure", "neutral"),
            trade.get("session_name", "unknown"),
            trade.get("family", "unknown"),
            trade.get("confidence_score", 0.0),
            trade.get("signal_id", "")
        ))
    conn.close()


def load_trade_history(limit: int = 200) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM trade_history ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ── Strategy specs ────────────────────────────────────────────────────────────

def save_strategy_spec(symbol: str, strategy: str, spec: dict):
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO strategy_specs (symbol, strategy, spec_json, created_at)
            VALUES (?, ?, ?, ?)
        """, (symbol, strategy, json.dumps(spec), datetime.now(UTC).isoformat()))
    conn.close()

def load_latest_strategy_specs(limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT spec_json FROM strategy_specs
        ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [json.loads(r["spec_json"]) for r in rows]

# ── Playbook packets ──────────────────────────────────────────────────────────

def save_playbook_packet(symbol: str, strategy: str, packet: dict):
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO playbook_packets (symbol, strategy, packet_json, created_at)
            VALUES (?, ?, ?, ?)
        """, (symbol, strategy, json.dumps(packet), datetime.now(UTC).isoformat()))
    conn.close()

def load_latest_playbook_packets(limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT packet_json FROM playbook_packets
        ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [json.loads(r["packet_json"]) for r in rows]

# ── Ranking history ───────────────────────────────────────────────────────────

def save_ranking_snapshot(ranked_items: list):
    """Save one full ranking snapshot (all strategies at this moment)."""
    if not ranked_items:
        return
    conn = get_connection()
    now = datetime.now(UTC).isoformat()
    with conn:
        conn.executemany("""
            INSERT INTO ranking_history
                (symbol, strategy_name, composite_score, perf_score,
                 robust_score, decay_score, complexity_score,
                 decision, net_pnl, win_rate, recorded_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, [(
            r["symbol"], r["strategy_name"],
            r["composite_score"], r["perf_score"],
            r["robust_score"], r["decay_score"], r["complexity_score"],
            r["decision"], r["net_pnl"], r["win_rate"], now
        ) for r in ranked_items])
    conn.close()

def load_ranking_history(symbol: str | None = None, limit: int = 500) -> List[Dict[str, Any]]:
    conn = get_connection()
    if symbol:
        rows = conn.execute("""
            SELECT * FROM ranking_history WHERE symbol=?
            ORDER BY id DESC LIMIT ?
        """, (symbol, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM ranking_history ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Validation history ────────────────────────────────────────────────────────

def save_validation_snapshot(symbol: str, validation_packet: dict):
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO validation_history
                (symbol, decay_detected, code_valid, validation_json, recorded_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            symbol,
            int(validation_packet.get("decay_detected", False)),
            int(validation_packet.get("code_valid", True)),
            json.dumps(validation_packet),
            datetime.now(UTC).isoformat()
        ))
    conn.close()

def load_validation_history(symbol: str, limit: int = 200) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM validation_history WHERE symbol=?
        ORDER BY id DESC LIMIT ?
    """, (symbol, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Auto-Pruning ──────────────────────────────────────────────────────────────

def prune_old_records(keep_days: int = 30):
    """Delete records older than keep_days to prevent DB bloat.
    Safe to call on startup or periodically."""
    from datetime import timedelta
    cutoff = (datetime.now(UTC) - timedelta(days=keep_days)).isoformat()
    conn = get_connection()
    with conn:
        for table in ("strategy_specs", "playbook_packets",
                      "ranking_history", "validation_history",
                      "signal_snapshots", "equity_curve",
                      "system_events", "order_log"):
            try:
                conn.execute(
                    f"DELETE FROM {table} WHERE created_at < ? OR recorded_at < ? OR attempted_at < ?",
                    (cutoff, cutoff, cutoff)
                )
            except Exception:
                pass  # column name differs — skip silently
    conn.close()
    logger.info(f"[DB] Pruned records older than {keep_days} days")


# ── Equity curve ──────────────────────────────────────────────────────────────

def save_equity_point(balance: float, equity: float,
                      open_positions: int, unrealized_pnl: float):
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO equity_curve
                (balance, equity, open_positions, unrealized_pnl, recorded_at)
            VALUES (?, ?, ?, ?, ?)
        """, (balance, equity, open_positions,
              unrealized_pnl, datetime.now(UTC).isoformat()))
    conn.close()

def load_equity_curve(limit: int = 1440) -> List[Dict[str, Any]]:
    """Load last N equity points. Default 1440 = 24h at 1-min intervals."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT balance, equity, open_positions, unrealized_pnl, recorded_at
        FROM equity_curve ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return list(reversed([dict(r) for r in rows]))

# ── System events ─────────────────────────────────────────────────────────────

def save_system_event(event_type: str, value: str, triggered_by: str = "system"):
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO system_events (event_type, value, triggered_by, recorded_at)
            VALUES (?, ?, ?, ?)
        """, (event_type, value, triggered_by, datetime.now(UTC).isoformat()))
    conn.close()

def load_latest_system_event(event_type: str) -> Optional[str]:
    """Return the most recent value for a given event_type."""
    conn = get_connection()
    row = conn.execute("""
        SELECT value FROM system_events
        WHERE event_type = ?
        ORDER BY id DESC LIMIT 1
    """, (event_type,)).fetchone()
    conn.close()
    return row["value"] if row else None

def load_system_events(limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM system_events ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Order log ─────────────────────────────────────────────────────────────────

def save_order_log(symbol: str, direction: str, quantity: float,
                   price: float, stop_loss: float | None,
                   take_profit: float | None, signal_source: str,
                   accepted: bool, reject_reason: str | None = None):
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO order_log
                (symbol, direction, quantity, price, stop_loss, take_profit,
                 signal_source, accepted, reject_reason, attempted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (symbol, direction, quantity, price, stop_loss, take_profit,
              signal_source, int(accepted), reject_reason,
              datetime.now(UTC).isoformat()))
    conn.close()

def load_order_log(limit: int = 200) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM order_log ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
