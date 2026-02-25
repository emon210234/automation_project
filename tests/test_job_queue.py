"""Tests for the JobQueue module."""

import pytest

from automation_platform.core.job_queue import JobQueue
from automation_platform.database.db_manager import DatabaseManager
from automation_platform.monitoring.logger import StructuredLogger


@pytest.fixture
def setup(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = DatabaseManager(db_path)
    db.initialize()
    logger = StructuredLogger(
        log_dir=str(tmp_path / "logs"),
        log_to_db=False,
    )
    queue = JobQueue(db, logger)
    yield db, queue
    db.close()


class TestJobQueue:
    def test_enqueue(self, setup):
        db, queue = setup
        job_id = queue.enqueue("invoice_processing", {"file": "test.pdf"})
        assert job_id is not None
        assert queue.size() == 1

    def test_enqueue_with_custom_id(self, setup):
        db, queue = setup
        job_id = queue.enqueue("test", job_id="custom-id")
        assert job_id == "custom-id"

    def test_dequeue(self, setup):
        db, queue = setup
        queue.enqueue("test", {"data": "value"}, job_id="j1")
        job = queue.dequeue()
        assert job is not None
        assert job["job_id"] == "j1"
        assert queue.size() == 0  # no more queued

    def test_dequeue_empty(self, setup):
        db, queue = setup
        assert queue.dequeue() is None

    def test_complete(self, setup):
        db, queue = setup
        queue.enqueue("test", job_id="j1")
        queue.dequeue()
        queue.complete("j1", {"result": "ok"})
        assert queue.get_status("j1") == "completed"

    def test_fail_with_retry(self, setup):
        db, queue = setup
        queue.enqueue("test", job_id="j1", max_retries=2)
        queue.dequeue()
        queue.fail("j1", "error occurred")
        # Should be re-queued for retry
        assert queue.get_status("j1") == "queued"

    def test_fail_permanent(self, setup):
        db, queue = setup
        queue.enqueue("test", job_id="j1", max_retries=0)
        queue.dequeue()
        queue.fail("j1", "error occurred")
        # Should be permanently failed (retry_count=1 > max_retries=0)
        assert queue.get_status("j1") == "failed"

    def test_get_stats(self, setup):
        db, queue = setup
        queue.enqueue("test", job_id="j1")
        queue.enqueue("test", job_id="j2")
        queue.dequeue()
        stats = queue.get_stats()
        assert stats["queued"] == 1
        assert stats["processing"] == 1

    def test_get_status_nonexistent(self, setup):
        db, queue = setup
        assert queue.get_status("nonexistent") is None

    def test_priority_ordering(self, setup):
        db, queue = setup
        queue.enqueue("test", priority=10, job_id="low")
        queue.enqueue("test", priority=1, job_id="high")
        job = queue.dequeue()
        assert job["job_id"] == "high"
