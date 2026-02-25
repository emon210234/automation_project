"""
PDF Parser - Extracts structured data from PDF invoices and CSV files.

Uses pdfplumber for PDF text extraction and regex patterns for field extraction.
Falls back to pattern matching when structured parsing isn't possible.

Libraries used:
- pdfplumber: High-accuracy PDF text extraction with table support
- re (regex): Pattern matching for invoice fields (numbers, dates, amounts)
- csv: Standard library CSV parsing for spreadsheet-based invoices
"""

import csv
import io
import os
import re
from typing import Any, Dict, List, Optional

from automation_platform.monitoring.logger import StructuredLogger

try:
    import pdfplumber
except ImportError:
    pdfplumber = None  # type: ignore[assignment]


class PDFParser:
    """Extracts invoice data from PDF and CSV files."""

    # Regex patterns for common invoice fields
    PATTERNS = {
        "invoice_number": re.compile(
            r"(?:invoice\s*(?:#|no\.?|number)\s*[:\s]?\s*)([A-Z0-9\-]+)",
            re.IGNORECASE,
        ),
        "date": re.compile(
            r"(?:date\s*[:\s]?\s*)(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
            re.IGNORECASE,
        ),
        "due_date": re.compile(
            r"(?:due\s*date\s*[:\s]?\s*)(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
            re.IGNORECASE,
        ),
        "total": re.compile(
            r"(?:total|amount\s*due|balance\s*due)\s*[:\s]?\s*\$?\s*([\d,]+\.?\d*)",
            re.IGNORECASE,
        ),
        "vendor": re.compile(
            r"(?:from|vendor|company|bill\s*from)\s*[:\s]?\s*(.+)",
            re.IGNORECASE,
        ),
        "currency": re.compile(
            r"(USD|EUR|GBP|CAD|AUD|JPY|\$|€|£)", re.IGNORECASE
        ),
    }

    CURRENCY_MAP = {"$": "USD", "€": "EUR", "£": "GBP"}

    def __init__(self, logger: StructuredLogger) -> None:
        self.logger = logger

    def extract(self, file_path: str) -> Dict[str, Any]:
        """Extract invoice data from a PDF file.

        Args:
            file_path: Path to the PDF file.

        Returns:
            Dictionary with extracted invoice fields.
        """
        if not os.path.isfile(file_path):
            self.logger.warning(
                event="file_not_found",
                message=f"PDF file not found: {file_path}",
                module="pdf_parser",
            )
            return self._empty_result()

        if pdfplumber is None:
            self.logger.warning(
                event="pdfplumber_missing",
                message="pdfplumber not installed, returning empty result",
                module="pdf_parser",
            )
            return self._empty_result()

        try:
            text = self._extract_text(file_path)
            return self._parse_text(text)
        except Exception as e:
            self.logger.error(
                event="pdf_extraction_error",
                message=f"Failed to extract PDF: {str(e)}",
                module="pdf_parser",
            )
            return self._empty_result()

    def _extract_text(self, file_path: str) -> str:
        """Extract raw text from PDF using pdfplumber."""
        full_text = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text.append(text)
        return "\n".join(full_text)

    def _parse_text(self, text: str) -> Dict[str, Any]:
        """Parse extracted text using regex patterns."""
        result: Dict[str, Any] = {
            "invoice_number": None,
            "vendor_name": None,
            "invoice_date": None,
            "due_date": None,
            "total_amount": None,
            "currency": "USD",
            "line_items": [],
            "raw_text": text[:2000],
            "confidence": 0.0,
        }

        fields_found = 0

        # Extract invoice number
        match = self.PATTERNS["invoice_number"].search(text)
        if match:
            result["invoice_number"] = match.group(1).strip()
            fields_found += 1

        # Extract vendor name
        match = self.PATTERNS["vendor"].search(text)
        if match:
            result["vendor_name"] = match.group(1).strip()[:100]
            fields_found += 1

        # Extract date
        match = self.PATTERNS["date"].search(text)
        if match:
            result["invoice_date"] = match.group(1).strip()
            fields_found += 1

        # Extract due date
        match = self.PATTERNS["due_date"].search(text)
        if match:
            result["due_date"] = match.group(1).strip()
            fields_found += 1

        # Extract total amount
        match = self.PATTERNS["total"].search(text)
        if match:
            amount_str = match.group(1).replace(",", "")
            try:
                result["total_amount"] = float(amount_str)
                fields_found += 1
            except ValueError:
                pass

        # Extract currency
        match = self.PATTERNS["currency"].search(text)
        if match:
            symbol = match.group(1)
            result["currency"] = self.CURRENCY_MAP.get(symbol, symbol.upper())

        # Confidence based on fields found
        result["confidence"] = min(fields_found / 5.0, 1.0)

        return result

    def extract_csv(self, file_path: str) -> Dict[str, Any]:
        """Extract invoice data from a CSV file.

        Expects columns: invoice_number, vendor_name, invoice_date,
        due_date, total_amount, currency.
        """
        if not os.path.isfile(file_path):
            self.logger.warning(
                event="file_not_found",
                message=f"CSV file not found: {file_path}",
                module="pdf_parser",
            )
            return self._empty_result()

        try:
            with open(file_path, "r", newline="") as f:
                reader = csv.DictReader(f)
                row = next(reader, None)
                if row is None:
                    return self._empty_result()

                total = row.get("total_amount", "0")
                try:
                    total_amount = float(str(total).replace(",", ""))
                except ValueError:
                    total_amount = 0.0

                return {
                    "invoice_number": row.get("invoice_number", ""),
                    "vendor_name": row.get("vendor_name", ""),
                    "invoice_date": row.get("invoice_date", ""),
                    "due_date": row.get("due_date", ""),
                    "total_amount": total_amount,
                    "currency": row.get("currency", "USD"),
                    "line_items": [],
                    "raw_text": str(row),
                    "confidence": 0.9,
                }
        except Exception as e:
            self.logger.error(
                event="csv_extraction_error",
                message=f"Failed to extract CSV: {str(e)}",
                module="pdf_parser",
            )
            return self._empty_result()

    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        """Return an empty result template."""
        return {
            "invoice_number": None,
            "vendor_name": None,
            "invoice_date": None,
            "due_date": None,
            "total_amount": None,
            "currency": "USD",
            "line_items": [],
            "raw_text": "",
            "confidence": 0.0,
        }
