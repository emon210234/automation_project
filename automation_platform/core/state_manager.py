"""
State Manager - Provides checkpoint and crash recovery for the automation platform.

Implements a checkpoint system that saves intermediate state during job processing.
If the system crashes, jobs can resume from the last checkpoint instead of restarting.
"""

import json
from typing import Any, Dict, List, Optional

from automation_platform.database.db_manager import DatabaseManager
from automation_platform.monitoring.logger import StructuredLogger


class StateManager:
    """Manages checkpoints and state recovery for fault tolerance."""

    STEPS = ["ingestion", "parsing", "validation", "storage", "reporting"]

    def __init__(self, db_manager: DatabaseManager, logger: StructuredLogger) -> None:
        self.db = db_manager
        self.logger = logger

    def save_checkpoint(
        self, job_id: str, step_name: str, step_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Save a checkpoint for a job step."""
        self.db.save_checkpoint(job_id, step_name, step_data)
        self.logger.info(
            event="checkpoint_saved",
            message=f"Checkpoint saved for step '{step_name}'",
            job_id=job_id,
            module="state_manager",
        )

    def get_checkpoint(self, job_id: str, step_name: str) -> Optional[Dict[str, Any]]:
        """Get checkpoint data for a specific step."""
        return self.db.get_checkpoint(job_id, step_name)

    def get_last_completed_step(self, job_id: str) -> Optional[str]:
        """Get the name of the last completed step for a job."""
        checkpoints = self.db.get_all_checkpoints(job_id)
        if not checkpoints:
            return None
        return checkpoints[-1]["step_name"]

    def get_resume_step(self, job_id: str) -> Optional[str]:
        """Determine which step to resume from after a crash.

        Returns the step AFTER the last completed checkpoint,
        or None if no checkpoints exist (start from beginning).
        """
        last_step = self.get_last_completed_step(job_id)
        if last_step is None:
            return None

        if last_step in self.STEPS:
            idx = self.STEPS.index(last_step)
            if idx + 1 < len(self.STEPS):
                resume_step = self.STEPS[idx + 1]
                self.logger.info(
                    event="resume_determined",
                    message=f"Resuming from step '{resume_step}' (last completed: '{last_step}')",
                    job_id=job_id,
                    module="state_manager",
                )
                return resume_step
            else:
                return None  # All steps completed
        return None

    def clear_checkpoints(self, job_id: str) -> None:
        """Clear all checkpoints for a job (called after successful completion)."""
        self.db.clear_checkpoints(job_id)
        self.logger.info(
            event="checkpoints_cleared",
            message="All checkpoints cleared",
            job_id=job_id,
            module="state_manager",
        )

    def should_skip_step(self, job_id: str, step_name: str) -> bool:
        """Check if a step should be skipped (already completed based on checkpoints)."""
        checkpoint = self.get_checkpoint(job_id, step_name)
        return checkpoint is not None
