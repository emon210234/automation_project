"""Tests for the StateManager module."""

import pytest

from automation_platform.core.state_manager import StateManager
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
    state = StateManager(db, logger)
    db.create_job("job-1", "test")
    yield db, state
    db.close()


class TestStateManager:
    def test_save_and_get_checkpoint(self, setup):
        db, state = setup
        state.save_checkpoint("job-1", "parsing", {"data": "test"})
        cp = state.get_checkpoint("job-1", "parsing")
        assert cp is not None
        assert cp["step_data"] == {"data": "test"}

    def test_get_last_completed_step(self, setup):
        db, state = setup
        state.save_checkpoint("job-1", "ingestion")
        state.save_checkpoint("job-1", "parsing")
        last = state.get_last_completed_step("job-1")
        assert last == "parsing"

    def test_get_last_completed_step_none(self, setup):
        db, state = setup
        assert state.get_last_completed_step("job-1") is None

    def test_get_resume_step(self, setup):
        db, state = setup
        state.save_checkpoint("job-1", "ingestion")
        state.save_checkpoint("job-1", "parsing")
        resume = state.get_resume_step("job-1")
        assert resume == "validation"

    def test_get_resume_step_all_done(self, setup):
        db, state = setup
        for step in StateManager.STEPS:
            state.save_checkpoint("job-1", step)
        resume = state.get_resume_step("job-1")
        assert resume is None  # All steps completed

    def test_get_resume_step_no_checkpoints(self, setup):
        db, state = setup
        resume = state.get_resume_step("job-1")
        assert resume is None

    def test_should_skip_step(self, setup):
        db, state = setup
        state.save_checkpoint("job-1", "ingestion")
        assert state.should_skip_step("job-1", "ingestion") is True
        assert state.should_skip_step("job-1", "parsing") is False

    def test_clear_checkpoints(self, setup):
        db, state = setup
        state.save_checkpoint("job-1", "ingestion")
        state.save_checkpoint("job-1", "parsing")
        state.clear_checkpoints("job-1")
        assert state.get_last_completed_step("job-1") is None
