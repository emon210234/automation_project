"""
Metrics Collector - Tracks performance metrics for the automation platform.

Records execution times, success/failure rates, throughput, and resource usage
to enable monitoring and alerting.
"""

import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, Optional

from automation_platform.database.db_manager import DatabaseManager


class MetricsCollector:
    """Collects and stores performance metrics."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self.db_manager = db_manager
        self._counters: Dict[str, float] = {}

    @contextmanager
    def track_duration(
        self, metric_name: str, tags: Optional[Dict[str, str]] = None
    ) -> Generator[None, None, None]:
        """Context manager to track operation duration in milliseconds."""
        start = time.time()
        try:
            yield
        finally:
            duration_ms = (time.time() - start) * 1000
            self.record(metric_name, duration_ms, tags)

    def record(
        self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a metric value."""
        if self.db_manager:
            try:
                self.db_manager.record_metric(metric_name, value, tags)
            except Exception:
                pass

    def increment(self, counter_name: str, amount: float = 1.0) -> None:
        """Increment a counter."""
        self._counters[counter_name] = self._counters.get(counter_name, 0) + amount
        self.record(counter_name, self._counters[counter_name])

    def get_counter(self, counter_name: str) -> float:
        """Get current value of a counter."""
        return self._counters.get(counter_name, 0)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all job metrics from database."""
        if not self.db_manager:
            return {}
        stats = self.db_manager.get_job_stats()
        total = sum(stats.values())
        completed = stats.get("completed", 0)
        failed = stats.get("failed", 0)
        return {
            "total_jobs": total,
            "completed": completed,
            "failed": failed,
            "success_rate": (completed / total * 100) if total > 0 else 0,
            "failure_rate": (failed / total * 100) if total > 0 else 0,
            "by_status": stats,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
