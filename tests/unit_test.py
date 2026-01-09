import json
from pathlib import Path
import sys
from typing import cast
import src.engine.logger as Logger
import src.engine.config as Config
import src.engine.cli as Cli


class UnitTest(Cli.CliModule):
    """Unit test CLI module."""

    def specify_config_file_path(self) -> None:
        self._config.specify_file_path("tests/config/unit-test-module-config.json")

    def prepare(self) -> None:

        # Create dedicated logger for unit tests
        try:
            self._unit_test_logger = Logger.create("unit-test")
            self._unit_test_logger.success("Created unit test logger: ")
            self._unit_test_logger.get_config().print(
                output=self._unit_test_logger.prompt
            )
        except Exception:
            self._unit_test_logger = Logger.get("unit-test")
            self._unit_test_logger.success("Got unit test logger: ")
            self._unit_test_logger.get_config().print(
                output=self._unit_test_logger.prompt
            )

        # Change config path for unit tests
        self.specify_config_file_path()

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
            self._unit_test_logger.error("This is a test error message.")
            self._unit_test_logger.success("This is a test success message.")
            self._unit_test_logger.prompt("This is a test prompt message.")
            self._unit_test_logger.debug("This is a test debug message.")
        if "config" in modes:

            # Manipulate  config
            unit_test_config = self._config
            unit_test_logger_config = self._unit_test_logger.get_config()
            self._unit_test_logger.prompt("Starting config tests...")

            def print_config(message: str, config: Config.Config):
                spec_name = "module" if config == unit_test_config else "logger"
                self._unit_test_logger.success(f"[{spec_name}] {message}")
                config.print(
                    output=lambda *args, **kwargs: self._unit_test_logger.print(
                        *args, **kwargs, compact=lambda k: True
                    )
                )

            dumps_count = 0

            def dump_config(config: Config.Config):
                nonlocal unit_test_config
                nonlocal dumps_count
                spec_name = "module" if config == unit_test_config else "logger"
                dumps_count += 1
                config.specify_file_path(
                    f"tests/dump/unit-test.dump.{dumps_count}.{spec_name}.json",
                    reload=False,
                )
                config.dump()

            # Reload with dict
            config_dict = {
                "animate": True,
                "flush_rate": [2, 3],
                "styles": {
                    "objk": "cm;bo",
                    "str": "cw;it;di",
                    "sep": "cw",
                },
            }
            self._unit_test_logger.prompt("Test config dict: ", config_dict)
            unit_test_logger_config.reload(config_dict=config_dict, trust="dict")
            print_config("Reloaded trusting dict: ", unit_test_logger_config)
            dump_config(unit_test_logger_config)
            dump_config(unit_test_config)

            # Reload with unknown file
            unit_test_logger_config.specify_file_path("tests/unknown.json")
            print_config("Reloaded trusting unknown file: ", unit_test_logger_config)
            dump_config(unit_test_logger_config)
            unit_test_logger_config.reload_for_module(self)
            print_config(
                "Reloaded from module using last dump:", unit_test_logger_config
            )
            dump_config(unit_test_logger_config)
            dump_config(unit_test_config)

            # Reload configs
            self.specify_config_file_path()
            unit_test_logger_config.reload_for_module(self)
            print_config("Reloaded from module defaults.", unit_test_logger_config)
            dump_config(unit_test_config)
            dump_config(unit_test_logger_config)

            self._unit_test_logger.success("Done config tests.")
        if "data-print" in modes:

            def print_test_data(data: any):
                modes = self.get_arg("--data-print-modes")
                if modes:
                    self._unit_test_logger.prompt(
                        "Printing with: ",
                        modes,
                        data,
                        compact=lambda k: "compact" in modes,
                        force_inline=lambda k: "inline" in modes,
                    )
                else:
                    self._unit_test_logger.prompt("Printing: ", data)

            def read_print_test_data(read_path: any):
                try:
                    self._unit_test_logger.prompt(f"Loading test data from {read_path}")
                    with open(read_path, "r", encoding="utf-8") as f:
                        test_data = json.load(f)
                    self._unit_test_logger.success(f"Loaded test data from {read_path}")
                    print_test_data(test_data)
                except Exception as e:
                    self._unit_test_logger.critical(
                        f"Failed to load test data from: {read_path} ({type(e).__name__})"
                    )

            if self.get_arg("--test-data"):
                for read_path in cast(list[Cli.CliFile], self.get_arg("--test-data")):
                    read_print_test_data(read_path)
            if self.get_arg("--test-data-dir"):
                for read_dir in cast(list[Cli.CliDir], self.get_arg("--test-data-dir")):
                    dir_path = read_dir
                    self._unit_test_logger.prompt(f"Reading test data from {read_dir}")
                    for read_path in dir_path.glob("*.json"):
                        read_print_test_data(read_path)
            else:
                self._unit_test_logger.prompt(
                    "No test data provided. Printing logger configuration:"
                )
                print_test_data(self._unit_test_logger.get_config())
            self._unit_test_logger.success("Done data print tests.")
        if "kraken" in modes:
            Logger.get().print("/;__kraken/;/ ")

        return 0
