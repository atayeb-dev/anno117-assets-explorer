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
from typing import cast
import src.engine.config as Config
import src.engine.logger as Logger
import src.engine.cli as Cli


# ============================================================
# CONSTANTS
# ============================================================

_current_module = None  # type: str
_cached_modules: dict[str, Cli.CliModule] = {}


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
        logger.print("/;cg;bo/Assets Explorer/; - Interactive CLI")
        logger.print(
            "Welcome! Type /;cy;bo/help/; for commands ; /;cm;bo/exit/; or /;cm;bo/bye/; to quit."
        )
        # print_config_state()
        logger.print("==")

        def run():
            # Get user input
            cmd = input(">>> ").strip()

            if not cmd:
                return

            # Easter egg.

            if cmd.lower() == "kraken":
                try:
                    logger.print("/;__kraken/;/ ")
                except BaseException as e:
                    return handle_error(e)

            # Handle exit
            if cmd.lower() in ("exit", "bye", "quit"):
                logger.print("{succ/}Goodbye!")
                return 0

            # Handle help
            if cmd.lower() == "help":
                logger.write(f"{LaunchError().message}")
                return

            # Parse command
            cmd_parts = cmd.split()
            module_name = cmd_parts[0]
            module_args = cmd_parts[1:]

            # Execute module
            return self._invoke_module(module_name, module_args)

        while True:
            result = run()
            if result == -1:
                break

    def _resolve_module_name(self, module_name: str) -> str:
        """Resolve full module name from shorthand."""
        if "." in module_name:
            return module_name  # Assume full module path provided

        def check_path(source: str) -> str:
            return (
                f"src.{source}.{module_name}"
                if (Path.cwd() / "src" / source / f"{module_name}.py").is_file()
                else ""
            )

        for source in ["routines", "engine"]:
            if path := check_path(source):
                return path
        raise ModuleNotFoundError(f"Module not found: {module_name}.")

    def _invoke_module(
        self,
        module_name: str,
        module_args: list[str] = [],
    ) -> int | None:

        logger = Logger.get()
        try:
            print_separator = "=" * 30
            logger.print(print_separator)
            if not module_name or module_name.strip() == "":
                raise ModuleNotFoundError(f"Provide a module name")

            invoke_name = self._resolve_module_name(module_name)
            mod = importlib.import_module(invoke_name)
            mod = importlib.reload(mod)  # Hot reload for development

            logger.print(f"Invoking module: {module_name}: ", module_args)
            cli_module_class = getattr(
                mod, "CliModule", None
            ) or self._find_cli_module_class(mod)

            if cli_module_class:
                cli_module = cast(Cli.CliModule, cli_module_class())
                res = cli_module.execute(module_args)
            else:
                raise ModuleNotFoundError(
                    f"No CliModule subclass found for {invoke_name}"
                )
        except BaseException as e:
            res = handle_error(e)
        logger.print(print_separator)
        return res

    def _find_cli_module_class(self, module) -> type | None:
        """Find a CliModule subclass in the module."""
        from src.engine.cli import CliModule

        for name in dir(module):
            obj = getattr(module, name)
            if (
                isinstance(obj, type)
                and issubclass(obj, CliModule)
                and obj is not CliModule
            ):
                return obj
        return None


def handle_error(e: BaseException, raise_uncaught: bool = False) -> None:

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
        return 0
    elif isinstance(e, ModuleNotFoundError):
        Logger.get().critical(f"{e}")
        return 1
    elif isinstance(e, Logger.KrakenError):
        handle_kraken_error(e)
        return 1
    elif isinstance(e, KeyboardInterrupt):
        Logger.get().critical(f"Interrupted!")
        return 130
    else:
        handle_uncaught_exception(e)
        if raise_uncaught:
            raise e
        return 1


def handle_kraken_error(e: Logger.KrakenError) -> None:
    stream = StringIO()
    kraken = "/;" + "/;".join(f"{e}".split("/;")[1:])
    Logger.get().write(kraken, ansi=False, stream=stream)
    Logger.get().critical(f"{e}".split("/;")[0][:-1] + ": ", end="/;cm;bo/")
    Logger.get().write(stream.getvalue(), ansi=False)
    Logger.get().print("/;")
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


def main() -> int:
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

    try:
        cli = False
        args = sys.argv[1:]
        dispatcher = ModuleDispatcher()
        if "--cli" in args:
            if not args[0] == "--cli":
                raise RuntimeError("--cli must be the first argument")
            cli = True
            args.remove("--cli")

        if len(args) == 0:
            if cli:
                return dispatcher._interactive_prompt()
            else:
                raise LaunchError()

        if args[0] in ("--help", "-h"):
            raise LaunchError()

        module_name = args[0].replace("-", "_")
        module_args = args[1:]
        res = dispatcher._invoke_module(module_name, module_args)
        if cli:
            return dispatcher._interactive_prompt()
        return res if isinstance(res, int) else 0

    except BaseException as e:
        handle_error(e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
