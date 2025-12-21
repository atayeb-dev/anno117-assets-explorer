"""
Cache Manager: CLI interface for cache management.

Provides a command-line interface to clear, view statistics,
and manage the asset cache.
"""

# ============================================================
# IMPORTS
# ============================================================

import logging
from ..cache import clear_cache, clear_not_found_cache, get_cache_stats

# ============================================================
# CONFIGURATION
# ============================================================

logger = logging.getLogger(__name__)

# ============================================================
# CLI
# ============================================================


def main(args: list[str] | None = None) -> int:
    """
    Main entry point for cache manager.

    Args:
        args: Command-line arguments:
              --clear: Clear entire cache
              --clear-not-found: Clear only not-found GUIDs
              --stats: Show cache statistics

    Returns:
        Exit code (0 on success, 1 on error).
    """
    import argparse

    parser = argparse.ArgumentParser(description="Cache management utility")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear entire cache",
    )
    parser.add_argument(
        "--clear-not-found",
        action="store_true",
        help="Clear only not-found GUIDs",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show cache statistics",
    )

    try:
        parsed = parser.parse_args(args or [])

        if parsed.clear:
            clear_cache()
            print("✓ Cache cleared")
            return 0
        elif parsed.clear_not_found:
            clear_not_found_cache()
            stats = get_cache_stats()
            print(
                f"✓ Cleared not-found GUIDs. Cache now has {stats['total_entries']} entries"
            )
            return 0
        elif parsed.stats:
            stats = get_cache_stats()
            print(f"\n📊 Cache Statistics:")
            print(f"  Total entries: {stats['count']}")
            print(f"  Cache file: {stats['cache_file']}")
            print(f"  Exists: {stats['cache_exists']}")

            # Count not-found
            from ..cache import _ASSET_CACHE, _load_cache_from_disk

            _load_cache_from_disk()
            not_found_count = sum(
                1
                for guid, data in _ASSET_CACHE.items()
                if isinstance(data, dict) and data.get("not_found") is True
            )
            print(f"  Not-found GUIDs: {not_found_count}\n")
            return 0
        else:
            parser.print_help()
            return 1

    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
