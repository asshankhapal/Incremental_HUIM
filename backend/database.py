"""
SQLite database initialisation, schema creation, and connection helpers.
"""

import sqlite3
from contextlib import contextmanager
from config import config

def _get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with WAL mode enabled."""
    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

@contextmanager
def get_db():
    """Context manager that yields a DB connection and commits on success."""
    conn = _get_connection()
    
    # Auto-initialize database tables if missing
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='batches';"
        )
        if not cursor.fetchone():
            init_db()
    except Exception:
        pass

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db() -> None:
    """Create all tables if they do not exist."""
    conn = _get_connection()
    try:
        conn.executescript(
            """
            -- ── Batches ─────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS batches (
                batch_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                status      TEXT    NOT NULL DEFAULT 'queued'
            );

            -- ── Transactions ────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS transactions (
                tid         INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id    INTEGER NOT NULL,
                items       TEXT    NOT NULL,   -- JSON array of item names
                utilities   TEXT    NOT NULL,   -- JSON array of utility values
                FOREIGN KEY (batch_id) REFERENCES batches(batch_id)
            );
            CREATE INDEX IF NOT EXISTS idx_txn_batch
                ON transactions(batch_id);

            -- ── Prefix Utility & MRU state ──────────────────────────
            CREATE TABLE IF NOT EXISTS prefix_utility (
                item        TEXT PRIMARY KEY,
                value       REAL NOT NULL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS global_mru (
                item        TEXT PRIMARY KEY,
                value       REAL NOT NULL DEFAULT 0.0
            );

            -- ── Pattern Tracker (Phase 5 HashMap) ───────────────────
            CREATE TABLE IF NOT EXISTS pattern_tracker (
                pattern_key     TEXT    PRIMARY KEY,
                total_util      REAL    NOT NULL DEFAULT 0.0,
                count           INTEGER NOT NULL DEFAULT 0,
                avg_util        REAL    NOT NULL DEFAULT 0.0,
                last_seen_batch INTEGER NOT NULL DEFAULT 0
            );

            -- ── Pipeline Run Log ────────────────────────────────────
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                finished_at TEXT,
                status      TEXT    NOT NULL DEFAULT 'running',
                details     TEXT                                -- JSON blob
            );
            """
        )
    finally:
        conn.close()


def clear_db() -> None:
    """Clear all data from all tables to start fresh."""
    init_db()
    with get_db() as conn:
        conn.execute("DELETE FROM transactions;")
        conn.execute("DELETE FROM batches;")
        conn.execute("DELETE FROM prefix_utility;")
        conn.execute("DELETE FROM global_mru;")
        conn.execute("DELETE FROM pattern_tracker;")
        conn.execute("DELETE FROM pipeline_runs;")
        conn.execute(
            "DELETE FROM sqlite_sequence WHERE name IN ('batches', 'transactions', 'pipeline_runs');"
        )

