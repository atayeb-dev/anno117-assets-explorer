from ..cache import clear_cache, clear_not_found_cache, _get_cache, CACHE_FILE
from ..cli import CliArgumentParser
from ..log import log

# ============================================================
# CLI
# ============================================================


def build_parser(parser: CliArgumentParser) -> None:
    """
    Build argument parser for cache manager.

    Args:
        parser: CustomArgumentParser instance to configure.
    """
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


def run(parsed: CliArgumentParser) -> int:
    """
    Main entry point for cache manager.

    Args:
        parsed: Parsed command-line arguments.

    Returns:
        Exit code (0 on success, 1 on error).
    """
    if parsed.clear:
        clear_cache()
        log("{succ/Cache cleared}")
        return 0
    elif parsed.clear_not_found:
        clear_not_found_cache()
        cache = _get_cache()
        log(f"{{succ/Cleared not-found GUIDs. Cache now has {len(cache)} entries}}")
        return 0
    elif parsed.stats:
        cache = _get_cache()
        not_found_count = sum(
            1 for entry in cache.values() if entry.get("not_found", False)
        )
        log(f"\tCache Statistics:")
        log(f"\tTotal entries: {len(cache)}")
        log(f"\tCache file: {CACHE_FILE}")
        log(f"\tExists: {CACHE_FILE.exists()}")
        log(f"\tNot-found GUIDs: {not_found_count}\n")
        return 0
    else:
        raise ValueError(
            "No command provided. Use {hu/--stats}, {hu/--clear}, or {hu/--clear-not-found}"
        )
