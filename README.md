# Invoice Automation Platform

A production-grade, modular automation platform for processing invoices at scale, built with Python as the core engine and UiPath as the orchestration layer.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Why Invoice Automation?](#why-invoice-automation)
- [Folder Structure](#folder-structure)
- [Design Principles](#design-principles)
- [Components](#components)
  - [1. Automation Orchestrator (UiPath)](#1-automation-orchestrator-uipath)
  - [2. Python Automation Engine](#2-python-automation-engine)
  - [3. Task Queue System](#3-task-queue-system)
  - [4. State Management](#4-state-management)
  - [5. Observability Layer](#5-observability-layer)
  - [6. Data Processing Layer](#6-data-processing-layer)
  - [7. Storage Layer](#7-storage-layer)
  - [8. Automation Modules](#8-automation-modules)
- [Setup Guide](#setup-guide)
- [Real Execution Flow](#real-execution-flow)
- [UiPath Integration](#uipath-integration)
- [Failure Recovery](#failure-recovery)
- [Testing Strategy](#testing-strategy)
- [Security Design](#security-design)
- [Scaling the System](#scaling-the-system)
- [Library Justification](#library-justification)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    UiPath Orchestrator                          │
│  (Trigger Jobs • Schedule • Monitor • Retry • Report)          │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Calls Python via Start Process
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Python Automation Engine                        │
│                                                                 │
│  ┌──────────┐  ┌───────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ Scheduler │→│ Job Queue  │→│  Job Runner   │→│  Modules   │ │
│  └──────────┘  └───────────┘  └──────────────┘  └───────────┘ │
│       │              │              │                  │        │
│       │              ▼              ▼                  │        │
│       │       ┌─────────────┐ ┌──────────────┐        │        │
│       │       │   State     │ │   Metrics    │        │        │
│       │       │   Manager   │ │   Collector  │        │        │
│       │       └─────────────┘ └──────────────┘        │        │
│       │                                               │        │
│       └───────────────────┬───────────────────────────┘        │
│                           ▼                                    │
│                  ┌──────────────────┐                           │
│                  │  SQLite Database  │                           │
│                  │  (Jobs, Data,     │                           │
│                  │   Logs, Errors)   │                           │
│                  └──────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

### Processing Pipeline

Each job flows through a 5-step pipeline:

```
Ingestion → Parsing → Validation → Storage → Reporting
```

Each step creates a checkpoint so the system can resume from any failure point.

---

## Why Invoice Automation?

**Invoice processing** is one of the most common enterprise automation use cases. Companies process hundreds to thousands of invoices daily, and manual processing is:

- **Error-prone**: Manual data entry leads to ~4% error rate
- **Time-consuming**: Each invoice takes 15-25 minutes manually
- **Costly**: Average cost per invoice manually processed is $15-40

This platform automates the full cycle: collect invoices → extract data → validate → store → report.

---

## Folder Structure

```
automation_platform/
├── core/                           # Core engine components
│   ├── __init__.py
│   ├── job_queue.py                # Persistent task queue (enqueue/dequeue/retry)
│   ├── job_runner.py               # Worker engine that processes jobs through pipeline
│   ├── state_manager.py            # Checkpoint system for crash recovery
│   └── scheduler.py                # Batch job creation and scheduling
│
├── automation_modules/             # Modular automation components
│   ├── __init__.py
│   ├── email_processor.py          # Email collection and attachment extraction
│   ├── pdf_parser.py               # PDF/CSV text extraction and field parsing
│   ├── data_validator.py           # Business rule validation for invoice data
│   └── report_generator.py         # CSV/summary report generation
│
├── database/                       # Persistence layer
│   ├── __init__.py
│   ├── db_manager.py               # Thread-safe SQLite database operations
│   └── schema.sql                  # Database schema (jobs, data, logs, errors)
│
├── monitoring/                     # Observability layer
│   ├── __init__.py
│   ├── logger.py                   # Structured logging (file + database)
│   └── metrics.py                  # Performance metrics tracking
│
├── config/                         # Configuration
│   ├── __init__.py
│   ├── config.yaml                 # Platform configuration file
│   └── settings.py                 # Config loader with env var overrides
│
├── scripts/                        # Entry point scripts
│   ├── init_db.py                  # Initialize the database
│   ├── create_jobs.py              # Create sample invoice jobs
│   └── start_worker.py             # Start the job processing worker
│
├── uipath_project/                 # UiPath integration documentation
│   └── README.md                   # Detailed UiPath workflow instructions
│
├── reports/                        # Generated reports (CSV output)
└── logs/                           # Log files
```

---

## Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Production-ready** | Type hints, error handling, configurable settings, structured logging |
| **Fault-tolerant** | Checkpoint system, automatic retries, stale job recovery |
| **Modular** | Each component is independently testable and replaceable |
| **Observable** | Structured logs in files + database, performance metrics |
| **Extensible** | Add new job types by creating new automation modules |
| **Maintainable** | Clean separation of concerns, comprehensive test suite |

---

## Components

### 1. Automation Orchestrator (UiPath)

UiPath serves as the orchestration layer, managing the job lifecycle:

- **Trigger jobs**: Start the automation platform on schedule or on-demand
- **Schedule automation**: Configure recurring runs via UiPath Orchestrator
- **Call Python services**: Execute Python scripts via `Start Process` activity
- **Monitor execution**: Poll job statuses and track completion
- **Retry failed jobs**: Re-trigger processing for failed jobs
- **Generate reports**: Call report generation after processing completes

See [`uipath_project/README.md`](automation_platform/uipath_project/README.md) for detailed workflow design.

### 2. Python Automation Engine

The engine is built around the `JobRunner` class which processes jobs through a 5-step pipeline:

```python
# Each job flows through these steps:
steps = [
    ("ingestion",  _step_ingestion),   # Load/collect input data
    ("parsing",    _step_parsing),     # Extract structured fields
    ("validation", _step_validation),  # Validate against business rules
    ("storage",    _step_storage),     # Persist to database
    ("reporting",  _step_reporting),   # Generate report entry
]
```

**Key features:**
- Processes multiple automation tasks (PDF, CSV, email sources)
- Automatic retry with configurable max attempts
- Checkpoint after each step for crash recovery
- Performance tracking for each step

### 3. Task Queue System

The queue is implemented as a persistent SQLite-backed system (`core/job_queue.py`).

**Job schema:**

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | TEXT | Unique identifier (UUID) |
| `job_type` | TEXT | Type of automation (e.g., `invoice_processing`) |
| `status` | TEXT | `queued` → `processing` → `completed` / `failed` / `retrying` |
| `priority` | INTEGER | Lower number = higher priority (1-10) |
| `payload` | TEXT | JSON-encoded job parameters |
| `result` | TEXT | JSON-encoded processing result |
| `retry_count` | INTEGER | Number of retry attempts |
| `max_retries` | INTEGER | Maximum allowed retries (default: 3) |
| `error_message` | TEXT | Last error message |
| `created_at` | TIMESTAMP | Job creation time |
| `started_at` | TIMESTAMP | Processing start time |
| `completed_at` | TIMESTAMP | Completion time |

**Job lifecycle:**
```
queued → processing → completed
                   ↘ failed
                   ↘ retrying → queued (re-enqueued)
```

### 4. State Management

The `StateManager` (`core/state_manager.py`) provides crash recovery through checkpoints:

- **Checkpoint system**: After each pipeline step, state is saved to the database
- **Task recovery**: On restart, the system checks for incomplete jobs with existing checkpoints
- **Safe restart**: Jobs resume from the last completed step, not from the beginning

```python
# Example: Job crashes during validation
# On restart, it finds checkpoints for ingestion and parsing
# It skips those steps and resumes from validation
resume_step = state_manager.get_resume_step(job_id)  # Returns "validation"
```

### 5. Observability Layer

**Structured Logging** (`monitoring/logger.py`):
- Every log includes: timestamp, level, event type, job_id, module, duration, message
- Dual output: console + rotating log files + database
- Format: `2024-01-15 10:30:00 | INFO | event=job_completed | job_id=abc-123 | duration_ms=450.2 | msg=...`

**Metrics** (`monitoring/metrics.py`):
- Track step durations, job counts, success/failure rates
- Context manager for automatic duration tracking
- Counters for aggregate statistics

### 6. Data Processing Layer

| Module | Purpose | Libraries Used |
|--------|---------|---------------|
| `pdf_parser.py` | Extract text from PDFs, parse invoice fields | `pdfplumber`, `re` |
| `email_processor.py` | Collect emails, extract attachments | `email` (stdlib) |
| `data_validator.py` | Validate fields, check business rules | `re`, `datetime` |
| `report_generator.py` | Generate CSV reports, summaries | `csv`, `pandas` |

### 7. Storage Layer

SQLite database with the following tables:

| Table | Purpose |
|-------|---------|
| `jobs` | Job queue and status tracking |
| `processed_data` | Extracted invoice data (number, vendor, amount, etc.) |
| `logs` | Structured execution logs |
| `errors` | Error records for analysis |
| `checkpoints` | State checkpoints for crash recovery |
| `metrics` | Performance metrics |

Full schema is in [`database/schema.sql`](automation_platform/database/schema.sql).

### 8. Automation Modules

| Module | Responsibility |
|--------|---------------|
| `email_processor.py` | Connects to mail servers, filters invoices, downloads attachments |
| `pdf_parser.py` | Extracts text from PDFs using pdfplumber, parses fields with regex |
| `data_validator.py` | Validates required fields, amounts, dates, business rules |
| `report_generator.py` | Generates CSV reports and summary statistics from processed data |

---

## Setup Guide

### Prerequisites

- Python 3.9+
- UiPath Studio (for orchestration, optional for standalone use)

### Step-by-Step Setup

```bash
# 1. Clone the repository
git clone <repository-url>
cd automation_project

# 2. Create virtual environment
python -m venv venv

# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Initialize the database
python -m automation_platform.scripts.init_db

# 5. Create sample jobs (for testing)
python -m automation_platform.scripts.create_jobs

# 6. Start the worker to process jobs
python -m automation_platform.scripts.start_worker
# Press Ctrl+C to stop

# 7. Run tests
python -m pytest tests/ -v
```

### Environment Variables (Optional)

| Variable | Purpose |
|----------|---------|
| `AUTOMATION_DB_PATH` | Override database file path |
| `AUTOMATION_LOG_LEVEL` | Set log level (DEBUG, INFO, WARNING, ERROR) |
| `AUTOMATION_EMAIL_USER` | Email username for IMAP collection |
| `AUTOMATION_EMAIL_PASSWORD` | Email password (never in config files) |
| `AUTOMATION_EMAIL_SERVER` | IMAP server address |

---

## Real Execution Flow

### Scenario: Company receives 500 invoices daily

```
1. COLLECT INVOICES
   - Invoices arrive as PDF attachments via email or file drop
   - Scheduler scans input directory for new files
   - Jobs are created for each invoice

2. CREATE JOBS
   - Each invoice becomes a job with unique ID
   - Jobs are stored in SQLite with status "queued"
   - Priority can be set (urgent invoices get priority 1)

3. QUEUE PROCESSING
   - Worker polls the queue for available jobs
   - Jobs are dequeued in priority order (lowest number first)
   - Status changes from "queued" to "processing"

4. PROCESS EACH INVOICE
   Step 1 - Ingestion:  Load file, identify source type
   Step 2 - Parsing:    Extract text, find invoice number/vendor/amount/dates
   Step 3 - Validation: Check required fields, validate amounts, verify dates
   Step 4 - Storage:    Store validated data in processed_data table
   Step 5 - Reporting:  Record processing result

5. VALIDATE DATA
   - Required fields: invoice_number, vendor_name, total_amount
   - Business rules: amount > 0, valid date formats
   - Warnings for unusual values (amount > $10M, short invoice numbers)

6. STORE RESULTS
   - Valid invoices → processed_data table
   - Invalid invoices → job marked with validation errors
   - All processing → logged with timestamps and durations

7. GENERATE REPORT
   - CSV export of all processed invoices
   - Summary: total count, total amount, by vendor, by currency
   - Job statistics: completed, failed, retry counts
```

---

## UiPath Integration

UiPath orchestrates the Python engine through `Start Process` activities:

### Key Activities

| Step | UiPath Activity | Python Command |
|------|----------------|----------------|
| Initialize DB | `Start Process` | `python -m automation_platform.scripts.init_db` |
| Create Jobs | `Start Process` | `python -m automation_platform.scripts.create_jobs` |
| Start Worker | `Start Process` | `python -m automation_platform.scripts.start_worker` |

### Main.xaml Design

```
Main.xaml
├── TryCatch (Global error handler)
│   ├── Initialize: Set pythonPath, projectDir variables
│   ├── Start Process: init_db.py
│   ├── Start Process: create_jobs.py
│   ├── Start Process: start_worker.py (async)
│   ├── Do While: Poll job status until all complete
│   │   ├── Delay: 5 seconds
│   │   └── Check: Read job stats via Python script
│   └── Log: Report final summary
└── Catch: Log error, retry, or notify
```

See [`uipath_project/README.md`](automation_platform/uipath_project/README.md) for full details.

---

## Failure Recovery

### Simulated Failure Scenarios

| Failure Type | How It's Handled |
|-------------|-----------------|
| **Network failure** | Job fails, retry mechanism re-queues with exponential backoff |
| **Corrupt file** | PDF parser catches exception, job marked failed with error details |
| **Database error** | Transaction rollback via context manager, job stays in current state |
| **Timeout** | Stale job recovery resets "processing" jobs older than 30 minutes |
| **Worker crash** | On restart, `recover_stale_jobs()` re-queues stuck jobs; checkpoints allow resuming from last step |
| **Invalid data** | Validation step catches issues, job completes but data not stored |

### Recovery Mechanisms

1. **Automatic Retry**: Jobs retry up to `max_retries` (default: 3) before permanent failure
2. **Checkpoint Resume**: After crash, jobs resume from the last completed pipeline step
3. **Stale Job Recovery**: Worker startup scans for jobs stuck in "processing" state
4. **Error Logging**: All errors stored in both error table and log table for analysis

---

## Testing Strategy

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=automation_platform --cov-report=term-missing

# Run specific test module
python -m pytest tests/test_job_queue.py -v
python -m pytest tests/test_job_runner.py -v
python -m pytest tests/test_automation_modules.py -v
```

### Test Coverage

| Test File | What It Tests |
|-----------|--------------|
| `test_db_manager.py` | Database CRUD operations, schema integrity, checkpoints |
| `test_job_queue.py` | Enqueue, dequeue, priority, retry logic, stats |
| `test_state_manager.py` | Checkpoint save/load, resume logic, step skipping |
| `test_job_runner.py` | Full pipeline processing, validation failures, resume, batch processing |
| `test_automation_modules.py` | PDF parsing, CSV extraction, data validation, email processing, reports |

---

## Security Design

| Concern | Solution |
|---------|----------|
| **Credential storage** | Environment variables for passwords; never in config.yaml or code |
| **Database access** | SQLite file permissions; WAL mode for concurrent safety |
| **Secrets handling** | UiPath Orchestrator Assets for production credentials |
| **Config security** | `settings.py` supports env var overrides for all sensitive fields |
| **Error exposure** | Stack traces stored in DB only, not exposed to end users |

---

## Scaling the System

### From Local to Enterprise

| Level | Enhancement |
|-------|-------------|
| **Multiple Workers** | Run multiple `start_worker.py` instances (SQLite WAL supports concurrent reads) |
| **Cloud Database** | Replace SQLite with PostgreSQL by updating `db_manager.py` |
| **API Interface** | Add Flask/FastAPI layer to expose job creation and status endpoints |
| **Message Queue** | Replace SQLite queue with Redis or RabbitMQ for distributed processing |
| **Cloud Deployment** | Containerize with Docker, deploy to AWS/Azure/GCP |
| **Apache Airflow** | Replace UiPath orchestration with Airflow DAGs for complex scheduling |
| **UiPath Orchestrator** | Connect to UiPath Cloud for enterprise-grade scheduling and monitoring |

### Adding New Automation Types

1. Create a new module in `automation_modules/`
2. Register the job type in `job_runner.py`
3. Add validation rules in `data_validator.py`
4. Create jobs with the new type via `job_queue.enqueue(job_type="new_type", ...)`

---

## Library Justification

| Library | Purpose | Why This Library |
|---------|---------|-----------------|
| `pdfplumber` | PDF text extraction | High accuracy, table support, pure Python, actively maintained |
| `pandas` | Data analysis and reporting | Industry standard for tabular data, powerful aggregation |
| `pyyaml` | Configuration parsing | Standard YAML parser, clean syntax for config files |
| `requests` | HTTP requests | Simple API for web interactions, connection pooling |
| `beautifulsoup4` | HTML parsing | Robust HTML/XML parser for web scraping scenarios |
| `sqlite3` | Database | Zero-config, ACID compliant, perfect for local deployment |
| `re` (regex) | Pattern matching | Built-in, efficient for extracting invoice fields from text |
| `csv` | CSV processing | Built-in, handles standard CSV I/O reliably |
| `pytest` | Testing | Feature-rich, fixtures, parametrize, excellent for Python testing |

---

## Debugging Guide

### Common Issues

| Issue | Solution |
|-------|---------|
| `ModuleNotFoundError` | Ensure virtual environment is activated and dependencies installed |
| Database locked | Check for multiple processes accessing the same DB file |
| Jobs stuck in "processing" | Run `python -c "from automation_platform.core.job_queue import ...; queue.recover_stale_jobs()"` |
| No jobs processing | Check queue stats: `python -c "..."` to verify jobs are in "queued" status |

### Inspecting the Database

```bash
# Open SQLite CLI
sqlite3 automation_platform/data/automation.db

# Check job status
SELECT status, COUNT(*) FROM jobs GROUP BY status;

# View recent errors
SELECT * FROM errors ORDER BY occurred_at DESC LIMIT 10;

# View processing logs
SELECT * FROM logs WHERE level = 'ERROR' ORDER BY timestamp DESC;

# Check checkpoints
SELECT * FROM checkpoints;
```

---

## License

This project is provided as-is for educational and professional use.
