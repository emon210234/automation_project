"""
Configuration loader for the automation platform.

Reads config.yaml and provides a typed configuration object.
Supports environment variable overrides for sensitive settings.
"""

import os
from pathlib import Path
from typing import Any, Dict

import yaml


def load_config(config_path: str = "") -> Dict[str, Any]:
    """Load configuration from YAML file with environment variable overrides.

    Args:
        config_path: Path to the config YAML file. If empty, uses the default.

    Returns:
        Dictionary with configuration values.
    """
    if not config_path:
        config_path = str(Path(__file__).parent / "config.yaml")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Environment variable overrides for sensitive settings
    env_overrides = {
        "database.path": "AUTOMATION_DB_PATH",
        "logging.level": "AUTOMATION_LOG_LEVEL",
        "email.username": "AUTOMATION_EMAIL_USER",
        "email.imap_server": "AUTOMATION_EMAIL_SERVER",
    }

    for config_key, env_var in env_overrides.items():
        env_val = os.environ.get(env_var)
        if env_val:
            keys = config_key.split(".")
            section = config
            for k in keys[:-1]:
                section = section.setdefault(k, {})
            section[keys[-1]] = env_val

    return config
