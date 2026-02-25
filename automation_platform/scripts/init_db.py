#!/usr/bin/env python3
"""
Initialize Database - Sets up the SQLite database with the required schema.

Usage:
    python -m automation_platform.scripts.init_db
"""

import sys
from pathlib import Path

# Allow running as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from automation_platform.config.settings import load_config
from automation_platform.database.db_manager import DatabaseManager


def main() -> None:
    config = load_config()
    db_path = config.get("database", {}).get("path", "automation_platform/data/automation.db")
    print(f"Initializing database at: {db_path}")

    db = DatabaseManager(db_path)
    db.initialize()
    db.close()

    print("Database initialized successfully.")


if __name__ == "__main__":
    main()
