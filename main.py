"""
Atayeb Assets Explorer - Main entry point.

Provides a dispatcher to launch different modules (CLI tools or UI) with their
respective arguments. Supports both command-line tools and graphical interfaces.
"""

import argparse
import importlib
import logging
import sys
from typing import Any

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Constants
CLI_PREFIX = "src.routines."
UI_MODULE = "src.ui"
CALLABLE_NAMES = ("main", "run", "cli", "ui")


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
    Build and return the argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="Atayeb Assets Explorer - Asset extraction and management utility"
    )
    parser.add_argument(
        "-c",
        "--cli",
        nargs=argparse.REMAINDER,
        help="Run CLI module: --cli MODULE_NAME [ARGS...]",
    )
    parser.add_argument(
        "-u",
        "--ui",
        nargs=argparse.REMAINDER,
        help="Launch UI mode: --ui [ARGS...]",
    )
    return parser


def main(args: list[str] | None = None) -> int:
    """
    Main entry point for the application dispatcher.

    Routes command execution to either CLI modules or the UI based on
    command-line arguments.

    Args:
        args: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 on success, non-zero on failure).
    """
    parser = _build_parser()
    parsed = parser.parse_args(args)

    try:
        if parsed.cli:
            if len(parsed.cli) == 0:
                parser.error("--cli requires a module name")

            module_name = parsed.cli[0]
            module_args = parsed.cli[1:]
            full_module_name = f"{CLI_PREFIX}{module_name}"

            logger.info(f"Launching CLI module: {module_name}")
            result = _invoke_module(full_module_name, module_args)
            return result or 0

        elif parsed.ui is not None:
            logger.info("Launching UI module")
            result = _invoke_module(UI_MODULE, parsed.ui)
            return result or 0

        else:
            parser.error("Specify a mode: --cli MODULE or --ui")
            return 1

    except ModuleNotFoundError as e:
        logger.error(f"Failed to load module: {e}")
        return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
