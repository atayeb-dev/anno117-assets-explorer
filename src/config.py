"""
Configuration management for Atayeb Assets Explorer.

Loads default paths and settings from config.json.
"""

# ============================================================
# IMPORTS
# ============================================================

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================
# MAIN
# ============================================================


def load_config() -> dict:
    """
    Load configuration from config.json.

    Returns:
        Dictionary with all configuration settings.

    Raises:
        FileNotFoundError: If config.json is not found.
        json.JSONDecodeError: If config.json is malformed.
    """
    config_path = Path.cwd() / "config.json"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    # Process paths: convert string paths to absolute Path objects
    paths = {}
    for key, value in config.get("paths", {}).items():
        if isinstance(value, str):
            paths[key] = Path.cwd() / value
        else:
            paths[key] = Path(value)

    config["paths"] = paths
    logger.info(f"Configuration loaded from {config_path}")

    return config


def get_path(key: str, config: dict | None = None) -> Path:
    """
    Get a path from configuration.

    Args:
        key: Key in config["paths"] dictionary.
        config: Configuration dictionary (loads if None).

    Returns:
        Path object for the requested key.

    Raises:
        KeyError: If key not found in paths.
    """
    if config is None:
        config = load_config()

    if key not in config["paths"]:
        raise KeyError(f"Path '{key}' not found in configuration")

    return config["paths"][key]
