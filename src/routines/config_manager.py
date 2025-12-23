from src.utils import CustomArgumentParser
from src.log import log
from ..config import reload_config, print_config, unload_config, print_config_state

# ============================================================
# CLI
# ============================================================


def build_parser(parser: CustomArgumentParser):
    """
    Build argument parser for config manager.

    Args:
        parser: CustomArgumentParser instance to configure.
    """
    parser.add_argument(
        "-r",
        "--reload",
        action="store_true",
        default=None,
    )
    parser.add_argument(
        "-s",
        "--state",
        action="store_true",
    )
    parser.add_argument(
        "-p",
        "--print",
        action="store_true",
    )
    parser.add_argument(
        "-u",
        "--unload",
        action="store_true",
    )


def run(parsed: CustomArgumentParser) -> int:
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
    if parsed.reload:
        reload_config()
    if parsed.print:
        print_config()
    if parsed.unload:
        unload_config()

    print_config_state()

    return 0
