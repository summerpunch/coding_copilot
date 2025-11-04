"""Session management and database operations for CLI."""

import sqlite3
import uuid
from datetime import datetime
from typing import Optional, List
from pathlib import Path
import os


class ChatSession:
    """Represents a single chat session."""

    def __init__(
        self,
        thread_id: Optional[str] = None,
        mode: str = "edit",
        created_at: Optional[datetime] = None,
        last_used: Optional[datetime] = None,
        message_count: int = 0,
        title: Optional[str] = None,
    ):
        self.thread_id = thread_id or str(uuid.uuid4())
        self.mode = mode
        self.created_at = created_at or datetime.now()
        self.last_used = last_used or datetime.now()
        self.message_count = message_count
        self.title = title or f"Session {self.thread_id[:8]}"

    def __str__(self):
        return f"Session {self.thread_id[:8]}... ({self.mode})"


class SessionDatabase:
    """Manages session persistence in SQLite database."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize session database.

        Args:
            db_path: Path to SQLite database. If None, uses copilot_checkpoints.sqlite
        """
        if db_path is None:
            db_path = os.path.join(os.getcwd(), "copilot_checkpoints.sqlite")

        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """Create sessions table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                thread_id TEXT PRIMARY KEY,
                mode TEXT NOT NULL DEFAULT 'edit',
                created_at TIMESTAMP NOT NULL,
                last_used TIMESTAMP NOT NULL,
                message_count INTEGER DEFAULT 0,
                title TEXT
            )
        """)

        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_last_used
            ON sessions(last_used DESC)
        """)

        conn.commit()
        conn.close()

    def save_session(self, session: ChatSession) -> None:
        """Save or update a session in the database.

        Args:
            session: ChatSession to save
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO sessions
            (thread_id, mode, created_at, last_used, message_count, title)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session.thread_id,
            session.mode,
            session.created_at.isoformat(),
            session.last_used.isoformat(),
            session.message_count,
            session.title,
        ))

        conn.commit()
        conn.close()

    def get_session(self, thread_id: str) -> Optional[ChatSession]:
        """Retrieve a session by thread_id.

        Args:
            thread_id: Thread ID to look up

        Returns:
            ChatSession if found, None otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT thread_id, mode, created_at, last_used, message_count, title
            FROM sessions
            WHERE thread_id = ?
        """, (thread_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return ChatSession(
                thread_id=row[0],
                mode=row[1],
                created_at=datetime.fromisoformat(row[2]),
                last_used=datetime.fromisoformat(row[3]),
                message_count=row[4],
                title=row[5],
            )
        return None

    def list_sessions(self, limit: int = 50) -> List[ChatSession]:
        """List all sessions ordered by last used.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of ChatSession objects
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT thread_id, mode, created_at, last_used, message_count, title
            FROM sessions
            ORDER BY last_used DESC
            LIMIT ?
        """, (limit,))

        sessions = []
        for row in cursor.fetchall():
            sessions.append(ChatSession(
                thread_id=row[0],
                mode=row[1],
                created_at=datetime.fromisoformat(row[2]),
                last_used=datetime.fromisoformat(row[3]),
                message_count=row[4],
                title=row[5],
            ))

        conn.close()
        return sessions

    def delete_session(self, thread_id: str) -> bool:
        """Delete a session from the database.

        Args:
            thread_id: Thread ID to delete

        Returns:
            True if deleted, False if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM sessions WHERE thread_id = ?", (thread_id,))
        deleted = cursor.rowcount > 0

        conn.commit()
        conn.close()

        return deleted

    def update_last_used(self, thread_id: str) -> None:
        """Update the last_used timestamp for a session.

        Args:
            thread_id: Thread ID to update
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE sessions
            SET last_used = ?
            WHERE thread_id = ?
        """, (datetime.now().isoformat(), thread_id))

        conn.commit()
        conn.close()

    def increment_message_count(self, thread_id: str) -> None:
        """Increment the message count for a session.

        Args:
            thread_id: Thread ID to update
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE sessions
            SET message_count = message_count + 1,
                last_used = ?
            WHERE thread_id = ?
        """, (datetime.now().isoformat(), thread_id))

        conn.commit()
        conn.close()

    def update_mode(self, thread_id: str, mode: str) -> None:
        """Update the mode for a session.

        Args:
            thread_id: Thread ID to update
            mode: New mode ('edit' or 'plan')
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE sessions
            SET mode = ?,
                last_used = ?
            WHERE thread_id = ?
        """, (mode, datetime.now().isoformat(), thread_id))

        conn.commit()
        conn.close()

    def cleanup_old_sessions(self, days: int = 30) -> int:
        """Delete sessions older than specified days.

        Args:
            days: Delete sessions not used in this many days

        Returns:
            Number of sessions deleted
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM sessions
            WHERE last_used < ?
        """, (cutoff.isoformat(),))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        return deleted
