"""
Cache system for asset explorer.

Stores information about not-found GUIDs to avoid redundant CLI calls
and disable links to invalid assets in the UI.
"""

import json
from pathlib import Path
from .log import log

# Cache file location
CACHE_FILE = Path.cwd() / ".cache" / "cache.json"

# Global cache (loaded on first access)
_CACHE = None
_CACHE_MTIME = None  # Track file modification time


def _ensure_cache_dir() -> None:
    """Ensure cache directory exists."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _write_cache_file() -> None:
    """Save cache to disk."""
    _ensure_cache_dir()

    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_CACHE, f, indent=2)
    except IOError as e:
        log(f"{{err/Failed to save cache: {e}}}")


def _read_cache_file() -> dict:
    """Load cache from disk, returning empty dict if file doesn't exist."""
    _ensure_cache_dir()

    if not CACHE_FILE.exists():
        return {}

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        log(f"{{err/Failed to load cache: {e}, starting fresh}}")
        return {}


def _get_cache() -> dict:
    """Get cached data, loading from disk if file has changed or not yet loaded."""
    global _CACHE, _CACHE_MTIME

    # Check if file exists and has been modified since last load
    if CACHE_FILE.exists():
        current_mtime = CACHE_FILE.stat().st_mtime
        if _CACHE is None or _CACHE_MTIME != current_mtime:
            # File is new or has changed, reload it
            _CACHE = _read_cache_file()
            _CACHE_MTIME = current_mtime

    return _CACHE


def get_cached_asset(guid: str) -> dict | None:
    """
    Get cached asset info for a GUID (NOT related_guids).

    Returns found assets or not_found markers, but NOT related_guids.
    Related GUIDs are recalculated on demand (~4ms, negligible performance cost).

    Args:
        guid: The GUID to look up

    Returns:
        Asset dict if GUID is cached (asset or not_found), None otherwise.
        Asset dict has 'guid', 'name', 'template', 'file' keys (no 'related').
        Not_found entry has 'not_found': True.
    """
    cache = _get_cache()
    guid_entry = cache.get(guid, {})

    # Return the entry if it exists (could be asset or not_found marker)
    if guid_entry:
        # Remove 'related' field if present (we don't cache related_guids)
        guid_entry_copy = guid_entry.copy()
        guid_entry_copy.pop("related", None)
        return guid_entry_copy
    return None


def set_cached_asset(
    guid: str, asset_data: dict, related_guids: list[dict] = None
) -> None:
    """
    Cache asset data for a GUID (related_guids are NOT cached).
    Args:
        guid: The GUID as key
        asset_data: Asset information dict with 'name', 'template', 'file', etc.
        related_guids: Ignored (for backwards compatibility with old code)
    """
    cache = _get_cache()

    # Store asset data only (strip related_guids if present)
    cache_entry = asset_data.copy()
    cache_entry.pop("related", None)  # Remove related if present
    cache[guid] = cache_entry

    # Save to disk
    _write_cache_file()


def clear_cache() -> None:
    """Clear all cached data."""
    global _CACHE
    _CACHE = {}
    _write_cache_file()
