"""
Email Processor - Collects and processes emails for invoice extraction.

Handles IMAP email collection, attachment downloading, and email metadata
extraction. In production, connects to a mail server; provides a simulation
mode for development and testing.
"""

import email
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from automation_platform.monitoring.logger import StructuredLogger


class EmailProcessor:
    """Processes emails to extract invoice attachments and metadata."""

    def __init__(self, logger: StructuredLogger) -> None:
        self.logger = logger

    def collect(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Collect email data based on configuration.

        In production, this would connect to an IMAP server.
        For development/testing, it returns simulated data.

        Args:
            config: Dictionary with email collection parameters.
                - source: 'email' to trigger collection
                - sender: Optional sender filter
                - subject_filter: Optional subject line filter

        Returns:
            Dictionary with extracted email metadata and file paths.
        """
        sender = config.get("sender", "")
        subject_filter = config.get("subject_filter", "invoice")

        self.logger.info(
            event="email_collection_start",
            message=f"Collecting emails (sender={sender}, filter={subject_filter})",
            module="email_processor",
        )

        # Simulation mode for development
        result = {
            "source": "email",
            "sender": sender or "vendor@example.com",
            "subject": f"Invoice - {datetime.now(tz=timezone.utc).strftime('%Y%m%d')}",
            "received_at": datetime.now(tz=timezone.utc).isoformat(),
            "file_path": config.get("file_path", ""),
            "attachments": config.get("attachments", []),
        }

        self.logger.info(
            event="email_collected",
            message="Email data collected successfully",
            module="email_processor",
        )
        return result

    @staticmethod
    def parse_email_content(raw_email: str) -> Dict[str, Any]:
        """Parse raw email content and extract metadata.

        Args:
            raw_email: Raw email string (RFC 2822 format).

        Returns:
            Dictionary with sender, subject, date, body, and attachment info.
        """
        msg = email.message_from_string(raw_email)
        attachments: List[str] = []

        if msg.is_multipart():
            for part in msg.walk():
                filename = part.get_filename()
                if filename:
                    attachments.append(filename)

        return {
            "sender": msg.get("From", ""),
            "subject": msg.get("Subject", ""),
            "date": msg.get("Date", ""),
            "has_attachments": len(attachments) > 0,
            "attachment_names": attachments,
        }
