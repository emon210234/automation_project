"""
Data Validator - Validates extracted invoice data against business rules.

Performs field validation, format checking, and business rule enforcement
to ensure data quality before storage.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from automation_platform.monitoring.logger import StructuredLogger


class DataValidator:
    """Validates extracted invoice data for completeness and correctness."""

    REQUIRED_FIELDS = ["invoice_number", "vendor_name", "total_amount"]

    def __init__(self, logger: StructuredLogger) -> None:
        self.logger = logger

    def validate_invoice(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate an extracted invoice record.

        Checks:
        - Required fields are present and non-empty
        - Total amount is a positive number
        - Invoice number format is valid
        - Date formats are valid (if present)

        Args:
            data: Dictionary of extracted invoice fields.

        Returns:
            Dictionary with 'is_valid', 'errors', and 'warnings' keys.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Check required fields
        for field in self.REQUIRED_FIELDS:
            value = data.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f"Missing required field: {field}")

        # Validate total_amount
        total = data.get("total_amount")
        if total is not None:
            try:
                amount = float(total)
                if amount < 0:
                    errors.append(f"Total amount cannot be negative: {amount}")
                elif amount == 0:
                    warnings.append("Total amount is zero")
                elif amount > 10_000_000:
                    warnings.append(f"Unusually large amount: {amount}")
            except (ValueError, TypeError):
                errors.append(f"Invalid total amount: {total}")

        # Validate invoice number format
        inv_num = data.get("invoice_number")
        if inv_num and isinstance(inv_num, str):
            if len(inv_num) < 2:
                warnings.append(f"Invoice number seems too short: {inv_num}")

        # Validate dates if present
        for date_field in ["invoice_date", "due_date"]:
            date_val = data.get(date_field)
            if date_val and isinstance(date_val, str) and date_val.strip():
                if not self._is_valid_date(date_val):
                    warnings.append(f"Could not parse {date_field}: {date_val}")

        is_valid = len(errors) == 0

        result = {
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "fields_checked": len(self.REQUIRED_FIELDS) + 2,
        }

        log_event = "validation_passed" if is_valid else "validation_failed"
        self.logger.info(
            event=log_event,
            message=f"Validation {'passed' if is_valid else 'failed'}: {len(errors)} errors, {len(warnings)} warnings",
            module="data_validator",
        )
        return result

    @staticmethod
    def _is_valid_date(date_str: str) -> bool:
        """Check if a string is a parseable date."""
        date_formats = [
            "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d",
            "%m-%d-%Y", "%d-%m-%Y",
            "%m.%d.%Y", "%d.%m.%Y",
            "%m/%d/%y", "%d/%m/%y",
        ]
        for fmt in date_formats:
            try:
                datetime.strptime(date_str.strip(), fmt)
                return True
            except ValueError:
                continue
        return False
