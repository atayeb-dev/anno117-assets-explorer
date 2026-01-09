"""
Utility functions for Atayeb Assets Explorer.

Provides reusable functions for file handling, XML processing, and naming conventions.
"""

# ============================================================
# IMPORTS
# ============================================================

import xml.etree.ElementTree as ET
from fnmatch import fnmatch
from pathlib import Path
import copy


def ensure_nested_path(d: dict, path: str, push: dict = {}) -> dict:
    """Create nested dict structure from dotted path."""
    keys = path.split(".")
    current = d
    for key in keys:
        if key not in current:
            current[key] = {}
        current = current[key]
    current.update(copy.deepcopy(push))
    return current


def nest_dict(dict: dict, path: str) -> dict:
    nested_config_dict = {}
    ensure_nested_path(nested_config_dict, path, push=dict)
    return nested_config_dict


def dict_path(d: dict, path: str, default: any = None) -> any | None:
    """Get value from nested dict using dotted path."""
    for key in path.split("."):
        if not isinstance(d, dict) or key not in d:
            return default
        d = d[key]
    return d


def deep_merge_dicts(*dicts: dict) -> dict:
    dicts_list = list(copy.deepcopy(d) for d in dicts)
    while len(dicts_list) > 1:
        _deep_merge_dicts(dicts_list[-2], dicts_list[-1])
        dicts_list.pop()
    return dicts_list[0]


def _deep_merge_dicts(d1: dict, d2: dict) -> dict:
    """Recursively merge d2 into d1 with deep copy"""

    for key, value in d2.items():
        if not key in d1.keys():
            d1[key] = copy.deepcopy(value)
        elif isinstance(value, dict) and isinstance(d1.get(key), dict):
            _deep_merge_dicts(d1[key], value)
        else:
            d1[key] = copy.deepcopy(value)
    return d1


# ============================================================
# FILE OPERATIONS
# ============================================================


def sanitize_filename(name: str, strict: bool = False) -> str:
    """
    Remove/replace forbidden filename characters.

    Args:
        name: Original filename or string.
        strict: If True, remove all special chars; if False, only forbidden ones.

    Returns:
        Sanitized filename.
    """
    if strict:
        # Remove all special characters except underscores and dots
        return "".join(c if c.isalnum() or c in "._" else "_" for c in name)
    else:
        # Remove only forbidden characters on Windows
        forbidden = '<>:"/\\|?*'
        sanitized = name
        for char in forbidden:
            sanitized = sanitized.replace(char, "_")
        return sanitized


def generate_constant_name(template_name: str) -> str:
    """
    Generate Python constant name from template name.

    Converts CamelCase filename to UPPER_SNAKE_CASE.

    Args:
        template_name: Template filename (e.g., "AssetPoolNamed.xml").

    Returns:
        Constant name (e.g., "ASSET_POOL_NAMED_MAP").

    Example:
        >>> generate_constant_name("AssetPoolNamed.xml")
        "ASSET_POOL_NAMED"
    """
    # Remove .xml extension and convert to UPPER_SNAKE_CASE
    stem = template_name.replace(".xml", "")

    # Insert underscores before uppercase letters (except the first)
    parts = []
    for i, char in enumerate(stem):
        if i > 0 and char.isupper():
            parts.append("_")
        parts.append(char.upper())

    return "".join(parts)


# ============================================================
# XML PROCESSING
# ============================================================


def indent_xml(elem: ET.Element, level: int = 0) -> None:
    """
    Pretty-print XML element tree with indentation.

    Modifies the element tree in-place to add proper indentation and newlines.

    Args:
        elem: Root element to format.
        level: Current indentation level (used for recursion).
    """
    indent_str = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent_str + "  "
        for child in elem:
            indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent_str
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = indent_str


def match_pattern(name: str, patterns: list[str]) -> bool:
    """
    Check if name matches any pattern in list (wildcard support).

    Supports fnmatch patterns (*, ?, [seq], [!seq]).

    Args:
        name: String to match.
        patterns: List of patterns (with wildcards).

    Returns:
        True if match found, False otherwise.

    Example:
        >>> match_pattern("AssetPool", ["Asset*", "Template*"])
        True
    """
    return any(fnmatch(name, pattern) for pattern in patterns)


# ============================================================
# VALIDATION
# ============================================================


def load_xml_file(file_path: Path) -> ET.Element | None:
    """
    Load and parse XML file.

    Args:
        file_path: Path to XML file.

    Returns:
        Root element of parsed XML, or None if error.
    """
    return ET.parse(file_path)


# ============================================================
# MODULE UTILITIES
# ============================================================


def reload_module_preserving_globals(mod):
    import importlib
    from src import Logger

    if not "preserve_globals" in dir(mod):
        Logger.get("cli").debug(
            f"Module {mod.__name__} does not specify preserve_globals attribute.",
            verbose_only=True,
        )
        return importlib.reload(mod)

    # Save globals.
    saved_state = {
        attr_name: getattr(mod, attr_name)
        for attr_name in getattr(mod, "preserve_globals", [])
    }

    # Reload module.
    mod = importlib.reload(mod)

    # Restore globals.
    for attr_name, value in saved_state.items():
        setattr(mod, attr_name, value)
        Logger.get("cli").debug(
            f"Restored global {attr_name} in module {mod.__name__}.",
            verbose_only=True,
        )

    return mod
