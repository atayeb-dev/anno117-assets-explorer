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
from .log import log, pp_log

# ============================================================
# CONSTANTS
# ============================================================

DEFAULT_CONFIG_FILE = "config.json"

_GLOBAL_CONFIG = None
_CUSTOM_CONFIG_FILE = None

# ============================================================
# GLOBAL CONFIG INSTANCE
# ============================================================


class ConfigPath(Path):
    """Custom Path subclass for configuration paths."""

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, *args, **kwargs)


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
        global _CUSTOM_CONFIG_FILE
        _CUSTOM_CONFIG_FILE = custom_config_path
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
        custom_config_path if custom_config_path else _CUSTOM_CONFIG_FILE
    )


def print_config_state() -> None:
    """Utility to print current global config for debugging."""
    if _GLOBAL_CONFIG is None:
        log("{err/Configuration unloaded}")
    else:
        log("{succ/Configuration loaded}")
    if _CUSTOM_CONFIG_FILE:
        log(f"{{succ/Custom configuration: {_CUSTOM_CONFIG_FILE}}}")


def print_config(path: str | None = None) -> None:
    """Utility to print current global config for debugging."""
    if _GLOBAL_CONFIG is None:
        print_config_state()
        return
    if not path:
        pp_log(_GLOBAL_CONFIG)
    else:
        value = get_value_or_none(path)
        pp_log({path: value})


def unload_config() -> None:
    """Utility to unload current global config."""
    global _GLOBAL_CONFIG
    _GLOBAL_CONFIG = None


def _get_nested_dict(d: dict, path: str, default=None):
    keys = path.split(".")
    value = d
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default
    return value


def _get_value_or_none(key: str, default=None, type="str") -> any | None:
    """
    Get a value from global configuration, or None if not found.

    Args:
        key: Key in global configuration dictionary.

    Returns:
        Value for the requested key, or None if not found.
    """
    if not _GLOBAL_CONFIG:
        return None
    config_value = _get_nested_dict(_GLOBAL_CONFIG, key, default=default)
    if config_value is None:
        config_value = _get_nested_dict(
            _GLOBAL_CONFIG, key, default=default
        )  # try global
    return config_value


def get_value_or_none(key: str, default=None, prefix="") -> any | None:
    """
    Get a value from global configuration, or None if not found.

    Args:
        key: Key in global configuration dictionary.

    Returns:
        Value for the requested key, or None if not found.
    """
    return _get_value_or_none(f"{prefix}{key}", default=default)


def get_str_value(key: str, default="", prefix="") -> str:
    str_value = _get_value_or_none(f"{prefix}{key}", default=default)
    if str_value is None:
        return ""
    return str(str_value)


def get_bool_value(key: str, default=False, prefix="") -> bool:
    bool_value = _get_value_or_none(f"{prefix}{key}", default=default)
    if bool_value is None:
        return False
    return bool(bool_value)


def get_file_path(key: str, default=None, prefix="") -> ConfigPath:
    """
    Get a path from configuration.
    Args:
        key: Key in config["paths"] dictionary.

    Returns:
        Path object for the requested key.

    Raises:
        KeyError: If key not found in paths.
    """
    path_value = _get_value_or_none(f"{prefix}paths.{key}", default=default)
    if path_value is None:
        return default
    return ConfigPath(Path.cwd() / path_value)
