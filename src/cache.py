"""
Cache system for asset explorer.

Stores information about not-found GUIDs to avoid redundant CLI calls
and disable links to invalid assets in the UI.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Cache file location
CACHE_FILE = Path(__file__).parent.parent / ".cache" / "assets.json"


def _ensure_cache_dir() -> None:
    """Ensure cache directory exists."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_cache() -> dict:
    """Load cache from disk, returning empty dict if file doesn't exist."""
    _ensure_cache_dir()

    if not CACHE_FILE.exists():
        return {}

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to load cache: {e}, starting fresh")
        return {}


def _save_cache(cache: dict) -> None:
    """Save cache to disk."""
    _ensure_cache_dir()

    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to save cache: {e}")


# Global cache (loaded on first access)
_CACHE = None
_CACHE_MTIME = None  # Track file modification time


def reload_cache() -> dict:
    """Reload cache from disk and return it."""
    global _CACHE, _CACHE_MTIME
    _CACHE = _load_cache()
    # Update mtime after loading
    if CACHE_FILE.exists():
        _CACHE_MTIME = CACHE_FILE.stat().st_mtime
    return _CACHE


def _get_cache() -> dict:
    """Get cached data, loading from disk if file has changed or not yet loaded."""
    global _CACHE, _CACHE_MTIME

    # Check if file exists and has been modified since last load
    if CACHE_FILE.exists():
        current_mtime = CACHE_FILE.stat().st_mtime
        if _CACHE is None or _CACHE_MTIME != current_mtime:
            # File is new or has changed, reload it
            logger.debug("Cache file modified, reloading from disk")
            _CACHE = _load_cache()
            _CACHE_MTIME = current_mtime
    else:
        # File doesn't exist yet, load empty cache
        if _CACHE is None:
            _CACHE = _load_cache()
            _CACHE_MTIME = None

    return _CACHE


def is_guid_not_found(guid: str) -> bool:
    """
    Check if a GUID was previously searched and not found.

    Args:
        guid: The GUID to check

    Returns:
        True if GUID is marked as not found, False otherwise
    """
    cached = get_cached_asset(guid)
    return cached is not None and cached.get("not_found", False)


def set_guid_not_found(guid: str) -> None:
    """
    Mark a GUID as not found (cache the search failure).

    Args:
        guid: The GUID to mark as not found
    """
    cache = _get_cache()

    # Store as not found
    cache[guid] = {"not_found": True}

    # Save to disk
    _save_cache(cache)
    logger.debug(f"Cached GUID {guid} as not found")


def get_cached_asset(guid: str) -> dict | None:
    """
    Get cached data for a GUID from the asset cache.

    Returns BOTH found assets AND not_found markers.
    Caller should check for "not_found" key to distinguish.

    Args:
        guid: The GUID to look up

    Returns:
        Cache entry dict if GUID is cached (asset or not_found), None otherwise.
        Asset entry has 'guid', 'name', 'template', 'file' keys.
        Not_found entry has 'not_found': True.
    """
    cache = _get_cache()
    guid_entry = cache.get(guid, {})

    # Return the entry if it exists (could be asset or not_found marker)
    if guid_entry:
        return guid_entry
    return None


def set_cached_asset(guid: str, asset_data: dict) -> None:
    """
    Cache asset data for a GUID.

    Args:
        guid: The GUID as key
        asset_data: Asset information dict with 'name', 'template', 'file', etc.
    """
    cache = _get_cache()

    # Store asset data
    cache[guid] = asset_data

    # Save to disk
    _save_cache(cache)
    logger.debug(f"Cached asset data for GUID {guid}")


def get_cache_stats() -> dict:
    """
    Get cache statistics.

    Returns:
        Dict with total_entries and not_found_count
    """
    cache = _get_cache()

    not_found_count = sum(
        1 for entry in cache.values() if entry.get("not_found", False)
    )

    return {
        "total_entries": len(cache),
        "not_found_count": not_found_count,
    }


def clear_cache() -> None:
    """Clear all cached data."""
    global _CACHE
    _CACHE = {}
    _save_cache({})
    logger.info("Cache cleared")


def clear_not_found_cache() -> None:
    """Clear only the not-found entries from cache."""
    cache = _get_cache()

    # Remove all entries marked as not_found
    original_count = sum(1 for entry in cache.values() if entry.get("not_found", False))

    cache = {
        guid: entry
        for guid, entry in cache.items()
        if not entry.get("not_found", False)
    }

    _save_cache(cache)
    global _CACHE
    _CACHE = cache

    logger.info(f"Cleared {original_count} not-found entries from cache")
