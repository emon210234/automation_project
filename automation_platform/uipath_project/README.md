# UiPath Integration Guide

This directory contains instructions for integrating UiPath as the orchestration layer
for the Invoice Automation Platform. UiPath acts as a controller, triggering Python
services while the Python engine handles all data processing.

---

## Architecture Overview

```
UiPath Orchestrator/Studio
    │
    ├── Main.xaml (Entry point)
    │     ├── InitializeWorkflow   → Set up config, check Python environment
    │     ├── JobDispatcher        → Call Python to create jobs
    │     ├── WorkerExecution      → Call Python worker to process jobs
    │     ├── MonitorCompletion    → Poll job statuses until done
    │     ├── ErrorHandler         → Handle failures, trigger retries
    │     └── ReportGenerator      → Call Python to generate final report
    │
    └── Python Services (called via Invoke Python / Run Process)
          ├── init_db.py
          ├── create_jobs.py
          └── start_worker.py
```

---

## UiPath Workflow Design

### Main.xaml

The main workflow orchestrates the entire automation lifecycle:

1. **Initialize**
   - Activity: `Assign` to set configuration variables
   - Set `pythonPath` = `"python"` (or full path to Python executable)
   - Set `projectDir` = `"C:\automation_project"` (path to project folder)

2. **Initialize Database**
   - Activity: `Start Process` or `Invoke Python Method`
   - Command: `python -m automation_platform.scripts.init_db`
   - Working directory: `projectDir`

3. **Create Jobs**
   - Activity: `Start Process`
   - Command: `python -m automation_platform.scripts.create_jobs`
   - This queues all pending invoices for processing

4. **Start Worker**
   - Activity: `Start Process` (run asynchronously)
   - Command: `python -m automation_platform.scripts.start_worker`
   - The worker processes all queued jobs

5. **Monitor Completion**
   - Activity: `Do While` loop
   - Condition: Check if all jobs are completed
   - Use `Start Process` to run a status check script
   - `Delay` activity between polls (5 seconds)

6. **Generate Report**
   - Activity: `Start Process`
   - Command: `python -c "from automation_platform.scripts.create_jobs import ...; ..."`
   - Or create a dedicated report script

7. **Error Handling**
   - Activity: `Try Catch` around each major section
   - On failure: Log error, retry up to 3 times, send notification

### Job Dispatcher Sequence

```
Sequence: JobDispatcher
  ├── Log Message: "Starting job dispatch"
  ├── Start Process
  │     FileName: pythonPath
  │     Arguments: "-m automation_platform.scripts.create_jobs"
  │     WorkingDirectory: projectDir
  ├── If (exitCode != 0)
  │     Then: Throw BusinessRuleException
  └── Log Message: "Jobs dispatched successfully"
```

### Worker Execution Sequence

```
Sequence: WorkerExecution
  ├── Log Message: "Starting worker"
  ├── Start Process (Async)
  │     FileName: pythonPath
  │     Arguments: "-m automation_platform.scripts.start_worker"
  │     WorkingDirectory: projectDir
  ├── Delay: 00:00:05
  └── Log Message: "Worker started"
```

### Failure Handling

```
TryCatch: MainErrorHandler
  Try:
    [Main workflow activities]
  Catch System.Exception:
    ├── Log Message: "Error: " + exception.Message
    ├── Retry Scope (MaxRetries=3)
    │     ├── [Retry the failed activity]
    └── If still failing:
          ├── Send notification
          └── Terminate workflow
```

---

## UiPath Activities Used

| Activity | Purpose |
|----------|---------|
| `Start Process` | Launch Python scripts as external processes |
| `Assign` | Set configuration variables |
| `If` | Conditional logic for error checking |
| `Do While` | Poll for job completion |
| `Delay` | Wait between poll cycles |
| `Try Catch` | Error handling wrapper |
| `Retry Scope` | Automatic retry on failure |
| `Log Message` | Workflow logging |
| `Throw` | Raise exceptions for error handling |

---

## Passing Arguments to Python

Arguments are passed via command-line arguments to `Start Process`:

```
FileName: "python"
Arguments: "-m automation_platform.scripts.create_jobs --input-dir C:\invoices"
WorkingDirectory: "C:\automation_project"
```

For reading results, Python scripts write output to:
- **Database**: Job statuses and processed data in SQLite
- **CSV Reports**: Generated in `automation_platform/reports/`
- **Stdout**: Exit codes and summary messages

UiPath reads results by:
1. Checking the exit code of `Start Process`
2. Reading generated CSV/JSON report files using `Read Text File` activity
3. Optionally querying the SQLite database via Python helper scripts

---

## Configuration in UiPath Studio

1. **Create a new UiPath project** in UiPath Studio
2. **Add variables** in the Variables panel:
   - `pythonPath` (String) = Path to Python executable
   - `projectDir` (String) = Path to automation_project directory
   - `pollInterval` (TimeSpan) = TimeSpan.FromSeconds(5)
   - `maxRetries` (Int32) = 3
3. **Set up Config file** (optional): Use UiPath Config.xlsx for environment-specific settings
4. **Install Python activities** (optional): UiPath.Python.Activities package from NuGet

---

## Setup Steps

1. Install Python 3.9+ on the machine running UiPath
2. Clone/copy the automation_project to a local directory
3. Create virtual environment: `python -m venv venv`
4. Install dependencies: `venv\Scripts\pip install -r requirements.txt`
5. Update `pythonPath` in UiPath to point to `venv\Scripts\python.exe`
6. Open UiPath Studio and create a new project
7. Build the Main.xaml following the design above
8. Test each activity individually before running the full workflow

---

## Security Notes

- Store email credentials in UiPath Orchestrator Assets (Credential type)
- Use environment variables for sensitive Python configuration
- Never hardcode passwords in YAML config or UiPath workflows
- Use Windows Credential Manager or UiPath Vault for production
