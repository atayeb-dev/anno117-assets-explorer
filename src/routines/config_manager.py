from os import path
from src.cli import CliArgumentParser
from ..config import reload_config, print_config, unload_config, print_config_state

# ============================================================
# CLI
# ============================================================


def build_parser(parser: CliArgumentParser) -> None:
    """
    Build argument parser for config manager.

    Args:
        parser: CustomArgumentParser instance to configure.
    """
    parser.add_argument(
        long="reload",
        action="store_true",
    )
    parser.add_argument(
        long="status",
        action="store_true",
    )
    parser.add_argument(
        long="print",
        nargs="?",
        const=True,
    )
    parser.add_argument(
        long="unload",
        action="store_true",
    )


def run(parser: CliArgumentParser) -> int:
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

    parsed = parser.module_parsed

    if parsed.reload:
        reload_config()
    if parsed.print:

        prints = parser.module_arg("print")
        if isinstance(prints, list) and len(prints) > 0:
            for path in prints:
                print_config(path)
        else:
            print_config()
    if parsed.unload:
        unload_config()

    print_config_state()

    return 0
