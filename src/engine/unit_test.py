import json
from pathlib import Path
import sys
from typing import cast
import src.engine.logger as Logger
import src.engine.config as Config
import src.engine.cli as Cli

_unit_test_logger: Logger = None


class UnitTest(Cli.CliModule):
    """Unit test CLI module."""

    def prepare(self) -> None:

        global _unit_test_logger
        try:
            _unit_test_logger = Logger.create(
                "unit-test",
                stream=sys.stdout,
                config_dict={"animate": True},
            )
        except Exception:
            _unit_test_logger = Logger.get("unit-test")

        # Change config path for unit tests
        self._config.specify_file_path("tests/config/unit_test_module_config.json")

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
            _unit_test_logger.error("This is a test error message.")
            _unit_test_logger.success("This is a test success message.")
            _unit_test_logger.prompt("This is a test prompt message.")
            _unit_test_logger.debug("This is a test debug message.")
        if "config" in modes:
            Logger.get("config").get_config().reload(
                config_dict={"verbose": True}, trust="dict"
            )
            logger_config = _unit_test_logger.get_config()
            logger_config._custom_config_path = "tests/unit-test-logger.json"
            _unit_test_logger.prompt("Starting config tests...")

            def print_config(message: str):
                nonlocal logger_config
                _unit_test_logger.success(
                    message,
                    logger_config,
                    force_inline=lambda k: "styles" in k,
                )

            print_config("Initialized config: ")
            config_dict = {
                "flush_rate": [2, 3],
                "styles": {
                    "objk": "cm;bo",
                    "str": "cw;it;di",
                    "sep": "cw",
                },
            }
            logger_config.dump()
            _unit_test_logger.prompt("Reloading config trusting dict: ", config_dict)
            logger_config.reload(
                config_dict=config_dict,
                trust="dict",
            )
            print_config("Reloaded config trusting dict: ")
            logger_config._custom_config_path = "tests/unknown.json"
            logger_config.reload()
            print_config("Reloaded config trusting file: ")
            logger_config._custom_config_path = "tests/unit-test-logger.json"
            logger_config.reload()
            print_config("Reloaded config trusting file: ")
            logger_config.delete_file()
            Logger.get("config").get_config().reload()
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


# def build_parser(parser: Cli.CliArgumentParser) -> None:
#     """Legacy function - use UnitTest class instead."""
#     unit_test = UnitTest()
#     unit_test.prepare(parser)


# def run(parser: Cli.CliArgumentParser) -> int:
#     """Legacy function - use UnitTest class instead."""
#     unit_test = UnitTest()
#     return unit_test.run(parser)
