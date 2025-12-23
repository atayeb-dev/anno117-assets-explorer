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
from pathlib import Path
from typing import Any
from src.log import log

# ============================================================
# CONSTANTS
# ============================================================

DEFAULT_CONFIG_FILE = "config.json"
# For tracking config file modifications
# REQUIRED_CONFIG_STRUCTURE = {
#     "paths": {
#         "workdir": False,
#         "unpacked_dir": False,
#         "rda_console_exec": False,
#         "assets_xml": False,
#         "assets_unpack_dir": False,
#         "gen_dir": False,
#     }
# }

# ============================================================
# GLOBAL CONFIG INSTANCE
# ============================================================

_GLOBAL_CONFIG = None
_CUSTOM_CONFIG_PATH = None

# ============================================================
# LOAD
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


def load_global_config(custom_config_path: str | Path | None = None) -> dict:
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
    # Load default config, stay silent.
    default_path = Path(DEFAULT_CONFIG_FILE)
    if default_path.exists():
        with default_path.open("r", encoding="utf-8") as f:
            default_config = json.load(f)

    # Load custom config, should be here if specified.
    custom_config = {}
    if custom_config_path:
        global _CUSTOM_CONFIG_PATH
        _CUSTOM_CONFIG_PATH = custom_config_path
        custom_config_path = Path(custom_config_path)
        if not custom_config_path.exists():
            raise FileNotFoundError(
                f"Custom config file not found: {custom_config_path}"
            )
        with custom_config_path.open("r", encoding="utf-8") as f:
            custom_config = json.load(f)

    global _GLOBAL_CONFIG
    _GLOBAL_CONFIG = _deep_merge(default_config, custom_config)


# ============================================================
# CENTRALIZED CONFIG METHODS
# ============================================================


def reload_config(custom_config_path: str | None = None) -> None:
    """
    Reload global configuration, optionally from a new custom path.

    Args:
        config_path: Optional new custom path to config file.
    """
    load_global_config(
        custom_config_path if custom_config_path else _CUSTOM_CONFIG_PATH
    )


def print_config_state() -> None:
    """Utility to print current global config for debugging."""
    if _GLOBAL_CONFIG is None:
        log("{err/Configuration unloaded}")
    else:
        log("{succ/Configuration loaded}")
    if _CUSTOM_CONFIG_PATH:
        log(f"{{succ/Custom configuration: {_CUSTOM_CONFIG_PATH}}}")


def print_config() -> None:
    """Utility to print current global config for debugging."""
    import pprint

    if _GLOBAL_CONFIG is None:
        print_config_state()
        return
    pprint.pprint(_GLOBAL_CONFIG)


def unload_config() -> None:
    """Utility to unload current global config."""
    global _GLOBAL_CONFIG
    _GLOBAL_CONFIG = None


def get_path(key: str) -> Path:
    """
    Get a path from configuration.
    Args:
        key: Key in config["paths"] dictionary.

    Returns:
        Path object for the requested key.

    Raises:
        KeyError: If key not found in paths.
    """

    if not _GLOBAL_CONFIG or key not in _GLOBAL_CONFIG.get("paths", {}):
        return select_file(
            f"Path '{key}' not found in configuration. Please select the file:"
        )

    return Path.cwd() / _GLOBAL_CONFIG["paths"][key]


def select_file(title: str = "Select a file") -> str:
    """Ask user to input file path."""
    log(f"\n{title}")
    filepath = input("Enter file path: ").strip()
    return Path(filepath)
