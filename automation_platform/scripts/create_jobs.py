#!/usr/bin/env python3
"""
Create Jobs - Creates sample invoice processing jobs for testing.

Usage:
    python -m automation_platform.scripts.create_jobs
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from automation_platform.config.settings import load_config
from automation_platform.core.job_queue import JobQueue
from automation_platform.database.db_manager import DatabaseManager
from automation_platform.monitoring.logger import StructuredLogger


SAMPLE_INVOICES = [
    {
        "file_path": "",
        "source": "direct",
        "invoice_number": "INV-2024-001",
        "vendor_name": "Acme Corp",
        "invoice_date": "01/15/2024",
        "due_date": "02/15/2024",
        "total_amount": 1250.00,
        "currency": "USD",
    },
    {
        "file_path": "",
        "source": "direct",
        "invoice_number": "INV-2024-002",
        "vendor_name": "Global Supplies Inc",
        "invoice_date": "01/20/2024",
        "due_date": "02/20/2024",
        "total_amount": 3400.50,
        "currency": "USD",
    },
    {
        "file_path": "",
        "source": "direct",
        "invoice_number": "INV-2024-003",
        "vendor_name": "Tech Solutions Ltd",
        "invoice_date": "01/25/2024",
        "due_date": "02/25/2024",
        "total_amount": 8750.00,
        "currency": "EUR",
    },
    {
        "file_path": "",
        "source": "direct",
        "invoice_number": "INV-2024-004",
        "vendor_name": "Office Depot",
        "invoice_date": "02/01/2024",
        "due_date": "03/01/2024",
        "total_amount": 425.99,
        "currency": "USD",
    },
    {
        "file_path": "",
        "source": "direct",
        "invoice_number": "INV-2024-005",
        "vendor_name": "Cloud Services Corp",
        "invoice_date": "02/05/2024",
        "due_date": "03/05/2024",
        "total_amount": 15000.00,
        "currency": "USD",
    },
]


def main() -> None:
    config = load_config()
    db_path = config.get("database", {}).get("path", "automation_platform/data/automation.db")

    db = DatabaseManager(db_path)
    db.initialize()
    logger = StructuredLogger(
        log_dir=config.get("logging", {}).get("log_dir", "automation_platform/logs"),
        log_to_db=True,
        db_manager=db,
    )
    queue = JobQueue(db, logger)

    print(f"Creating {len(SAMPLE_INVOICES)} sample invoice jobs...")
    for invoice in SAMPLE_INVOICES:
        job_id = queue.enqueue(
            job_type="invoice_processing",
            payload=invoice,
            priority=5,
        )
        print(f"  Created job: {job_id} ({invoice['invoice_number']})")

    stats = queue.get_stats()
    print(f"\nQueue stats: {stats}")
    db.close()


if __name__ == "__main__":
    main()
