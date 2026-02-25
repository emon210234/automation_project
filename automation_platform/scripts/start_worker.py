#!/usr/bin/env python3
"""
Start Worker - Starts the automation worker to process jobs from the queue.

Usage:
    python -m automation_platform.scripts.start_worker
"""

import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from automation_platform.config.settings import load_config
from automation_platform.core.job_queue import JobQueue
from automation_platform.core.job_runner import JobRunner
from automation_platform.core.state_manager import StateManager
from automation_platform.database.db_manager import DatabaseManager
from automation_platform.monitoring.logger import StructuredLogger
from automation_platform.monitoring.metrics import MetricsCollector


def main() -> None:
    config = load_config()
    db_path = config.get("database", {}).get("path", "automation_platform/data/automation.db")
    log_dir = config.get("logging", {}).get("log_dir", "automation_platform/logs")
    log_level = config.get("logging", {}).get("level", "INFO")
    poll_interval = config.get("queue", {}).get("poll_interval_seconds", 2)

    db = DatabaseManager(db_path)
    db.initialize()

    logger = StructuredLogger(
        log_dir=log_dir,
        log_level=log_level,
        log_to_db=True,
        db_manager=db,
    )
    metrics = MetricsCollector(db)
    queue = JobQueue(db, logger)
    state = StateManager(db, logger)

    runner = JobRunner(db, queue, state, logger, metrics)

    def signal_handler(sig: int, frame: object) -> None:
        print("\nShutdown signal received, stopping worker...")
        runner.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("Starting automation worker...")
    print(f"Database: {db_path}")
    print(f"Poll interval: {poll_interval}s")
    print("Press Ctrl+C to stop.\n")

    runner.run(poll_interval=poll_interval)

    db.close()
    print("Worker stopped.")


if __name__ == "__main__":
    main()
