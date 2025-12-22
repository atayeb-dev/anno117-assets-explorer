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
    Uses the global config path if set, otherwise uses default config.json.

    Args:
        config: Configuration dictionary to reload if needed.
    """
    global _CONFIG_MTIME

    # Use the correct config file path
    config_path = _GLOBAL_CONFIG_PATH or Path.cwd() / DEFAULT_CONFIG_FILE
    if not config_path.exists():
        return

    current_mtime = config_path.stat().st_mtime
    if _CONFIG_MTIME is None or _CONFIG_MTIME != current_mtime:
        # File is new or has changed, reload it
        logger.debug(f"Config file modified, reloading from {config_path}")
        try:
            with config_path.open("r", encoding="utf-8") as f:
                new_config = json.load(f)

            # Update the provided config dict (in-place)
            config.clear()
            config.update(new_config)

            # Re-convert paths
            paths = {}
            for key, value in config.get("paths", {}).items():
                paths[key] = (
                    Path.cwd() / value if isinstance(value, str) else Path(value)
                )
            config["paths"] = paths

            _CONFIG_MTIME = current_mtime
            logger.info(f"Config reloaded from {config_path}")
        except Exception as e:
            logger.error(f"Failed to reload config: {e}")


# ============================================================
# GLOBAL CONFIG INSTANCE
# ============================================================

_GLOBAL_CONFIG = None
_GLOBAL_CONFIG_PATH = None  # Track which file the config came from


def set_global_config(config: dict, config_path: str | Path | None = None) -> None:
    """
    Set the global config instance.

    Used by main.py to initialize the global config with a custom config file.
    All subsequent get_config() calls will use this instance.

    Args:
        config: Configuration dictionary to use globally.
        config_path: Path to the config file (for saving updates).
    """
    global _GLOBAL_CONFIG, _GLOBAL_CONFIG_PATH
    _GLOBAL_CONFIG = config
    _GLOBAL_CONFIG_PATH = (
        Path(config_path) if config_path else Path.cwd() / DEFAULT_CONFIG_FILE
    )
    logger.info(f"Global config set from: {_GLOBAL_CONFIG_PATH}")


def get_config() -> dict:
    """
    Get global config instance with auto-reload.

    Smart access: Ensures config is always up-to-date by checking MTIME.
    All code should use this instead of accessing config directly.

    Returns:
        Configuration dictionary (guaranteed fresh from disk if modified).
    """
    global _GLOBAL_CONFIG

    if _GLOBAL_CONFIG is None:
        _GLOBAL_CONFIG = load_config()

    # Ensure up-to-date
    reload_config_if_needed(_GLOBAL_CONFIG)
    return _GLOBAL_CONFIG


# ============================================================
# CENTRALIZED CONFIG ACCESSORS
# ============================================================


def get_ui_keywords() -> list[str]:
    """
    Get UI filter keywords from config with auto-reload.

    Returns:
        List of keyword strings, guaranteed fresh from disk.
    """
    config = get_config()
    return config.get("ui", {}).get("related_filter_keywords", [])


def set_ui_keywords(keywords: list[str]) -> None:
    """
    Set UI filter keywords in config and save to disk.

    Saves to the config file that was loaded (custom or default).

    Args:
        keywords: List of keyword strings to save.
    """
    config = get_config()

    if "ui" not in config:
        config["ui"] = {}

    config["ui"]["related_filter_keywords"] = keywords

    # Persist to disk (use the correct config file path)
    try:
        from .utils import make_json_serializable

        config_path = _GLOBAL_CONFIG_PATH or Path.cwd() / DEFAULT_CONFIG_FILE
        serializable_config = make_json_serializable(config)
        with open(config_path, "w") as f:
            json.dump(serializable_config, f, indent=4)
        logger.info(f"Saved config keywords to {config_path}: {keywords}")
    except Exception as e:
        logger.error(f"Failed to save config: {e}")


def get_path_value(key: str) -> Path:
    """
    Get a path from configuration with auto-reload.

    Smart access: Ensures config is fresh before accessing.

    Args:
        key: Key in config["paths"] dictionary.

    Returns:
        Path object for the requested key.

    Raises:
        KeyError: If key not found in paths.
    """
    config = get_config()

    if key not in config.get("paths", {}):
        raise KeyError(f"Path '{key}' not found in configuration")

    return config["paths"][key]
