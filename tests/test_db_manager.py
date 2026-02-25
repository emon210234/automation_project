"""Tests for the DatabaseManager module."""

import json
import os
import tempfile

import pytest

from automation_platform.database.db_manager import DatabaseManager


@pytest.fixture
def db(tmp_path):
    """Create a temporary database for testing."""
    db_path = str(tmp_path / "test.db")
    manager = DatabaseManager(db_path)
    manager.initialize()
    yield manager
    manager.close()


class TestJobOperations:
    def test_create_and_get_job(self, db):
        job = db.create_job("job-1", "invoice_processing", {"file": "test.pdf"})
        assert job["job_id"] == "job-1"
        assert job["job_type"] == "invoice_processing"
        assert job["status"] == "queued"
        assert job["retry_count"] == 0

    def test_get_nonexistent_job(self, db):
        assert db.get_job("nonexistent") is None

    def test_get_next_queued_job_priority(self, db):
        db.create_job("low", "test", priority=10)
        db.create_job("high", "test", priority=1)
        db.create_job("med", "test", priority=5)

        job = db.get_next_queued_job()
        assert job["job_id"] == "high"

    def test_update_job_status(self, db):
        db.create_job("job-1", "test")

        db.update_job_status("job-1", "processing")
        job = db.get_job("job-1")
        assert job["status"] == "processing"
        assert job["started_at"] is not None

        db.update_job_status("job-1", "completed", result={"ok": True})
        job = db.get_job("job-1")
        assert job["status"] == "completed"
        assert job["completed_at"] is not None
        assert json.loads(job["result"]) == {"ok": True}

    def test_update_job_status_with_error(self, db):
        db.create_job("job-1", "test")
        db.update_job_status("job-1", "failed", error_message="Something broke")
        job = db.get_job("job-1")
        assert job["status"] == "failed"
        assert job["error_message"] == "Something broke"

    def test_increment_retry(self, db):
        db.create_job("job-1", "test", max_retries=3)
        count = db.increment_retry("job-1")
        assert count == 1
        job = db.get_job("job-1")
        assert job["status"] == "retrying"

    def test_get_jobs_by_status(self, db):
        db.create_job("j1", "test")
        db.create_job("j2", "test")
        db.create_job("j3", "test")
        db.update_job_status("j2", "processing")

        queued = db.get_jobs_by_status("queued")
        assert len(queued) == 2

    def test_get_job_stats(self, db):
        db.create_job("j1", "test")
        db.create_job("j2", "test")
        db.update_job_status("j2", "completed")
        stats = db.get_job_stats()
        assert stats["queued"] == 1
        assert stats["completed"] == 1


class TestProcessedData:
    def test_store_and_retrieve(self, db):
        db.create_job("job-1", "test")
        record = {
            "job_id": "job-1",
            "invoice_number": "INV-001",
            "vendor_name": "Test Corp",
            "total_amount": 100.50,
            "currency": "USD",
        }
        record_id = db.store_processed_data(record)
        assert record_id is not None

        data = db.get_processed_data("job-1")
        assert data["invoice_number"] == "INV-001"
        assert data["vendor_name"] == "Test Corp"
        assert data["total_amount"] == 100.50

    def test_get_all_processed_data(self, db):
        db.create_job("j1", "test")
        db.create_job("j2", "test")
        db.store_processed_data({"job_id": "j1", "invoice_number": "A"})
        db.store_processed_data({"job_id": "j2", "invoice_number": "B"})
        all_data = db.get_all_processed_data()
        assert len(all_data) == 2


class TestCheckpoints:
    def test_save_and_get_checkpoint(self, db):
        db.create_job("job-1", "test")
        db.save_checkpoint("job-1", "parsing", {"text": "extracted"})
        cp = db.get_checkpoint("job-1", "parsing")
        assert cp is not None
        assert cp["step_data"] == {"text": "extracted"}

    def test_get_all_checkpoints(self, db):
        db.create_job("job-1", "test")
        db.save_checkpoint("job-1", "ingestion", {"a": 1})
        db.save_checkpoint("job-1", "parsing", {"b": 2})
        cps = db.get_all_checkpoints("job-1")
        assert len(cps) == 2

    def test_clear_checkpoints(self, db):
        db.create_job("job-1", "test")
        db.save_checkpoint("job-1", "ingestion", {"a": 1})
        db.clear_checkpoints("job-1")
        cps = db.get_all_checkpoints("job-1")
        assert len(cps) == 0


class TestLogs:
    def test_insert_and_get_logs(self, db):
        db.create_job("j1", "test")
        db.insert_log("INFO", "test_event", "Test message", job_id="j1")
        logs = db.get_logs(job_id="j1")
        assert len(logs) == 1
        assert logs[0]["event"] == "test_event"

    def test_get_logs_by_level(self, db):
        db.insert_log("INFO", "e1", "msg1")
        db.insert_log("ERROR", "e2", "msg2")
        errors = db.get_logs(level="ERROR")
        assert len(errors) == 1


class TestErrors:
    def test_insert_error(self, db):
        db.create_job("job-1", "test")
        db.insert_error("ValueError", "bad value", job_id="job-1", stack_trace="...")
        # Verify no exception is raised


class TestMetrics:
    def test_record_metric(self, db):
        db.record_metric("test_metric", 42.0, {"env": "test"})
        # Verify no exception is raised
