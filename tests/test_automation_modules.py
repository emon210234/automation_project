"""Tests for the automation modules."""

import csv
import os
import tempfile

import pytest

from automation_platform.automation_modules.data_validator import DataValidator
from automation_platform.automation_modules.email_processor import EmailProcessor
from automation_platform.automation_modules.pdf_parser import PDFParser
from automation_platform.automation_modules.report_generator import ReportGenerator
from automation_platform.database.db_manager import DatabaseManager
from automation_platform.monitoring.logger import StructuredLogger


@pytest.fixture
def logger(tmp_path):
    return StructuredLogger(
        log_dir=str(tmp_path / "logs"),
        log_to_db=False,
    )


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    manager = DatabaseManager(db_path)
    manager.initialize()
    yield manager
    manager.close()


class TestDataValidator:
    def test_valid_invoice(self, logger):
        validator = DataValidator(logger)
        data = {
            "invoice_number": "INV-001",
            "vendor_name": "Test Corp",
            "total_amount": 100.0,
            "invoice_date": "01/15/2024",
        }
        result = validator.validate_invoice(data)
        assert result["is_valid"] is True
        assert len(result["errors"]) == 0

    def test_missing_required_fields(self, logger):
        validator = DataValidator(logger)
        data = {"currency": "USD"}
        result = validator.validate_invoice(data)
        assert result["is_valid"] is False
        assert len(result["errors"]) == 3  # invoice_number, vendor_name, total_amount

    def test_negative_amount(self, logger):
        validator = DataValidator(logger)
        data = {
            "invoice_number": "INV-001",
            "vendor_name": "Test",
            "total_amount": -50.0,
        }
        result = validator.validate_invoice(data)
        assert result["is_valid"] is False
        assert any("negative" in e for e in result["errors"])

    def test_zero_amount_warning(self, logger):
        validator = DataValidator(logger)
        data = {
            "invoice_number": "INV-001",
            "vendor_name": "Test",
            "total_amount": 0,
        }
        result = validator.validate_invoice(data)
        assert result["is_valid"] is True
        assert any("zero" in w for w in result["warnings"])

    def test_large_amount_warning(self, logger):
        validator = DataValidator(logger)
        data = {
            "invoice_number": "INV-001",
            "vendor_name": "Test",
            "total_amount": 50_000_000,
        }
        result = validator.validate_invoice(data)
        assert result["is_valid"] is True
        assert any("large" in w.lower() for w in result["warnings"])

    def test_invalid_date_warning(self, logger):
        validator = DataValidator(logger)
        data = {
            "invoice_number": "INV-001",
            "vendor_name": "Test",
            "total_amount": 100.0,
            "invoice_date": "not-a-date",
        }
        result = validator.validate_invoice(data)
        assert result["is_valid"] is True
        assert any("parse" in w.lower() for w in result["warnings"])

    def test_valid_date_formats(self, logger):
        validator = DataValidator(logger)
        for date_str in ["01/15/2024", "2024-01-15", "15.01.2024"]:
            data = {
                "invoice_number": "INV-001",
                "vendor_name": "Test",
                "total_amount": 100.0,
                "invoice_date": date_str,
            }
            result = validator.validate_invoice(data)
            assert result["is_valid"] is True


class TestEmailProcessor:
    def test_collect_simulation(self, logger):
        processor = EmailProcessor(logger)
        result = processor.collect({"source": "email", "sender": "test@example.com"})
        assert result["source"] == "email"
        assert result["sender"] == "test@example.com"

    def test_parse_email_content(self, logger):
        raw = "From: vendor@example.com\nSubject: Invoice\nDate: Mon, 1 Jan 2024\n\nBody text"
        result = EmailProcessor.parse_email_content(raw)
        assert result["sender"] == "vendor@example.com"
        assert result["subject"] == "Invoice"


class TestPDFParser:
    def test_extract_nonexistent_file(self, logger):
        parser = PDFParser(logger)
        result = parser.extract("/nonexistent/file.pdf")
        assert result["invoice_number"] is None
        assert result["confidence"] == 0.0

    def test_empty_result(self, logger):
        result = PDFParser._empty_result()
        assert result["invoice_number"] is None
        assert result["total_amount"] is None

    def test_extract_csv(self, logger, tmp_path):
        csv_path = str(tmp_path / "test.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "invoice_number", "vendor_name", "invoice_date",
                "due_date", "total_amount", "currency",
            ])
            writer.writeheader()
            writer.writerow({
                "invoice_number": "INV-CSV-001",
                "vendor_name": "CSV Vendor",
                "invoice_date": "01/01/2024",
                "due_date": "02/01/2024",
                "total_amount": "1500.00",
                "currency": "USD",
            })

        parser = PDFParser(logger)
        result = parser.extract_csv(csv_path)
        assert result["invoice_number"] == "INV-CSV-001"
        assert result["total_amount"] == 1500.0
        assert result["vendor_name"] == "CSV Vendor"

    def test_extract_csv_nonexistent(self, logger):
        parser = PDFParser(logger)
        result = parser.extract_csv("/nonexistent/file.csv")
        assert result["invoice_number"] is None

    def test_parse_text(self, logger):
        parser = PDFParser(logger)
        text = """
        Invoice Number: INV-2024-100
        From: Acme Corporation
        Date: 01/15/2024
        Due Date: 02/15/2024
        Total: $1,250.00
        """
        result = parser._parse_text(text)
        assert result["invoice_number"] == "INV-2024-100"
        assert result["total_amount"] == 1250.0
        assert result["currency"] == "USD"
        assert result["confidence"] > 0


class TestReportGenerator:
    def test_generate_csv_report(self, db, logger, tmp_path):
        db.create_job("j1", "test")
        db.store_processed_data({
            "job_id": "j1",
            "invoice_number": "INV-001",
            "vendor_name": "Test",
            "total_amount": 100.0,
        })

        gen = ReportGenerator(db, logger, str(tmp_path / "reports"))
        path = gen.generate_csv_report("test_report.csv")
        assert os.path.exists(path)

        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["invoice_number"] == "INV-001"

    def test_generate_summary(self, db, logger):
        db.create_job("j1", "test")
        db.create_job("j2", "test")
        db.update_job_status("j1", "completed")
        db.update_job_status("j2", "completed")
        db.store_processed_data({
            "job_id": "j1",
            "invoice_number": "A",
            "vendor_name": "V1",
            "total_amount": 100.0,
        })
        db.store_processed_data({
            "job_id": "j2",
            "invoice_number": "B",
            "vendor_name": "V2",
            "total_amount": 200.0,
        })

        gen = ReportGenerator(db, logger)
        summary = gen.generate_summary()
        assert summary["total_invoices_processed"] == 2
        assert summary["total_amount"] == 300.0

    def test_generate_csv_report_empty(self, db, logger, tmp_path):
        gen = ReportGenerator(db, logger, str(tmp_path / "reports"))
        path = gen.generate_csv_report("empty.csv")
        assert isinstance(path, str)
