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

# Global cache (loaded on first access)
_CACHE = None
_CACHE_MTIME = None  # Track file modification time


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

    Related GUIDs are recalculated on demand (~4ms, negligible performance cost).
    This keeps the cache file small and lightweight.

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
    _save_cache(cache)
    logger.debug(f"Cached asset data for GUID {guid}")


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
