"""
Atayeb Assets Explorer - Main entry point and dispatcher.

Routes execution to CLI modules or UI based on command-line arguments.
Supports custom configuration files with partial merging.

Architecture:
- Entry point: Parses arguments and routes to CLI or UI
- Config: Loaded via src.config.load_config() (handles merging)
- CLI: Dynamic module loading from src.routines.*
- UI: Launched via src.ui.main()
"""

# ============================================================
# IMPORTS
# ============================================================

import argparse
import importlib
import logging
import sys
from pathlib import Path

# ============================================================
# CONSTANTS
# ============================================================

logger = logging.getLogger(__name__)

CLI_PREFIX = "src.routines."
UI_MODULE = "src.ui"
CALLABLE_NAMES = ("main", "run", "cli", "ui")

# ============================================================
# MODULE DISPATCHER
# ============================================================


def _invoke_module(module_name: str, module_args: list[str]) -> int | None:
    """
    Dynamically import and invoke a module's entry point.

    Attempts to import the specified module and calls the first available
    callable among: main, run, cli, or ui. Handles both cases where the
    callable accepts arguments and where it doesn't.

    Args:
        module_name: Fully qualified module name to import.
        module_args: Arguments to pass to the callable.

    Returns:
        Exit code (0-255) or None if no callable found.

    Raises:
        ModuleNotFoundError: If module cannot be imported.
        Exception: Any exception raised by the module's callable.
    """
    try:
        mod = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        logger.error(f"Module not found: {module_name}")
        raise

    for fn_name in CALLABLE_NAMES:
        if not hasattr(mod, fn_name):
            continue

        func = getattr(mod, fn_name)
        logger.debug(f"Calling {module_name}.{fn_name}()")

        try:
            return func(module_args)
        except TypeError:
            # Callable doesn't accept arguments, try without
            logger.debug(f"Calling {module_name}.{fn_name}() without args")
            return func()

    logger.warning(f"No entry point found in {module_name}")
    return None


def _build_parser() -> argparse.ArgumentParser:
    """
    Build argument parser for the dispatcher.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="Atayeb Assets Explorer - Asset extraction and management utility",
        epilog="Examples: main.py --ui | main.py --cli asset_finder",
    )
    parser.add_argument(
        "-cfg",
        "--config",
        type=Path,
        default=None,
        help="Custom config file (supports 'partial: true' for merging)",
    )
    parser.add_argument(
        "-c",
        "--cli",
        nargs=argparse.REMAINDER,
        help="Run CLI: --cli MODULE [ARGS...]",
    )
    return parser


def main(args: list[str] | None = None) -> int:
    """
    Main dispatcher entry point.

    Parses command-line arguments and routes execution to CLI modules or UI.
    Handles custom config file loading via src.config.load_config().

    Args:
        args: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 on success, non-zero on failure).
    """
    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = _build_parser()
    parsed = parser.parse_args(args)

    # Handle custom config (loads via src.config which handles merging)
    if parsed.config:
        from src.config import load_config, set_global_config

        try:
            # Load custom config (handles partial merging automatically)
            custom_config = load_config(parsed.config)
            # Set as global config for all modules to use
            set_global_config(custom_config, config_path=parsed.config)
            logger.info(f"Custom config loaded and set globally: {parsed.config}")
        except Exception as e:
            logger.error(f"Failed to load custom config: {e}")
            return 1

    try:
        if parsed.cli:
            if len(parsed.cli) == 0:
                parser.error("--cli requires a module name")

            module_name = parsed.cli[0]
            module_args = parsed.cli[1:]
            full_module_name = f"{CLI_PREFIX}{module_name}"

            logger.info(f"Launching CLI: {module_name}")
            result = _invoke_module(full_module_name, module_args)
            return result or 0

        else:
            parser.error("Specify a mode: --cli MODULE or --ui")
            return 1

    except ModuleNotFoundError as e:
        logger.error(f"Module not found: {e}")
        return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
