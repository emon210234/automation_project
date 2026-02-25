"""
Report Generator - Generates summary reports from processed invoice data.

Produces CSV reports and summary statistics from the processed_data table.
Uses pandas for data aggregation and analysis when available.
"""

import csv
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from automation_platform.database.db_manager import DatabaseManager
from automation_platform.monitoring.logger import StructuredLogger

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore[assignment]


class ReportGenerator:
    """Generates reports from processed automation data."""

    def __init__(
        self,
        db_manager: DatabaseManager,
        logger: StructuredLogger,
        output_dir: str = "automation_platform/reports",
    ) -> None:
        self.db = db_manager
        self.logger = logger
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_csv_report(self, filename: Optional[str] = None) -> str:
        """Generate a CSV report of all processed invoices.

        Returns:
            Path to the generated report file.
        """
        if filename is None:
            timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"invoice_report_{timestamp}.csv"

        filepath = os.path.join(self.output_dir, filename)
        data = self.db.get_all_processed_data()

        if not data:
            self.logger.warning(
                event="report_empty",
                message="No processed data available for report",
                module="report_generator",
            )
            return filepath

        fieldnames = [
            "job_id", "invoice_number", "vendor_name", "invoice_date",
            "due_date", "total_amount", "currency", "confidence", "created_at",
        ]

        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in data:
                writer.writerow(row)

        self.logger.info(
            event="report_generated",
            message=f"CSV report generated: {filepath} ({len(data)} records)",
            module="report_generator",
        )
        return filepath

    def generate_summary(self) -> Dict[str, Any]:
        """Generate a summary of processed data.

        Returns:
            Dictionary with summary statistics.
        """
        data = self.db.get_all_processed_data()
        job_stats = self.db.get_job_stats()

        total_amount = 0.0
        currencies: Dict[str, float] = {}
        vendors: Dict[str, int] = {}

        for record in data:
            amount = record.get("total_amount") or 0.0
            total_amount += amount
            currency = record.get("currency", "USD")
            currencies[currency] = currencies.get(currency, 0) + amount
            vendor = record.get("vendor_name", "Unknown")
            vendors[vendor] = vendors.get(vendor, 0) + 1

        summary = {
            "total_invoices_processed": len(data),
            "total_amount": round(total_amount, 2),
            "amount_by_currency": currencies,
            "invoices_by_vendor": vendors,
            "job_statistics": job_stats,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        self.logger.info(
            event="summary_generated",
            message=f"Summary: {len(data)} invoices, total ${total_amount:,.2f}",
            module="report_generator",
        )
        return summary

    def generate_pandas_report(self, filename: Optional[str] = None) -> Optional[str]:
        """Generate an enhanced report using pandas (if available).

        Returns:
            Path to the report file, or None if pandas is unavailable.
        """
        if pd is None:
            self.logger.warning(
                event="pandas_unavailable",
                message="pandas not installed, skipping enhanced report",
                module="report_generator",
            )
            return None

        data = self.db.get_all_processed_data()
        if not data:
            return None

        if filename is None:
            timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"invoice_analysis_{timestamp}.csv"

        filepath = os.path.join(self.output_dir, filename)
        df = pd.DataFrame(data)

        if "total_amount" in df.columns:
            df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce")

        df.to_csv(filepath, index=False)

        self.logger.info(
            event="pandas_report_generated",
            message=f"Pandas report generated: {filepath}",
            module="report_generator",
        )
        return filepath
