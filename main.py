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
import sys
from src.config import (
    # load_global_config,
    print_config_state,
)
import src.engine.config as Config
from src.engine.logger import get_logger as Logger, init_logging
from src.cli import CliArgumentParser


# ============================================================
# CONSTANTS
# ============================================================

CLI_PREFIX = "src.routines."
_current_module = None  # type: str


def get_current_module():
    global _current_module
    return _current_module


class LaunchError(Exception):
    """Custom exception for launch errors."""

    def __init__(self):

        self.message = """\
==
/;cg;bo/atayeb Anno 117 Assets Explorer
 /;cb/Modular routines/;r/ for /;cr/anno assets/;r/ : unpacking/searching/dumping/mapping.
   /;cy;it/Features/;:
      - Interactive CLI
      ...
/;cg;bo/Launch/; with /;cy/'--cli'/; for command-line interface.
\n\033[01m©\033[0m atayeb 2025
/;da/If my work made your day better, consider backing its creator./;
==
"""
        super().__init__(self.message)


# ============================================================
# MODULE DISPATCHER
# ============================================================


class ModuleDispatcher:
    def _interactive_prompt(self) -> int:

        logger = Logger()
        logger.print("==")
        logger.print("Assets Explorer - Interactive CLI")
        logger.print(
            "Welcome! Type {hu/help} for commands ; {hu/exit} or {hu/bye} to quit."
        )
        print_config_state()
        logger.print("==")

        while True:
            try:
                # Get user input
                cmd = input(">>> ").strip()

                if not cmd:
                    continue

                # Easter egg.

                if cmd.lower() == "kraken":
                    logger.print("/;__kraken/;/ ")

                # Handle exit
                if cmd.lower() in ("exit", "bye", "quit"):
                    logger.print("{succ/}Goodbye!")
                    return 0

                # Handle help
                if cmd.lower() == "help":
                    logger.write(f"{LaunchError().message}")
                    continue

                # Parse command
                cmd_parts = cmd.split()
                module_name = cmd_parts[0]
                module_args = cmd_parts[1:]

                # Execute module
                result = self._invoke_module(module_name, module_args)

                if result != 0:
                    logger.error(f"Command failed with exit code {result}/;r/\n")
                else:
                    logger.success(f"Command executed successfully/;r/\n")

            except ModuleNotFoundError:
                logger.error(f"Module not found: {module_name}/;r/\n")
            except KeyboardInterrupt:
                logger.error(f"\nInterrupted!")
            except Exception as e:
                logger.error(f"{e}")

    def _invoke_module(self, module_name: str, module_args: list[str]) -> int | None:
        logger = Logger()

        if not module_name or module_name.strip() == "":
            logger.error(f"{{err/Module not found: {module_name}}}")

        # shortcuts
        module_short_name = module_name
        if module_name in ["config", "cache"]:
            module_name = f"{module_name}_manager"

        module_name = f"{CLI_PREFIX}{module_name}"
        mod = importlib.import_module(module_name)
        mod = importlib.reload(mod)  # Hot reload for development

        entry_point = getattr(mod, "run")
        if entry_point is None or not callable(entry_point):
            logger.error(f"{{err/No entry point found in {module_name}}}")
            return None

        parser = CliArgumentParser(mod, module_args=module_args)

        help_run = parser.cli("help")
        instant_run = parser.cli("instant")
        live_run = parser.cli("live")
        silent_run = parser.cli("silent")

        logger.print("==============================")
        logger.print(f"Invoking module: {module_name}:", module_args)
        if parser.cli("print_args"):
            logger.print(
                {
                    "cli": vars(parser.cli_parsed),
                    "module": vars(parser.module_parsed),
                }
            )

        if help_run:
            if not hasattr(mod, "help"):
                logger.error("{err/}Nothing can help you now...}")
                return 0
            else:
                logger.print("{arr/}Asked for help")
                help_func = getattr(mod, "help")
                help_text = ""
                try:
                    help_text = help_func(module_args)
                except Exception:
                    help_text = help_func()
                logger.print(help_text, stream=not instant_run)
                return 0
        else:
            try:
                out = entry_point(parser)
                if isinstance(out, int):
                    return out
                elif isinstance(out, tuple):
                    if live_run and not silent_run:
                        logger.print(f"{{arr/}}{out[0]}")
                    return out[1]

            except Exception as e:
                logger.error(f"{{err/}}Error in module {{fn/{module_short_name}}}: {e}")
                return 1


class MainArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that raises exceptions instead of exiting."""

    def error(self, message):
        """Raise exception instead of exiting."""
        raise Exception(message)


def unit_test():
    logger_config = Config.get("logger")
    logger = Logger()
    config_dict = {
        "flush_rate": [15, 20],
        "styles": {
            "str": "cw;it;da",
        },
    }
    logger_config.reload(
        config_dict=config_dict,
        trust="dict",
    )
    logger.print("Testing logger: ", Config.get().create("test").get())
    logger_config.reload()
    logger.print(
        "Reverted logger configuration: ",
        Config.get("logger")._config_dict,
        force_inline=lambda k: "styles" in k,
    )


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
    global _current_module
    _current_module = "main"
    init_logging()
    Config.init()

    parser = MainArgumentParser(argparse.ArgumentParser, add_help=False)
    parser.add_argument("--cli", nargs=argparse.REMAINDER)
    parser.add_argument("-h", "--help", action="store_true")

    if "--unit-test" in sys.argv:
        unit_test()
        sys.argv.remove("--unit-test")

    Config.get("logger").merge()
    Logger().print(
        Config.get().get(),
        force_inline=lambda k: "logger.styles" in k,
    )
    Config.get().dump()
    Config.get("logger").dump()

    try:
        parsed = parser.parse_args(args)

        if parsed.help:
            raise LaunchError()

        if parsed.cli is not None:
            dispatcher = ModuleDispatcher()
            if len(parsed.cli) == 0:
                return dispatcher._interactive_prompt()

            module_name = parsed.cli[0]
            module_args = parsed.cli[1:]

            result = dispatcher._invoke_module(module_name, module_args)
            return result or 0

        else:
            raise LaunchError()

    except LaunchError as e:
        logger = Logger(
            "special",
            create_config_dict={
                "animate": True,
                "flush_rate": [1, 3],
            },
        )
        logger.write(f"{e}")
        return 1
    except Exception as e:
        print(f"{e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
