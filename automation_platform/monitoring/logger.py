"""
Structured Logger - Provides structured logging for the automation platform.

Logs are written to both files and the database for full observability.
Each log entry includes timestamp, job_id, event type, duration, and error details.
"""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional

from automation_platform.database.db_manager import DatabaseManager


class StructuredLogger:
    """Structured logging system that writes to files and database."""

    def __init__(
        self,
        name: str = "automation_platform",
        log_dir: str = "automation_platform/logs",
        log_level: str = "INFO",
        log_to_file: bool = True,
        log_to_db: bool = True,
        db_manager: Optional[DatabaseManager] = None,
    ) -> None:
        self.name = name
        self.log_dir = log_dir
        self.log_to_db = log_to_db
        self.db_manager = db_manager

        os.makedirs(log_dir, exist_ok=True)

        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        self.logger.handlers.clear()

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        if log_to_file:
            file_handler = RotatingFileHandler(
                os.path.join(log_dir, "automation.log"),
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def _log_to_db(
        self,
        level: str,
        event: str,
        message: str,
        job_id: Optional[str] = None,
        module: Optional[str] = None,
        duration_ms: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Write log entry to database."""
        if self.log_to_db and self.db_manager:
            try:
                self.db_manager.insert_log(
                    level=level,
                    event=event,
                    message=message,
                    job_id=job_id,
                    module=module,
                    duration_ms=duration_ms,
                    details=details,
                )
            except Exception:
                pass  # Don't let logging failures crash the system

    def info(
        self,
        event: str,
        message: str,
        job_id: Optional[str] = None,
        module: Optional[str] = None,
        duration_ms: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an INFO event."""
        log_msg = self._format_message(event, message, job_id, module, duration_ms)
        self.logger.info(log_msg)
        self._log_to_db("INFO", event, message, job_id, module, duration_ms, details)

    def warning(
        self,
        event: str,
        message: str,
        job_id: Optional[str] = None,
        module: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a WARNING event."""
        log_msg = self._format_message(event, message, job_id, module)
        self.logger.warning(log_msg)
        self._log_to_db("WARNING", event, message, job_id, module, details=details)

    def error(
        self,
        event: str,
        message: str,
        job_id: Optional[str] = None,
        module: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an ERROR event."""
        log_msg = self._format_message(event, message, job_id, module)
        self.logger.error(log_msg)
        self._log_to_db("ERROR", event, message, job_id, module, details=details)

    def _format_message(
        self,
        event: str,
        message: str,
        job_id: Optional[str] = None,
        module: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ) -> str:
        """Format a structured log message."""
        parts = [f"event={event}"]
        if job_id:
            parts.append(f"job_id={job_id}")
        if module:
            parts.append(f"module={module}")
        if duration_ms is not None:
            parts.append(f"duration_ms={duration_ms:.1f}")
        parts.append(f"msg={message}")
        return " | ".join(parts)
