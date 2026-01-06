import json
import sys
import src.engine.logger as Logger
import src.engine.config as Config
import src.engine.cli as Cli

unit_test_logger = Logger.get(
    "unit-test-logger",
    stream=sys.stdout,
    create_config_dict=Config.get("logger").to_dict(),
)


def build_parser(parser: Cli.CliArgumentParser) -> None:
    """Build argument parser for unit_test."""
    parser.add_args(
        Cli.CliArgument(
            "--modes",
            short="-m",
            expect="many",
            required=True,
            accepted_values=["prompt", "config", "data-print", "kraken"],
        ),
        Cli.CliArgument("--test-data", type=str, expect="many"),
        Cli.CliArgument(
            "--data-print-modes", expect="many", accepted_values=["inline", "compact"]
        ),
    )


def run(parser: Cli.CliArgumentParser):
    global unit_test_logger
    modes = parser._get_arg("--modes")
    if "prompt" in modes:
        unit_test_logger.error("This is a test error message.")
        unit_test_logger.success("This is a test success message.")
        unit_test_logger.prompt("This is a test prompt message.")
        unit_test_logger.debug("This is a test debug message.")
    if "config" in modes:
        test_logger_config = Config.get("unit-test-logger")
        test_logger_config._custom_config_path = "tests/unit-test-logger.json"
        unit_test_logger.prompt("Starting config tests...")

        def print_config(message: str):
            nonlocal test_logger_config
            global unit_test_logger
            unit_test_logger.success(
                message,
                test_logger_config,
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
        test_logger_config.dump()
        unit_test_logger.prompt("Reloading config trusting dict: ", config_dict)
        test_logger_config.reload(
            config_dict=config_dict,
            trust="dict",
        )
        print_config("Reloaded config trusting dict: ")
        test_logger_config.reload()
        print_config("Reloaded config trusting file: ")
        test_logger_config.delete_file()
        unit_test_logger.success("Done config tests.")
    if "data-print" in modes:

        def print_test_data(data: any):
            modes = parser._get_arg("--data-print-modes")
            if modes:
                unit_test_logger.prompt(
                    "Printing with: ",
                    modes,
                    data,
                    compact=lambda k: "compact" in modes,
                    force_inline=lambda k: "inline" in modes,
                )
            else:
                unit_test_logger.prompt("Printing: ", data)

        if parser._get_arg("--test-data"):
            for read_path in parser._get_arg("--test-data"):
                try:
                    from pathlib import Path

                    with open(Path.cwd() / read_path, "r", encoding="utf-8") as f:
                        test_data = json.load(f)
                    unit_test_logger.success(f"Loaded test data from {read_path}")
                    print_test_data(test_data)
                except Exception as e:
                    unit_test_logger.critical(
                        f"Failed to load test data from: {read_path} ({type(e).__name__})"
                    )
        else:
            unit_test_logger.prompt(
                "No test data provided. Printing logger configuration:"
            )
            print_test_data(Config.get("unit-test-logger"))
        unit_test_logger.success("Done data print tests.")
    if "kraken" in modes:
        Logger.get().print("/;__kraken/;/ ")
