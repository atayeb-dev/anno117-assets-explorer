import logging
from pathlib import Path
from ..cache import clear_cache, clear_not_found_cache, _get_cache, CACHE_FILE

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
            cache = _get_cache()
            print(f"✓ Cleared not-found GUIDs. Cache now has {len(cache)} entries")
            return 0
        elif parsed.stats:
            cache = _get_cache()
            not_found_count = sum(
                1 for entry in cache.values() if entry.get("not_found", False)
            )
            print(f"\n📊 Cache Statistics:")
            print(f"  Total entries: {len(cache)}")
            print(f"  Cache file: {CACHE_FILE}")
            print(f"  Exists: {CACHE_FILE.exists()}")
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
