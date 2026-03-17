"""SQLite database models for activity logging and app configuration.

Uses aiosqlite for async operations with a simple schema:
- activity_log: Tracks every action (email sent, status update, etc.)
- app_config: Key-value store for runtime configuration
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

DB_PATH = Path(settings.database_path)


def get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Create tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            action_type TEXT NOT NULL,
            firm_name TEXT,
            firm_row INTEGER,
            email_to TEXT,
            email_subject TEXT,
            status_from TEXT,
            status_to TEXT,
            details TEXT,
            dry_run INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        )
    """)

    # Create index for faster lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_activity_firm
        ON activity_log (firm_name, action_type)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_activity_timestamp
        ON activity_log (timestamp DESC)
    """)

    conn.commit()
    conn.close()
    logger.info("Database initialized.")


def log_activity(
    action_type: str,
    firm_name: str = "",
    firm_row: int | None = None,
    email_to: str = "",
    email_subject: str = "",
    status_from: str = "",
    status_to: str = "",
    details: str = "",
    dry_run: bool = False,
):
    """Insert an activity log entry."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO activity_log
        (timestamp, action_type, firm_name, firm_row, email_to, email_subject,
         status_from, status_to, details, dry_run)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now().isoformat(),
            action_type,
            firm_name,
            firm_row,
            email_to,
            email_subject,
            status_from,
            status_to,
            details,
            1 if dry_run else 0,
        ),
    )

    conn.commit()
    conn.close()


def get_activity_log(
    limit: int = 100,
    offset: int = 0,
    action_type: str | None = None,
    firm_name: str | None = None,
) -> list[dict]:
    """Retrieve activity log entries.

    Args:
        limit: Max number of entries.
        offset: Pagination offset.
        action_type: Filter by action type.
        firm_name: Filter by firm name.

    Returns:
        List of log entry dicts, newest first.
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM activity_log WHERE 1=1"
    params: list = []

    if action_type:
        query += " AND action_type = ?"
        params.append(action_type)
    if firm_name:
        query += " AND firm_name LIKE ?"
        params.append(f"%{firm_name}%")

    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def count_followups_for_firm(firm_name: str) -> int:
    """Count how many follow-up emails have been sent to a specific firm."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*) as count FROM activity_log
        WHERE firm_name = ? AND action_type = 'followup_sent' AND dry_run = 0
        """,
        (firm_name,),
    )

    result = cursor.fetchone()
    conn.close()
    return result["count"] if result else 0


def has_been_emailed(firm_name: str) -> bool:
    """Check if a firm has already been emailed (for duplicate prevention)."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*) as count FROM activity_log
        WHERE firm_name = ? AND action_type IN ('initial_email_sent', 'followup_sent')
        AND dry_run = 0
        """,
        (firm_name,),
    )

    result = cursor.fetchone()
    conn.close()
    return (result["count"] or 0) > 0


def get_config(key: str, default: str = "") -> str:
    """Get a config value."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM app_config WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default


def set_config(key: str, value: str):
    """Set a config value."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO app_config (key, value, updated_at)
        VALUES (?, ?, ?)
        """,
        (key, value, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
