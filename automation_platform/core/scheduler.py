"""
Scheduler - Provides job scheduling capabilities for the automation platform.

Supports creating batches of jobs and managing scheduled execution.
"""

import os
import uuid
from typing import Any, Dict, List, Optional

from automation_platform.core.job_queue import JobQueue
from automation_platform.monitoring.logger import StructuredLogger


class Scheduler:
    """Schedules and manages batches of automation jobs."""

    def __init__(self, job_queue: JobQueue, logger: StructuredLogger) -> None:
        self.queue = job_queue
        self.logger = logger

    def create_batch(
        self,
        job_type: str,
        payloads: List[Dict[str, Any]],
        priority: int = 5,
        max_retries: int = 3,
    ) -> List[str]:
        """Create a batch of jobs. Returns list of job_ids."""
        job_ids = []
        for payload in payloads:
            job_id = self.queue.enqueue(
                job_type=job_type,
                payload=payload,
                priority=priority,
                max_retries=max_retries,
            )
            job_ids.append(job_id)

        self.logger.info(
            event="batch_created",
            message=f"Created batch of {len(job_ids)} jobs of type '{job_type}'",
            module="scheduler",
        )
        return job_ids

    def create_jobs_from_directory(
        self,
        directory: str,
        job_type: str = "invoice_processing",
        extensions: Optional[List[str]] = None,
    ) -> List[str]:
        """Scan a directory and create a job for each matching file."""
        if extensions is None:
            extensions = [".pdf", ".csv", ".png", ".jpg"]

        job_ids = []
        if not os.path.isdir(directory):
            self.logger.warning(
                event="directory_not_found",
                message=f"Directory not found: {directory}",
                module="scheduler",
            )
            return job_ids

        for filename in sorted(os.listdir(directory)):
            ext = os.path.splitext(filename)[1].lower()
            if ext in extensions:
                file_path = os.path.join(directory, filename)
                payload = {"file_path": file_path, "source": "file"}
                job_id = self.queue.enqueue(
                    job_type=job_type, payload=payload
                )
                job_ids.append(job_id)

        self.logger.info(
            event="directory_scan_complete",
            message=f"Created {len(job_ids)} jobs from directory '{directory}'",
            module="scheduler",
        )
        return job_ids

    def get_batch_status(self, job_ids: List[str]) -> Dict[str, int]:
        """Get aggregated status for a batch of jobs."""
        status_counts: Dict[str, int] = {}
        for job_id in job_ids:
            status = self.queue.get_status(job_id)
            if status:
                status_counts[status] = status_counts.get(status, 0) + 1
        return status_counts
