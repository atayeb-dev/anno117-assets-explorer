from pathlib import Path
import re
from typing import cast

from src import Logger, Config, Cli, AppPath


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

        pattern = r"^level:(.*):(.*)$"

        def prompt(str: str) -> str:
            matches = re.match(pattern, str).groups()
            return {
                "level": matches[0],
                "message": matches[1],
            }

        """Register unit test arguments."""
        self.add_args(
            Cli.CliArgument(
                "--modes",
                short="-m",
                expect="many",
                required=True,
                accepted_values=["prompt", "config", "data-print", "kraken"],
            ),
            Cli.CliArgument(
                "--prompt", expect="one", type=prompt, accepted_values=pattern
            ),
            Cli.CliArgument("--test-data", type=AppPath.fpath, expect="many"),
            Cli.CliArgument("--test-data-dir", type=AppPath.dpath, expect="many"),
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
            while prompt := self.get_arg("--prompt"):
                self._parser.reset_arg("--prompt")
                try:
                    # Simple prompt tests
                    self._unit_test_logger.__getattribute__(prompt["level"])(
                        f"this is a test {prompt['level']} message: {prompt['message']}"
                    )
                except Exception as e:
                    self._unit_test_logger.error(f"Uknown level {prompt[0]}")
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
                "data_print": {
                    "styles": {
                        "objk": "cm;bo",
                        "str": "cw;it;di",
                        "sep": "cw",
                    }
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
                        data_print={
                            "compact": "compact" in modes,
                            "force_inline": "inline" in modes,
                        },
                    )
                else:
                    self._unit_test_logger.prompt("Printing: ", data)

            if self.get_arg("--test-data"):
                for read_path in cast(
                    list[AppPath.AppPath], self.get_arg("--test-data")
                ):
                    print_test_data(read_path.read_json())
            if self.get_arg("--test-data-dir"):
                for read_dir in cast(
                    list[AppPath.AppPath], self.get_arg("--test-data-dir")
                ):
                    dir_path = read_dir
                    self._unit_test_logger.prompt(f"Reading test data from {read_dir}")
                    for read_path in dir_path.glob("*.json"):
                        print_test_data(read_path.read_json())
            if not self.get_arg("--test-data") and not self.get_arg("--test-data-dir"):
                self._unit_test_logger.prompt(
                    "No test data provided. Printing logger configuration:"
                )
                print_test_data(self._unit_test_logger.get_config())
            self._unit_test_logger.success("Done data print tests.")
        if "kraken" in modes:
            Logger.get().print("/;__kraken/;/ ")

        return 0
