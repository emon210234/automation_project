"""Tests for the JobRunner module."""

import json

import pytest

from automation_platform.core.job_queue import JobQueue
from automation_platform.core.job_runner import JobRunner
from automation_platform.core.state_manager import StateManager
from automation_platform.database.db_manager import DatabaseManager
from automation_platform.monitoring.logger import StructuredLogger
from automation_platform.monitoring.metrics import MetricsCollector


@pytest.fixture
def setup(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = DatabaseManager(db_path)
    db.initialize()
    logger = StructuredLogger(
        log_dir=str(tmp_path / "logs"),
        log_to_db=False,
    )
    metrics = MetricsCollector(db)
    queue = JobQueue(db, logger)
    state = StateManager(db, logger)
    runner = JobRunner(db, queue, state, logger, metrics)
    yield db, queue, state, runner
    db.close()


class TestJobRunner:
    def test_run_once_no_jobs(self, setup):
        db, queue, state, runner = setup
        result = runner.run_once()
        assert result is None

    def test_run_once_success(self, setup):
        db, queue, state, runner = setup
        queue.enqueue(
            "invoice_processing",
            payload={
                "invoice_number": "INV-001",
                "vendor_name": "Test Corp",
                "total_amount": 100.0,
                "currency": "USD",
            },
            job_id="test-job",
        )
        result = runner.run_once()
        assert result == "test-job"
        assert queue.get_status("test-job") == "completed"

    def test_run_once_stores_data(self, setup):
        db, queue, state, runner = setup
        queue.enqueue(
            "invoice_processing",
            payload={
                "invoice_number": "INV-002",
                "vendor_name": "Acme Inc",
                "total_amount": 500.0,
                "invoice_date": "01/15/2024",
            },
            job_id="data-job",
        )
        runner.run_once()
        data = db.get_processed_data("data-job")
        assert data is not None
        assert data["invoice_number"] == "INV-002"
        assert data["total_amount"] == 500.0

    def test_run_once_validation_failure(self, setup):
        db, queue, state, runner = setup
        # Missing required fields: vendor_name is empty, total_amount is negative
        queue.enqueue(
            "invoice_processing",
            payload={
                "source": "direct",
                "invoice_number": "INV-BAD",
                "vendor_name": "",
                "total_amount": -100.0,
            },
            job_id="invalid-job",
        )
        runner.run_once()
        status = queue.get_status("invalid-job")
        assert status == "completed"
        # Data should not be stored when validation fails
        data = db.get_processed_data("invalid-job")
        assert data is None

    def test_resume_from_checkpoint(self, setup):
        db, queue, state, runner = setup
        # Simulate a previous partial run with checkpoints
        queue.enqueue(
            "invoice_processing",
            payload={
                "invoice_number": "INV-003",
                "vendor_name": "Resume Corp",
                "total_amount": 200.0,
            },
            job_id="resume-job",
        )

        # Save checkpoints as if ingestion and parsing were done
        state.save_checkpoint("resume-job", "ingestion", {
            "file_path": "", "source": "direct"
        })
        state.save_checkpoint("resume-job", "parsing", {
            "parsed_data": {
                "invoice_number": "INV-003",
                "vendor_name": "Resume Corp",
                "total_amount": 200.0,
                "currency": "USD",
            }
        })

        job = queue.dequeue()
        result = runner.process_job(job)
        assert "validation" in result
        assert "storage" in result
        assert "reporting" in result

    def test_multiple_jobs_processing(self, setup):
        db, queue, state, runner = setup
        for i in range(3):
            queue.enqueue(
                "invoice_processing",
                payload={
                    "invoice_number": f"INV-{i}",
                    "vendor_name": f"Vendor {i}",
                    "total_amount": 100.0 * (i + 1),
                },
                job_id=f"batch-{i}",
            )

        for i in range(3):
            runner.run_once()

        for i in range(3):
            assert queue.get_status(f"batch-{i}") == "completed"

    def test_stop(self, setup):
        db, queue, state, runner = setup
        runner.stop()
        assert runner._running is False
