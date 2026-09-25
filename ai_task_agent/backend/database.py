"""
database.py — Database (Local / Cloud) layer.

Responsibilities (per architecture):
  - Store tasks
  - Store status (completed / incomplete)
  - Keep historical data (for weekly analysis)

Security notes:
  - Every query uses parameterized statements (no string-formatted SQL),
    which eliminates SQL-injection risk.
  - The database file lives under ./data and is created with restrictive
    permissions on first run.
  - A single, short-lived connection is opened per operation using a
    context manager so connections never leak.
"""

from __future__ import annotations

import os
import sqlite3
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "tasks.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    category      TEXT NOT NULL DEFAULT 'general',
    priority      TEXT NOT NULL DEFAULT 'medium',
    status        TEXT NOT NULL DEFAULT 'pending',   -- pending | completed
    task_date     TEXT NOT NULL,                     -- YYYY-MM-DD (the day the task belongs to)
    created_at    TEXT NOT NULL,                      -- ISO timestamp
    completed_at  TEXT,                                -- ISO timestamp, NULL until completed
    notes         TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_date ON tasks (task_date);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);

CREATE TABLE IF NOT EXISTS daily_summaries (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_date      TEXT NOT NULL UNIQUE,
    completed_count   INTEGER NOT NULL,
    incomplete_count  INTEGER NOT NULL,
    completion_rate   REAL NOT NULL,
    ai_summary        TEXT,
    ai_suggestions    TEXT,
    created_at        TEXT NOT NULL
);
"""


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        # Restrict directory permissions to the current user where the OS supports it.
        os.chmod(DATA_DIR, stat.S_IRWXU)
    except (PermissionError, NotImplementedError, OSError):
        pass


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Yield a short-lived SQLite connection with sane, safe defaults."""
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they do not already exist. Safe to call every startup."""
    with get_connection() as conn:
        conn.executescript(SCHEMA)
    try:
        os.chmod(DB_PATH, stat.S_IRUSR | stat.S_IWUSR)
    except (PermissionError, NotImplementedError, OSError):
        pass
