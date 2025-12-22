"""
Utility functions for Atayeb Assets Explorer.

Provides reusable functions for file handling, XML processing, and naming conventions.
"""

# ============================================================
# IMPORTS
# ============================================================

import json
import logging
import xml.etree.ElementTree as ET
from fnmatch import fnmatch
from pathlib import Path
from tkinter import Tk, filedialog

logger = logging.getLogger(__name__)


# ============================================================
# LOGGING & SETUP
# ============================================================


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    Configure logging with standard format.

    Args:
        level: Logging level (default: INFO).

    Returns:
        Configured logger instance.
    """
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
    return logging.getLogger(__name__)


# ============================================================
# JSON & SERIALIZATION
# ============================================================


def make_json_serializable(obj):
    """
    Convert non-JSON-serializable objects (like Path) to JSON-compatible types.

    Recursively processes dicts and lists to convert any Path objects to strings.

    Args:
        obj: Object to convert (dict, list, Path, or any other type).

    Returns:
        JSON-serializable version of the object.
    """
    if isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, Path):
        return str(obj)
    else:
        return obj


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


def validate_file_exists(file_path: Path, description: str = "File") -> bool:
    """
    Validate that a file exists and is readable.

    Args:
        file_path: Path to file to validate.
        description: Human-readable description for error messages.

    Returns:
        True if file exists and is valid, False otherwise.
    """
    if not file_path.exists():
        logger.error(f"{description} not found: {file_path}")
        return False
    if not file_path.is_file():
        logger.error(f"Not a file: {file_path}")
        return False
    return True


def ensure_dir_exists(dir_path: Path) -> bool:
    """
    Ensure directory exists, creating it if necessary.

    Args:
        dir_path: Path to directory.

    Returns:
        True if directory exists or was created successfully.
    """
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError as e:
        logger.error(f"Failed to create directory {dir_path}: {e}")
        return False


def load_json_config(config_path: Path, defaults: dict | None = None) -> dict:
    """
    Load JSON configuration file with fallback to defaults.

    Args:
        config_path: Path to JSON config file.
        defaults: Default configuration dict if file not found.

    Returns:
        Loaded configuration or defaults if file not found.

    Raises:
        ValueError: If JSON is malformed.
    """
    import json

    if defaults is None:
        defaults = {}

    if not config_path.exists():
        logger.info(f"Config not found at {config_path}, using defaults")
        return defaults

    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        logger.info(f"Loaded config from {config_path}")
        return config
    except json.JSONDecodeError as e:
        logger.error(f"Config JSON malformed: {e}")
        raise ValueError(f"Invalid JSON in {config_path}") from e


def select_file_gui(
    title: str = "Select a file",
    filetypes: list[tuple[str, str]] | None = None,
) -> str:
    """
    Open a file selection dialog.

    Args:
        title: Dialog window title.
        filetypes: List of (label, pattern) tuples for file filtering.
                  Example: [("XML files", "*.xml"), ("All files", "*.*")]

    Returns:
        Path to selected file, or empty string if cancelled.
    """
    if filetypes is None:
        filetypes = [("All files", "*.*")]

    root = Tk()
    root.withdraw()
    filepath = filedialog.askopenfilename(title=title, filetypes=filetypes)
    return filepath


def load_xml_file(file_path: Path) -> ET.Element | None:
    """
    Load and parse XML file.

    Args:
        file_path: Path to XML file.

    Returns:
        Root element of parsed XML, or None if error.
    """
    try:
        tree = ET.parse(file_path)
        return tree.getroot()
    except ET.ParseError as e:
        logger.warning(f"Error parsing {file_path.name}: {e}")
        return None
    except OSError as e:
        logger.warning(f"Error reading {file_path.name}: {e}")
        return None
