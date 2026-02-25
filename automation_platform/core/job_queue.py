"""
Job Queue - Manages the task queue for the automation platform.

Provides a persistent, fault-tolerant job queue backed by SQLite.
Supports job creation, dequeuing, status tracking, and retry logic.
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from automation_platform.database.db_manager import DatabaseManager
from automation_platform.monitoring.logger import StructuredLogger


class JobQueue:
    """Persistent job queue backed by SQLite."""

    def __init__(self, db_manager: DatabaseManager, logger: StructuredLogger) -> None:
        self.db = db_manager
        self.logger = logger

    def enqueue(
        self,
        job_type: str,
        payload: Optional[Dict[str, Any]] = None,
        priority: int = 5,
        max_retries: int = 3,
        job_id: Optional[str] = None,
    ) -> str:
        """Add a new job to the queue. Returns the job_id."""
        if job_id is None:
            job_id = str(uuid.uuid4())
        self.db.create_job(
            job_id=job_id,
            job_type=job_type,
            payload=payload,
            priority=priority,
            max_retries=max_retries,
        )
        self.logger.info(
            event="job_enqueued",
            message=f"Job {job_id} of type '{job_type}' added to queue",
            job_id=job_id,
            module="job_queue",
        )
        return job_id

    def dequeue(self) -> Optional[Dict[str, Any]]:
        """Get the next job from the queue and mark it as processing."""
        job = self.db.get_next_queued_job()
        if job:
            self.db.update_job_status(job["job_id"], "processing")
            self.logger.info(
                event="job_dequeued",
                message=f"Job {job['job_id']} dequeued for processing",
                job_id=job["job_id"],
                module="job_queue",
            )
        return job

    def complete(
        self, job_id: str, result: Optional[Dict[str, Any]] = None
    ) -> None:
        """Mark a job as completed."""
        self.db.update_job_status(job_id, "completed", result=result)
        self.db.clear_checkpoints(job_id)
        self.logger.info(
            event="job_completed",
            message=f"Job {job_id} completed successfully",
            job_id=job_id,
            module="job_queue",
        )

    def fail(self, job_id: str, error_message: str) -> None:
        """Mark a job as failed, or re-queue for retry if retries remain."""
        job = self.db.get_job(job_id)
        if not job:
            return

        retry_count = self.db.increment_retry(job_id)
        max_retries = job.get("max_retries", 3)

        if retry_count <= max_retries:
            self.db.update_job_status(job_id, "queued", error_message=error_message)
            self.logger.warning(
                event="job_retry",
                message=f"Job {job_id} retry {retry_count}/{max_retries}: {error_message}",
                job_id=job_id,
                module="job_queue",
            )
        else:
            self.db.update_job_status(job_id, "failed", error_message=error_message)
            self.db.insert_error(
                error_type="job_failed",
                error_message=error_message,
                job_id=job_id,
            )
            self.logger.error(
                event="job_failed",
                message=f"Job {job_id} failed permanently after {retry_count} retries",
                job_id=job_id,
                module="job_queue",
            )

    def get_status(self, job_id: str) -> Optional[str]:
        """Get the status of a job."""
        job = self.db.get_job(job_id)
        return job["status"] if job else None

    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics."""
        return self.db.get_job_stats()

    def get_all_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all jobs with a given status."""
        return self.db.get_jobs_by_status(status)

    def recover_stale_jobs(self, timeout_minutes: int = 30) -> int:
        """Recover jobs stuck in processing (crash recovery)."""
        count = self.db.reset_stale_jobs(timeout_minutes)
        if count > 0:
            self.logger.warning(
                event="stale_jobs_recovered",
                message=f"Recovered {count} stale jobs back to queued state",
                module="job_queue",
            )
        return count

    def size(self) -> int:
        """Get the number of queued jobs."""
        stats = self.get_stats()
        return stats.get("queued", 0)
