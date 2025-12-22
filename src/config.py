"""
Configuration management for Atayeb Assets Explorer.

Loads default paths and settings from config.json.
Supports custom config files with partial merging.
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


def _deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge override dict into base dict.

    Override values take precedence. Missing values inherit from base.

    Args:
        base: Base configuration dictionary.
        override: Override configuration dictionary.

    Returns:
        Merged configuration dictionary.
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def load_config(config_path: str | Path | None = None) -> dict:
    """
    Load configuration from config.json or custom config file.

    If custom config has 'partial: true', merges with default config
    (custom values override, missing values inherit from default).

    Args:
        config_path: Optional custom path to config file.
                    Defaults to config.json in cwd.

    Returns:
        Dictionary with all configuration settings.

    Raises:
        FileNotFoundError: If config.json is not found.
        json.JSONDecodeError: If config.json is malformed.
    """
    # Load default config
    default_config_path = Path.cwd() / "config.json"

    if not default_config_path.exists():
        raise FileNotFoundError(f"Config file not found: {default_config_path}")

    with default_config_path.open("r", encoding="utf-8") as f:
        default_config = json.load(f)

    # If no custom config provided, use default
    if config_path is None:
        config = default_config
    else:
        custom_path = Path(config_path)

        if not custom_path.exists():
            raise FileNotFoundError(f"Custom config file not found: {custom_path}")

        with custom_path.open("r", encoding="utf-8") as f:
            custom_config = json.load(f)

        # Merge if partial=true
        if custom_config.get("partial", False):
            logger.info(
                f"Merging partial config from {custom_path} with default config"
            )
            config = _deep_merge(default_config, custom_config)
        else:
            logger.info(f"Using custom config from {custom_path}")
            config = custom_config

    # Process paths: convert string paths to absolute Path objects
    paths = {}
    for key, value in config.get("paths", {}).items():
        if isinstance(value, str):
            paths[key] = Path.cwd() / value
        else:
            paths[key] = Path(value)

    config["paths"] = paths
    config_source = config_path if config_path else default_config_path
    logger.info(f"Configuration loaded from {config_source}")

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
