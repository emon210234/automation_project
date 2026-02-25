"""
Job Runner - The core worker engine that processes automation jobs.

Picks jobs from the queue, executes the processing pipeline (ingestion, parsing,
validation, storage, reporting), handles retries, and manages state checkpoints.
"""

import json
import time
import traceback
from typing import Any, Callable, Dict, List, Optional

from automation_platform.automation_modules.data_validator import DataValidator
from automation_platform.automation_modules.email_processor import EmailProcessor
from automation_platform.automation_modules.pdf_parser import PDFParser
from automation_platform.automation_modules.report_generator import ReportGenerator
from automation_platform.core.job_queue import JobQueue
from automation_platform.core.state_manager import StateManager
from automation_platform.database.db_manager import DatabaseManager
from automation_platform.monitoring.logger import StructuredLogger
from automation_platform.monitoring.metrics import MetricsCollector


class JobRunner:
    """Worker engine that processes jobs from the queue through the automation pipeline."""

    def __init__(
        self,
        db_manager: DatabaseManager,
        job_queue: JobQueue,
        state_manager: StateManager,
        logger: StructuredLogger,
        metrics: MetricsCollector,
    ) -> None:
        self.db = db_manager
        self.queue = job_queue
        self.state = state_manager
        self.logger = logger
        self.metrics = metrics
        self._running = False

        # Initialize automation modules
        self.pdf_parser = PDFParser(logger)
        self.email_processor = EmailProcessor(logger)
        self.data_validator = DataValidator(logger)
        self.report_generator = ReportGenerator(db_manager, logger)

    def process_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single job through the automation pipeline.

        Pipeline steps:
        1. ingestion  - Collect/load the input data
        2. parsing    - Extract structured data from raw input
        3. validation - Validate the extracted data
        4. storage    - Store results in database
        5. reporting  - Generate output report
        """
        job_id = job["job_id"]
        job_type = job.get("job_type", "invoice_processing")
        payload = json.loads(job["payload"]) if job.get("payload") else {}

        self.logger.info(
            event="job_processing_start",
            message=f"Starting pipeline for job type '{job_type}'",
            job_id=job_id,
            module="job_runner",
        )

        result: Dict[str, Any] = {}
        resume_step = self.state.get_resume_step(job_id)

        steps = [
            ("ingestion", self._step_ingestion),
            ("parsing", self._step_parsing),
            ("validation", self._step_validation),
            ("storage", self._step_storage),
            ("reporting", self._step_reporting),
        ]

        should_skip = resume_step is not None
        for step_name, step_func in steps:
            if should_skip:
                if step_name == resume_step:
                    should_skip = False
                else:
                    # Load checkpoint data to carry forward
                    cp = self.state.get_checkpoint(job_id, step_name)
                    if cp and cp.get("step_data"):
                        result.update(cp["step_data"])
                    self.logger.info(
                        event="step_skipped",
                        message=f"Skipping already-completed step '{step_name}'",
                        job_id=job_id,
                        module="job_runner",
                    )
                    continue

            start_time = time.time()
            step_result = step_func(job_id, job_type, payload, result)
            duration_ms = (time.time() - start_time) * 1000

            result.update(step_result)

            # Save checkpoint after each step
            self.state.save_checkpoint(job_id, step_name, step_result)

            self.logger.info(
                event="step_completed",
                message=f"Step '{step_name}' completed",
                job_id=job_id,
                module="job_runner",
                duration_ms=duration_ms,
            )
            self.metrics.record(
                f"step_duration_{step_name}", duration_ms, {"job_id": job_id}
            )

        return result

    def _step_ingestion(
        self,
        job_id: str,
        job_type: str,
        payload: Dict[str, Any],
        prev_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Step 1: Ingest input data (file path, email source, etc.)."""
        source = payload.get("source", "file")
        file_path = payload.get("file_path", "")

        if source == "email":
            data = self.email_processor.collect(payload)
        else:
            data = {"file_path": file_path, "source": source}

        return {"ingestion": data}

    def _step_parsing(
        self,
        job_id: str,
        job_type: str,
        payload: Dict[str, Any],
        prev_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Step 2: Parse and extract structured data."""
        ingestion_data = prev_result.get("ingestion", {})
        file_path = ingestion_data.get("file_path", payload.get("file_path", ""))

        if file_path.lower().endswith(".pdf"):
            parsed = self.pdf_parser.extract(file_path)
        elif file_path.lower().endswith(".csv"):
            parsed = self.pdf_parser.extract_csv(file_path)
        else:
            # For demo/testing: parse from payload directly
            parsed = {
                "invoice_number": payload.get("invoice_number", "UNKNOWN"),
                "vendor_name": payload.get("vendor_name", "Unknown Vendor"),
                "invoice_date": payload.get("invoice_date", ""),
                "due_date": payload.get("due_date", ""),
                "total_amount": payload.get("total_amount", 0.0),
                "currency": payload.get("currency", "USD"),
                "line_items": payload.get("line_items", []),
                "raw_text": payload.get("raw_text", ""),
                "confidence": 1.0,
            }

        return {"parsed_data": parsed}

    def _step_validation(
        self,
        job_id: str,
        job_type: str,
        payload: Dict[str, Any],
        prev_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Step 3: Validate extracted data."""
        parsed = prev_result.get("parsed_data", {})
        validation_result = self.data_validator.validate_invoice(parsed)
        return {"validation": validation_result}

    def _step_storage(
        self,
        job_id: str,
        job_type: str,
        payload: Dict[str, Any],
        prev_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Step 4: Store validated data in the database."""
        parsed = prev_result.get("parsed_data", {})
        validation = prev_result.get("validation", {})

        if validation.get("is_valid", False):
            record = {
                "job_id": job_id,
                "invoice_number": parsed.get("invoice_number"),
                "vendor_name": parsed.get("vendor_name"),
                "invoice_date": parsed.get("invoice_date"),
                "due_date": parsed.get("due_date"),
                "total_amount": parsed.get("total_amount"),
                "currency": parsed.get("currency", "USD"),
                "line_items": parsed.get("line_items", []),
                "raw_text": parsed.get("raw_text", ""),
                "confidence": parsed.get("confidence", 0.0),
            }
            record_id = self.db.store_processed_data(record)
            return {"storage": {"stored": True, "record_id": record_id}}
        else:
            return {
                "storage": {
                    "stored": False,
                    "reason": "Validation failed",
                    "errors": validation.get("errors", []),
                }
            }

    def _step_reporting(
        self,
        job_id: str,
        job_type: str,
        payload: Dict[str, Any],
        prev_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Step 5: Generate report entry for this job."""
        return {
            "reporting": {
                "job_id": job_id,
                "stored": prev_result.get("storage", {}).get("stored", False),
                "validation_passed": prev_result.get("validation", {}).get(
                    "is_valid", False
                ),
            }
        }

    def run_once(self) -> Optional[str]:
        """Process a single job from the queue. Returns job_id or None."""
        job = self.queue.dequeue()
        if not job:
            return None

        job_id = job["job_id"]
        try:
            with self.metrics.track_duration("job_total_duration", {"job_id": job_id}):
                result = self.process_job(job)
            self.queue.complete(job_id, result)
            self.metrics.increment("jobs_completed")
            return job_id
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            tb = traceback.format_exc()
            self.queue.fail(job_id, error_msg)
            self.db.insert_error(
                error_type=type(e).__name__,
                error_message=str(e),
                job_id=job_id,
                stack_trace=tb,
            )
            self.metrics.increment("jobs_failed")
            self.logger.error(
                event="job_error",
                message=error_msg,
                job_id=job_id,
                module="job_runner",
                details={"traceback": tb},
            )
            return job_id

    def run(self, poll_interval: float = 2.0) -> None:
        """Run the worker loop, continuously processing jobs."""
        self._running = True
        self.logger.info(
            event="worker_started",
            message="Worker started, polling for jobs...",
            module="job_runner",
        )

        # Recover any stale jobs from previous crash
        self.queue.recover_stale_jobs()

        while self._running:
            job_id = self.run_once()
            if job_id is None:
                time.sleep(poll_interval)

    def stop(self) -> None:
        """Signal the worker to stop."""
        self._running = False
        self.logger.info(
            event="worker_stopped",
            message="Worker stop requested",
            module="job_runner",
        )
