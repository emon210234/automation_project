"""
Database Manager - Handles all database operations for the automation platform.

Uses SQLite for persistent storage of jobs, processed data, logs, and errors.
SQLite is chosen for local deployment simplicity, zero-configuration, and
ACID compliance which ensures data integrity during crash recovery.
"""

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional


class DatabaseManager:
    """Thread-safe SQLite database manager with connection pooling."""

    def __init__(self, db_path: str = "automation_platform/data/automation.db") -> None:
        self.db_path = db_path
        self._local = threading.local()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.db_path, timeout=30
            )
            self._local.connection.row_factory = sqlite3.Row
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA foreign_keys=ON")
        return self._local.connection

    @contextmanager
    def get_cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager for database cursor with auto-commit/rollback."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def initialize(self) -> None:
        """Initialize database schema from schema.sql."""
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path, "r") as f:
            schema_sql = f.read()
        with self.get_cursor() as cursor:
            cursor.executescript(schema_sql)

    def close(self) -> None:
        """Close the thread-local connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None

    # --- Job Operations ---

    def create_job(
        self,
        job_id: str,
        job_type: str,
        payload: Optional[Dict[str, Any]] = None,
        priority: int = 5,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Create a new job in the queue."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO jobs (job_id, job_type, status, priority, payload, max_retries, created_at, updated_at)
                   VALUES (?, ?, 'queued', ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    job_type,
                    priority,
                    json.dumps(payload) if payload else None,
                    max_retries,
                    datetime.now(tz=timezone.utc).isoformat(),
                    datetime.now(tz=timezone.utc).isoformat(),
                ),
            )
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_next_queued_job(self) -> Optional[Dict[str, Any]]:
        """Get the next queued job (highest priority, oldest first)."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """SELECT * FROM jobs
                   WHERE status = 'queued'
                   ORDER BY priority ASC, created_at ASC
                   LIMIT 1"""
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_job_status(
        self,
        job_id: str,
        status: str,
        error_message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update job status and related fields."""
        now = datetime.now(tz=timezone.utc).isoformat()
        with self.get_cursor() as cursor:
            updates = ["status = ?", "updated_at = ?"]
            params: list = [status, now]

            if status == "processing":
                updates.append("started_at = ?")
                params.append(now)
            elif status in ("completed", "failed"):
                updates.append("completed_at = ?")
                params.append(now)

            if error_message is not None:
                updates.append("error_message = ?")
                params.append(error_message)

            if result is not None:
                updates.append("result = ?")
                params.append(json.dumps(result))

            params.append(job_id)
            cursor.execute(
                f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?", params
            )

    def increment_retry(self, job_id: str) -> int:
        """Increment retry count and return new value."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """UPDATE jobs SET retry_count = retry_count + 1, status = 'retrying',
                   updated_at = ? WHERE job_id = ?""",
                (datetime.now(tz=timezone.utc).isoformat(), job_id),
            )
            cursor.execute("SELECT retry_count FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            return row["retry_count"] if row else 0

    def get_jobs_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all jobs with a given status."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM jobs WHERE status = ?", (status,))
            return [dict(row) for row in cursor.fetchall()]

    def get_job_stats(self) -> Dict[str, int]:
        """Get count of jobs by status."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT status, COUNT(*) as count FROM jobs GROUP BY status"
            )
            return {row["status"]: row["count"] for row in cursor.fetchall()}

    def reset_stale_jobs(self, timeout_minutes: int = 30) -> int:
        """Reset jobs stuck in 'processing' state (crash recovery)."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """UPDATE jobs SET status = 'queued', updated_at = ?
                   WHERE status = 'processing'
                   AND datetime(started_at, '+' || ? || ' minutes') < datetime('now')""",
                (datetime.now(tz=timezone.utc).isoformat(), timeout_minutes),
            )
            return cursor.rowcount

    # --- Processed Data Operations ---

    def store_processed_data(self, data: Dict[str, Any]) -> int:
        """Store extracted invoice data."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO processed_data
                   (job_id, invoice_number, vendor_name, invoice_date, due_date,
                    total_amount, currency, line_items, raw_text, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    data["job_id"],
                    data.get("invoice_number"),
                    data.get("vendor_name"),
                    data.get("invoice_date"),
                    data.get("due_date"),
                    data.get("total_amount"),
                    data.get("currency", "USD"),
                    json.dumps(data.get("line_items", [])),
                    data.get("raw_text"),
                    data.get("confidence"),
                ),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def get_processed_data(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get processed data for a job."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM processed_data WHERE job_id = ?", (job_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_processed_data(self) -> List[Dict[str, Any]]:
        """Get all processed invoice data."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM processed_data ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    # --- Log Operations ---

    def insert_log(
        self,
        level: str,
        event: str,
        message: str,
        job_id: Optional[str] = None,
        module: Optional[str] = None,
        duration_ms: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Insert a structured log entry."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO logs (timestamp, level, job_id, module, event, message, duration_ms, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now(tz=timezone.utc).isoformat(),
                    level,
                    job_id,
                    module,
                    event,
                    message,
                    duration_ms,
                    json.dumps(details) if details else None,
                ),
            )

    def get_logs(
        self, job_id: Optional[str] = None, level: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Query logs with optional filters."""
        conditions = []
        params: list = []
        if job_id:
            conditions.append("job_id = ?")
            params.append(job_id)
        if level:
            conditions.append("level = ?")
            params.append(level)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        with self.get_cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM logs {where} ORDER BY timestamp DESC LIMIT ?", params
            )
            return [dict(row) for row in cursor.fetchall()]

    # --- Error Operations ---

    def insert_error(
        self,
        error_type: str,
        error_message: str,
        job_id: Optional[str] = None,
        stack_trace: Optional[str] = None,
    ) -> None:
        """Record an error."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO errors (job_id, error_type, error_message, stack_trace, occurred_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (job_id, error_type, error_message, stack_trace, datetime.now(tz=timezone.utc).isoformat()),
            )

    # --- Checkpoint Operations ---

    def save_checkpoint(
        self, job_id: str, step_name: str, step_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Save or update a checkpoint for crash recovery."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """INSERT OR REPLACE INTO checkpoints (job_id, step_name, step_data, created_at)
                   VALUES (?, ?, ?, ?)""",
                (
                    job_id,
                    step_name,
                    json.dumps(step_data) if step_data else None,
                    datetime.now(tz=timezone.utc).isoformat(),
                ),
            )

    def get_checkpoint(self, job_id: str, step_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific checkpoint."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM checkpoints WHERE job_id = ? AND step_name = ?",
                (job_id, step_name),
            )
            row = cursor.fetchone()
            if row:
                result = dict(row)
                if result.get("step_data"):
                    result["step_data"] = json.loads(result["step_data"])
                return result
            return None

    def get_all_checkpoints(self, job_id: str) -> List[Dict[str, Any]]:
        """Get all checkpoints for a job."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM checkpoints WHERE job_id = ? ORDER BY created_at",
                (job_id,),
            )
            results = []
            for row in cursor.fetchall():
                r = dict(row)
                if r.get("step_data"):
                    r["step_data"] = json.loads(r["step_data"])
                results.append(r)
            return results

    def clear_checkpoints(self, job_id: str) -> None:
        """Clear all checkpoints for a completed job."""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM checkpoints WHERE job_id = ?", (job_id,))

    # --- Metrics Operations ---

    def record_metric(
        self, metric_name: str, metric_value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a performance metric."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO metrics (metric_name, metric_value, tags, recorded_at)
                   VALUES (?, ?, ?, ?)""",
                (
                    metric_name,
                    metric_value,
                    json.dumps(tags) if tags else None,
                    datetime.now(tz=timezone.utc).isoformat(),
                ),
            )
