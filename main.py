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
from io import StringIO
from pathlib import Path
import sys
import src.engine.config as Config
import src.engine.logger as Logger
import src.engine.cli as Cli


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
 /;cb/Modular routines/; for /;cr/anno assets/; : unpacking/searching/dumping/mapping.
   /;cy;it/Features/;:
      - Interactive CLI
      ...
/;cg;bo/Launch/; with /;cy/'--cli'/; for command-line interface.
\n\x1b[01m©\x1b[0m atayeb 2025
/;di/If my work made your day better, consider backing its creator./;
==
"""
        super().__init__(self.message)


# ============================================================
# MODULE DISPATCHER
# ============================================================


class ModuleDispatcher:
    def _interactive_prompt(self) -> int:

        logger = Logger.get()
        logger.print("==")
        logger.print("Assets Explorer - Interactive CLI")
        logger.print(
            "Welcome! Type {hu/help} for commands ; {hu/exit} or {hu/bye} to quit."
        )
        # print_config_state()
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
                    logger.error(f"Command failed with exit code {result}/;\n")
                else:
                    logger.success(f"Command executed successfully/;\n")

            except ModuleNotFoundError:
                logger.error(f"Module not found: {module_name}/;\n")
            except KeyboardInterrupt:
                logger.error(f"\nInterrupted!")
            except Exception as e:
                handle_error(e)

    def _invoke_module(
        self,
        module_name: str | None = None,
        full_module_name: str | None = None,
        module_args: list[str] = [],
    ) -> int | None:
        logger = Logger.get()

        invoke_name = None
        short_module_name = None
        if full_module_name:
            short_module_name = full_module_name.split(".")[-1]
            invoke_name = full_module_name
        else:
            short_module_name = module_name
            invoke_name = f"{CLI_PREFIX}{module_name}"

        if not invoke_name or invoke_name.strip() == "":
            logger.error(f"{{err/Module not found: {invoke_name}}}")
        mod = importlib.import_module(invoke_name)
        mod = importlib.reload(mod)  # Hot reload for development

        entry_point = getattr(mod, "run")
        if entry_point is None or not callable(entry_point):
            logger.error(f"{{err/No entry point found in {module_name}}}")
            return None

        logger.print("==============================")
        logger.print(f"Invoking module: {short_module_name}: ", module_args)
        from src.engine.cli import CliArgumentParser

        parser = CliArgumentParser(mod)
        parser.parse_args(module_args)
        help_run = parser.get_arg("--help")
        silent_run = parser.get_arg("--silent")

        if parser._get_arg("--print-args"):
            parser.print_args()

        if help_run:
            if not hasattr(mod, "help"):
                logger.critical("Nothing can help you now...")
                return 0
            else:
                logger.print("{arr/}Asked for help")
                help_func = getattr(mod, "help")
                help_text = ""
                try:
                    help_text = help_func(module_args)
                except Exception:
                    help_text = help_func()
                logger.print(help_text)
                return 0
        else:
            try:
                out = entry_point(parser)
                if isinstance(out, int):
                    return out
                elif isinstance(out, tuple):
                    # if live_run and not silent_run:
                    #     logger.print(f"{{arr/}}{out[0]}")
                    return out[1]
            except BaseException as e:
                logger.critical(
                    f"The following error occured while invoking {full_module_name}:"
                )
                raise e


class MainArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that raises exceptions instead of exiting."""

    def error(self, message):
        """Raise exception instead of exiting."""
        raise Exception(message)


def handle_error(e: BaseException) -> None:
    if isinstance(e, LaunchError):
        logger = Logger.get(
            "special",
            stream=sys.stdout,
            create_config_dict={
                "animate": True,
                "flush_rate": [1, 3],
            },
        )
        logger.write(f"{e}")
    elif isinstance(e, Logger.KrakenError):
        handle_kraken_error(e)
    elif isinstance(e, KeyboardInterrupt):
        Logger.get("default").critical(f"Interrupted!")
    else:
        handle_uncaught_exception(e)


def handle_kraken_error(e: Logger.KrakenError) -> None:
    stream = StringIO()
    kraken = "/;" + "/;".join(f"{e}".split("/;")[1:])
    Logger.get("default").write(kraken, ansi=False, stream=stream)
    Logger.get("default").critical(f"{e}".split("/;")[0][:-1] + ": ", end="/;cm;bo/")
    Logger.get("default").write(stream.getvalue(), ansi=False)
    Logger.get("default").print("/;")
    handle_uncaught_exception(e)


def handle_uncaught_exception(e: Exception):
    import traceback

    logger = Logger.get("traceback")
    if not isinstance(e, Logger.KrakenError) and e.args:
        logger.critical(f"{e} ({type(e).__name__})")
    for frame in traceback.extract_tb(e.__traceback__)[::-1]:
        logger.debug(
            {frame.name: f"{frame.filename}:{frame.lineno}"},
            force_inline=lambda k: True,
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

    # Init engine
    Logger.init()
    Config.init()
    Cli.init()

    # Setup traceback logger
    Logger.get(
        name="traceback",
        stream=sys.stderr,
        create_config_dict={"styles": {"objk": "cr", "str": "cm"}},
    )

    # Merge all logger configs and dump final config to initialize global config file
    if not (Path.cwd() / Config._default_config_file).exists():
        for logger in Logger._loggers.values():
            logger.get_config().merge()
        Config.get().dump()

    parser = MainArgumentParser(argparse.ArgumentParser, add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("--cli", nargs=argparse.REMAINDER)

    try:
        if "--unit-test" in sys.argv:
            Logger.get().prompt("Starting unit test module")
            sys.argv.remove("--unit-test")
            ModuleDispatcher()._invoke_module(
                full_module_name="src.engine.unit_test", module_args=sys.argv[1:]
            )
        elif "--help" in sys.argv or "-h" in sys.argv:
            raise LaunchError()
        elif "--cli" in sys.argv:
            parsed = parser.parse_args(args)
            dispatcher = ModuleDispatcher()
            if len(parsed.cli) == 0:
                return dispatcher._interactive_prompt()

            module_name = parsed.cli[0]
            module_args = parsed.cli[1:]

            result = dispatcher._invoke_module(module_name, module_args)
            return result or 0
        else:
            raise LaunchError()

    except BaseException as e:
        handle_error(e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
