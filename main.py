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
from email.mime import message
import importlib
import sys
from pathlib import Path
from src.config import (
    load_global_config,
    print_config_state,
)
from src.log import clean, log, pp_log
from src.cli import CliArgumentParser
from tkinter import Tk, filedialog

# ============================================================
# CONSTANTS
# ============================================================

CLI_PREFIX = "src.routines."
UI_MODULE = "src.ui"


class LaunchError(Exception):
    """Custom exception for launch errors."""

    def __init__(self):

        self.message = "\
\n==\n\
{fh/atayeb Anno 117 Assets Explorer}\n\
 {hf/Modular routines} for {r/anno assets}: unpacking/searching/dumping/mapping.\n\
   - Features:\n\
    - Interactive CLI\n\
    - ...\n\
{fh/Launch} with {hu/'--cli'} for command-line interface.\n\
\n\033[01m©\033[0m atayeb 2025\n\
{hvl/If my work made your day better, consider backing its creator.}\n\
==\n\
"
        super().__init__(self.message)


# ============================================================
# FILE SELECTION
# ============================================================


# ============================================================
# MODULE DISPATCHER
# ============================================================


def _interactive_prompt() -> int:
    """
    Interactive CLI prompt loop.

    Returns:
        Exit code (0 on normal exit).
    """
    log("\n==")
    log("Assets Explorer - Interactive CLI")
    log("Welcome! Type {hu/help} for commands ; {hu/exit} or {hu/bye} to quit.")
    print_config_state()
    log("==")

    while True:
        try:
            # Get user input
            cmd = input(">>> ").strip()

            if not cmd:
                continue

            # Handle exit
            if cmd.lower() in ("exit", "bye", "quit"):
                log("{succ/}Goodbye!")
                return 0

            # Handle help
            if cmd.lower() == "help":
                log("\nAvailable modules:")
                log("  asset_finder        Search for assets by GUID")
                log("  cache_manager       Manage cache (stats, clear)")
                log("  extract_rda         Extract RDA archives")
                log("  unpack_assets       Unpack XML assets")
                log("  assets_mapper       Generate name-to-GUID mappings")
                log("\nUsage: MODULE [ARGS...]")
                log("Example: asset_finder --guid 12345678 --json\n")
                continue

            # Parse command
            cmd_parts = cmd.split()
            module_name = cmd_parts[0]
            module_args = cmd_parts[1:]

            # Execute module
            result = _invoke_module(module_name, module_args)

            if result != 0:
                log(f"{{err/}}Command failed with exit code {result}\n")
            else:
                log(f"{{succ/}}Command executed successfully\n")

        except ModuleNotFoundError:
            log(f"{{err/}}Module not found: {module_name}\n")
        except KeyboardInterrupt:
            log(f"\n{{err/}}Interrupted!")
        except Exception as e:
            log(f"{{err/}}{e}\n")


def _invoke_module(module_name: str, module_args: list[str]) -> int | None:
    """
    Dynamically import and invoke a module's entry point.

    Attempts to import the specified module and calls the first available
    callable among: main, run, cli, or ui. Handles both cases where the
    callable accepts arguments and where it doesn't.

    Hot reload enabled: Module is reloaded on each invocation for development.

    Args:
        module_name: Fully qualified module name to import.
        module_args: Arguments to pass to the callable.

    Returns:
        Exit code (0-255) or None if no callable found.

    Raises:
        ModuleNotFoundError: If module cannot be imported.
        Exception: Any exception raised by the module's callable.
    """
    if not module_name or module_name.strip() == "":
        log(f"{{err/Module not found: {module_name}}}")

    # shortcuts
    module_short_name = module_name
    if module_name in ["config", "cache"]:
        module_name = f"{module_name}_manager"

    module_name = f"{CLI_PREFIX}{module_name}"
    mod = importlib.import_module(module_name)
    mod = importlib.reload(mod)  # Hot reload for development

    entry_point = getattr(mod, "run")
    if entry_point is None or not callable(entry_point):
        log(f"{{err/No entry point found in {module_name}}}")
        return None

    parser = CliArgumentParser(mod, module_args=module_args)

    help_run = parser.cli("help")
    instant_run = parser.cli("instant")
    live_run = parser.cli("live")
    silent_run = parser.cli("silent")

    log("==============================")
    log(f"Invoking module: {module_name}:")
    if parser.cli("print_args"):
        pp_log(
            {
                "cli": vars(parser.cli_parsed),
                "module": vars(parser.module_parsed),
            }
        )

    if help_run:
        if not hasattr(mod, "help"):
            log("{err/}Nothing can help you now...}", stream=True)
            return 0
        else:
            log("{arr/}Asked for help")
            help_func = getattr(mod, "help")
            help_text = ""
            try:
                help_text = help_func(module_args)
            except Exception:
                help_text = help_func()
            log(help_text, stream=not instant_run)
            return 0
    else:
        try:
            out = entry_point(parser)
            if isinstance(out, int):
                return out
            elif isinstance(out, tuple):
                if live_run and not silent_run:
                    log(f"{{arr/}}{out[0]}")
                return out[1]

        except Exception as e:
            log(f"{{err/}}Error in module {{fn/{module_short_name}}}: {e}")
            return 1


class MainArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that raises exceptions instead of exiting."""

    def error(self, message):
        """Raise exception instead of exiting."""
        raise Exception(message)


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

    parser = MainArgumentParser(argparse.ArgumentParser, add_help=False)
    parser.add_argument("--cli", nargs=argparse.REMAINDER)
    parser.add_argument("-h", "--help", action="store_true")

    # Load configuration
    # load_global_config(parsed.config)
    load_global_config()

    try:
        parsed = parser.parse_args(args)

        if parsed.help:
            raise LaunchError()

        if parsed.cli is not None:
            if len(parsed.cli) == 0:
                return _interactive_prompt()

            module_name = parsed.cli[0]
            module_args = parsed.cli[1:]

            result = _invoke_module(module_name, module_args)
            return result or 0

        else:
            raise LaunchError()

    except LaunchError as e:
        log(f"{e}", stream=True)
        return 1
    except Exception as e:
        log(f"{{err/{e}}}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
