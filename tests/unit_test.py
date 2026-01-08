import json
from pathlib import Path
import sys
from typing import cast
import src.engine.logger as Logger
import src.engine.config as Config
import src.engine.cli as Cli

_unit_test_logger: Logger.Logger = None


class UnitTest(Cli.CliModule):
    """Unit test CLI module."""

    def prepare(self) -> None:

        global _unit_test_logger
        # Create dedicated logger for unit tests
        try:
            _unit_test_logger = Logger.create(
                "unit-test",
                stream=sys.stdout,
                config_dict={"animate": True},
            )
            Logger.get().print(
                "Created unit test logger: ", _unit_test_logger.get_config()
            )
        except Exception:
            _unit_test_logger = Logger.get("unit-test")

        # Change config path for unit tests
        self._config.specify_file_path("tests/config/unit-test-module-config.json")

        # Clear previous dumps
        import shutil

        path = Path.cwd() / "tests" / "dump"
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)

        """Register unit test arguments."""
        self.add_args(
            Cli.CliArgument(
                "--modes",
                short="-m",
                expect="many",
                required=True,
                accepted_values=["prompt", "config", "data-print", "kraken"],
            ),
            Cli.CliArgument("--test-data", type=Cli.CliFile, expect="many"),
            Cli.CliArgument("--test-data-dir", type=Cli.CliDir, expect="many"),
            Cli.CliArgument(
                "--data-print-modes",
                expect="many",
                accepted_values=["inline", "compact"],
            ),
        )

    def run(self) -> int:
        """Execute unit test module."""
        modes = self.get_arg("--modes")
        Logger.get().print("Running UnitTest module with modes: ", modes)
        if "prompt" in modes:
            # Simple prompt tests
            _unit_test_logger.error("This is a test error message.")
            _unit_test_logger.success("This is a test success message.")
            _unit_test_logger.prompt("This is a test prompt message.")
            _unit_test_logger.debug("This is a test debug message.")
        if "config" in modes:

            # Manipulate logger config
            unit_test_config = _unit_test_logger.get_config()
            _unit_test_logger.prompt("Starting config tests...")

            # Print current config
            _unit_test_logger.prompt("Module config:")
            self._config.print()

            def print_config(message: str):
                nonlocal unit_test_config
                _unit_test_logger.success(message)
                unit_test_config.print(
                    output=lambda *args, **kwargs: _unit_test_logger.print(
                        *args, **kwargs, compact=lambda k: True
                    )
                )

            dumps_count = 0

            def dump_config():
                nonlocal unit_test_config
                nonlocal dumps_count
                dumps_count += 1
                # Dump reload result
                unit_test_config.specify_file_path(
                    f"tests/dump/unit-test-logger.dump.{dumps_count}.json", reload=False
                )
                unit_test_config.dump()

            # Initial print
            print_config("Initial config: ")
            dump_config()

            # Reload with dict
            config_dict = {
                "flush_rate": [2, 3],
                "styles": {
                    "objk": "cm;bo",
                    "str": "cw;it;di",
                    "sep": "cw",
                },
            }
            _unit_test_logger.prompt("Reloading config trusting dict: ", config_dict)
            unit_test_config.reload(config_dict=config_dict, trust="dict")
            print_config("Reloaded config trusting dict: ")
            dump_config()

            # Reload with unknown file
            unit_test_config.specify_file_path("tests/unknown.json")
            print_config("Reloaded config trusting unknown file: ")
            dump_config()

            # Reload with module file
            unit_test_config.reload_for_module(self)
            print_config("Reloaded config from module: ")
            dump_config()

            # Reload with module file
            unit_test_config.reload_for_module(self)

            _unit_test_logger.success("Done config tests.")

        if "data-print" in modes:

            def print_test_data(data: any):
                modes = self.get_arg("--data-print-modes")
                if modes:
                    _unit_test_logger.prompt(
                        "Printing with: ",
                        modes,
                        data,
                        compact=lambda k: "compact" in modes,
                        force_inline=lambda k: "inline" in modes,
                    )
                else:
                    _unit_test_logger.prompt("Printing: ", data)

            def read_print_test_data(read_path: any):
                try:
                    _unit_test_logger.prompt(f"Loading test data from {read_path}")
                    with open(read_path, "r", encoding="utf-8") as f:
                        test_data = json.load(f)
                    _unit_test_logger.success(f"Loaded test data from {read_path}")
                    print_test_data(test_data)
                except Exception as e:
                    _unit_test_logger.critical(
                        f"Failed to load test data from: {read_path} ({type(e).__name__})"
                    )

            if self.get_arg("--test-data"):
                for read_path in cast(list[Cli.CliFile], self.get_arg("--test-data")):
                    read_print_test_data(read_path)
            if self.get_arg("--test-data-dir"):
                for read_dir in cast(list[Cli.CliDir], self.get_arg("--test-data-dir")):
                    dir_path = read_dir
                    _unit_test_logger.prompt(f"Reading test data from {read_dir}")
                    for read_path in dir_path.glob("*.json"):
                        read_print_test_data(read_path)
            else:
                _unit_test_logger.prompt(
                    "No test data provided. Printing logger configuration:"
                )
                print_test_data(_unit_test_logger.get_config())
            _unit_test_logger.success("Done data print tests.")
        if "kraken" in modes:
            Logger.get().print("/;__kraken/;/ ")

        return 0
