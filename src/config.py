"""
Configuration management for Atayeb Assets Explorer.

Loads and merges configuration from:
- config.json (default)
- Custom config files (optional, with partial merge support)

Architecture:
- load_config(): Main entry point, handles merging logic
- Config is loaded once at app startup and shared across all components
"""

# ============================================================
# IMPORTS
# ============================================================

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================

DEFAULT_CONFIG_FILE = "config.json"
PARTIAL_MERGE_KEY = "partial"

# For tracking config file modifications (like cache does)
_CONFIG_MTIME = None


# ============================================================
# UTILITIES
# ============================================================


def _deep_merge(base: dict, override: dict) -> dict:
    """
    Recursively merge override dict into base dict.

    Override values take precedence. Nested dicts are merged recursively.
    Missing values inherit from base.

    Args:
        base: Base configuration dictionary.
        override: Override configuration dictionary (takes precedence).

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

    Behavior:
    - If config_path is None: Uses default config.json
    - If config has 'partial: true': Merges with default (custom overrides defaults)
    - Otherwise: Uses custom config entirely
    - All paths are converted to absolute Path objects

    Args:
        config_path: Optional custom path to config file.

    Returns:
        Dictionary with all configuration settings.

    Raises:
        FileNotFoundError: If config.json is not found.
        json.JSONDecodeError: If config.json is malformed.
    """
    # Load default config
    default_config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not default_config_path.exists():
        raise FileNotFoundError(f"Config file not found: {default_config_path}")

    with default_config_path.open("r", encoding="utf-8") as f:
        default_config = json.load(f)

    # If no custom config, use default
    if config_path is None:
        config = default_config
    else:
        custom_path = Path(config_path)
        if not custom_path.exists():
            raise FileNotFoundError(f"Custom config file not found: {custom_path}")

        with custom_path.open("r", encoding="utf-8") as f:
            custom_config = json.load(f)

        # Merge if partial=true, otherwise replace
        if custom_config.get(PARTIAL_MERGE_KEY, False):
            logger.info(f"Merging partial config from {custom_path}")
            config = _deep_merge(default_config, custom_config)
        else:
            logger.info(f"Using custom config from {custom_path}")
            config = custom_config

    # Convert string paths to absolute Path objects
    paths = {}
    for key, value in config.get("paths", {}).items():
        paths[key] = Path.cwd() / value if isinstance(value, str) else Path(value)
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


def reload_config_if_needed(config: dict) -> None:
    """
    Reload config from disk if the file has been modified.

    Similar to cache reload logic - tracks file modification time.
    Useful when config.json is modified externally or by other processes.

    Args:
        config: Configuration dictionary to reload if needed.
    """
    global _CONFIG_MTIME

    config_path = Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        return

    current_mtime = config_path.stat().st_mtime
    if _CONFIG_MTIME is None or _CONFIG_MTIME != current_mtime:
        # File is new or has changed, reload it
        logger.debug("Config file modified, reloading from disk")
        try:
            with config_path.open("r", encoding="utf-8") as f:
                new_config = json.load(f)

            # Update the provided config dict (in-place)
            config.clear()
            config.update(new_config)

            # Re-convert paths
            paths = {}
            for key, value in config.get("paths", {}).items():
                paths[key] = Path.cwd() / value if isinstance(value, str) else Path(value)
            config["paths"] = paths

            _CONFIG_MTIME = current_mtime
            logger.info(f"Config reloaded from {config_path}")
        except Exception as e:
            logger.error(f"Failed to reload config: {e}")

