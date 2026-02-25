-- Invoice Automation Platform Database Schema
-- SQLite database for jobs, processed data, logs, and errors

-- Jobs table: stores all automation jobs
CREATE TABLE IF NOT EXISTS jobs (
    job_id          TEXT PRIMARY KEY,
    job_type        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'queued'
                    CHECK(status IN ('queued', 'processing', 'completed', 'failed', 'retrying')),
    priority        INTEGER NOT NULL DEFAULT 5,
    payload         TEXT,              -- JSON-encoded job parameters
    result          TEXT,              -- JSON-encoded result data
    retry_count     INTEGER NOT NULL DEFAULT 0,
    max_retries     INTEGER NOT NULL DEFAULT 3,
    error_message   TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Processed data table: stores extracted invoice data
CREATE TABLE IF NOT EXISTS processed_data (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT NOT NULL,
    invoice_number  TEXT,
    vendor_name     TEXT,
    invoice_date    TEXT,
    due_date        TEXT,
    total_amount    REAL,
    currency        TEXT DEFAULT 'USD',
    line_items      TEXT,              -- JSON-encoded line items
    raw_text        TEXT,
    confidence      REAL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

-- Logs table: stores structured execution logs
CREATE TABLE IF NOT EXISTS logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    level           TEXT NOT NULL,
    job_id          TEXT,
    module          TEXT,
    event           TEXT NOT NULL,
    message         TEXT,
    duration_ms     REAL,
    details         TEXT,              -- JSON-encoded extra details
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

-- Errors table: stores error records for analysis
CREATE TABLE IF NOT EXISTS errors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT,
    error_type      TEXT NOT NULL,
    error_message   TEXT NOT NULL,
    stack_trace     TEXT,
    occurred_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved        INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

-- Checkpoints table: stores state for crash recovery
CREATE TABLE IF NOT EXISTS checkpoints (
    job_id          TEXT NOT NULL,
    step_name       TEXT NOT NULL,
    step_data       TEXT,              -- JSON-encoded step state
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (job_id, step_name),
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

-- Metrics table: stores performance metrics
CREATE TABLE IF NOT EXISTS metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name     TEXT NOT NULL,
    metric_value    REAL NOT NULL,
    tags            TEXT,              -- JSON-encoded tags
    recorded_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_logs_job ON logs(job_id);
CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level);
CREATE INDEX IF NOT EXISTS idx_errors_job ON errors(job_id);
CREATE INDEX IF NOT EXISTS idx_processed_job ON processed_data(job_id);
CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name);
