"""
Command-line argument parsing for Atayeb Assets Explorer.

Provides a custom ArgumentParser that raises exceptions instead of exiting.
"""

# ============================================================
# IMPORTS
# ============================================================

import re
import sys

import src.engine.config as Config
import src.engine.logger as Logger
from pathlib import Path
from types import ModuleType
from tkinter import Tk, filedialog
from typing import Callable, Tuple

_cli_logger: Logger.Logger = Logger.get(
    "cli.logger",
    stream=sys.stdout,
    create_config_dict=Config.get("logger").to_dict(),
)


def _select_file_gui(title: str = "Select a file") -> str:
    """Open file picker with tkinter (improved for interactive mode)."""
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)  # Force au premier plan
    root.update()  # Force le rendu

    filepath = filedialog.askopenfilename(title=title)

    root.destroy()
    root.update()  # Nettoie après fermeture
    return filepath


def select_file(
    key: str = "Select a file",
    default: str = "",
    autoconfirm: bool = False,
    stream: bool = False,
    silent: bool = False,
):
    """Ask user to input file path."""
    from src.config import ConfigPath, get_bool_value

    if autoconfirm and default is not None:
        return ConfigPath(
            prompt(key, default=default, autoconfirm=True, stream=stream, silent=silent)
        )

    if get_bool_value("cli.gui_file_chooser"):
        Logger.get().prompt(f"Using GUI file chooser for: {key}")
        file = _select_file_gui(key)
        if file == "":
            file = default
        return ConfigPath(file)
    return ConfigPath(
        prompt(key, default=default, autoconfirm=False, stream=stream, silent=silent)
    )


def prompt(
    key: str = None,
    default: str = "",
    autoconfirm: bool = False,
    silent=False,
    ex: bool = False,
    ex_type: str = "none",
) -> str:
    """Ask user to input text."""
    logger = Logger.get()
    out_confirm = lambda instant=False: logger.prompt(
        f"Please confirm /;cy/[{key}]/; (/;_arrow/cg;bo;/ /;cw;di/{default}/;): ",
        end="",
        instant=instant,
    )
    out_provide_ex = lambda instant=False: logger.prompt(
        f"Please provide {ex_type} /;cy/[{key}]/; (/;_arrow/cg;bo;/ /;cw;di/{default}/;): ",
        end="",
        instant=instant,
    )
    out_autoconfirm = lambda instant=False: logger.prompt(
        f"Provided [{key}]: ",
        end="",
        instant=instant,
    )

    input_value = ""
    if autoconfirm:
        if not silent:
            out_autoconfirm()
        input_value = default
    else:
        if ex:
            # out_debug_ex()
            out_provide_ex()
        else:
            out_confirm()

        input_value = input().strip()
        logger.clean_lines(1)
        if ex:
            out_provide_ex(True)
        else:
            out_confirm(True)

    if input_value == "":
        input_value = default

    if input_value is None or input_value is False:
        logger.error(f"{input_value}")
    elif input_value == "":
        logger.print(f"/;cw;di/(empty)/;")
    else:
        logger.success(f"{input_value}")
    return input_value


def prompt_for_arg(
    key: str = None,
    default=None,
    is_file: bool = False,
    autoconfirm: bool = False,
    silent: bool = False,
    ex: bool = False,
    ex_type: str = "none",
) -> str:
    if is_file:
        return select_file(
            key,
            default=default,
            autoconfirm=autoconfirm,
            silent=silent,
            ex=ex,
            ex_type=ex_type,
        )
    else:
        return prompt(
            key,
            default=default,
            autoconfirm=autoconfirm,
            silent=silent,
            ex=ex,
            ex_type=ex_type,
        )


def prompt_user(message: str, default: str = None) -> str:
    """Prompt user for input with a message."""
    global _cli_logger

    _cli_logger.prompt(f"{message}", end="")
    input_value = input().strip()
    _cli_logger.clean_lines(1)
    if input_value == "":
        input_value = default

    if input_value is None or input_value is False:
        _cli_logger.prompt(f"{message}", end="")
        _cli_logger.error(f"{input_value}")
    elif input_value == "":
        _cli_logger.print(f"{message}/;cw;di/(empty)/;")
    else:
        _cli_logger.success(f"{message}{input_value}")

    return input_value


# ============================================================
# ARGUMENT PARSING
# ============================================================


class CliError(Exception):

    def __init__(self, message: str):
        super().__init__(message)

    def solve(self) -> list[str]:
        _cli_logger.critical(f"Ignoring error: {self}")
        return []


class CliArgumentError(CliError):

    def __init__(self, argument: CliArgument, type: str):
        self.argument = argument
        self.type = type
        if type == "required":
            message = f"Missing required argument: {argument.long}"
        elif type == "missing":
            message = f"Missing argument value: {argument.long}"
        elif type == "expected_one":
            message = f"Too many values for argument: {argument.long}"
        if self.argument.short:
            message += f"/{argument.short}"
        super().__init__(message)

    def solve(self) -> list[str]:
        global _cli_logger
        args = [self.argument.long]
        _cli_logger.critical(f"{self}")
        if self.type in ["required", "missing"]:
            value = prompt_user(f"Please provide a value for {self.argument.long}: ")
        if value:
            args.extend(value.split(" "))
        return args


class CliArgumentValueError(CliError):

    def __init__(self, argument: CliArgument, value: str):
        self.argument = argument
        message = f"Unexpected value '{value}' for argument: {argument.long}"
        if self.argument.short:
            message += f"/{argument.short}"
        message += f". Accepted values: {self.argument.accepted_values}"
        super().__init__(message)

    def solve(self) -> list[str]:
        global _cli_logger
        args = [self.argument.long]
        _cli_logger.critical(f"{self}")
        value = prompt_user(f"Please provide a valid value for {self.argument.long}: ")
        if value:
            args.extend(value.split(" "))
        return args


from typing import Literal


class CliArgument:
    def __init__(
        self,
        long: str,
        short: str | None = None,
        default: any | None = None,
        expect: Literal["one", "many"] = "one",
        type: Callable[[str], any] | None = None,
        required: bool = False,
        accepted_values: list[str] | None = None,
    ):
        self.long = long
        self.short = short
        self.default = default
        self.expect = expect
        self.values = None
        self._raw_values = None
        self.type = type
        self.required = required
        self.accepted_values = accepted_values
        self._finalize()

    def _finalize(self):
        # indicate not provided.
        self.provided = False
        # prepare bool type handling
        if self.type == bool:
            if not self.accepted_values:
                self.accepted_values = ["y", "yes", "n", "no", "true", "false"]
            if self.default is None:
                self.default = False
        # wrap default values in array if needed
        if not isinstance(self.default, list) and self.default is not None:
            self.default = [self.default]

    def _validate(self):
        if self.required and not self.provided:
            raise CliArgumentError(self, "required")
        elif self.expect == "one" and len(self._raw_values) > 0:
            raise CliArgumentError(self, "too_many_values")
        elif self.provided and self._get_value() is None:
            raise CliArgumentError(self, "missing_value")
        elif self.provided and self.accepted_values:
            invalid_values = [
                v for v in self._raw_values if v not in self.accepted_values
            ]
            if len(invalid_values) > 0:
                raise CliArgumentError(self, "unexpected_value(s)")

    def _parse_bool_value(self, value: str) -> bool:
        if value.lower() in ["y", "yes", "true"]:
            return True
        elif value.lower() in ["n", "no", "false"]:
            return False
        raise CliArgumentValueError(self, value)

    def _parse_final_values(self):
        # Only process provided
        if not self.provided:
            return
        if len(self._raw_values) == 0:
            # For bool type, set to True if no value provided
            if self.type == bool:
                self.values.append(True)
            # Else, set to default if available
            elif self.default is not None:
                self.values.extend(self.default)
        else:
            # Parse raw values
            for value in self._raw_values:
                # Prepare reader.
                value_reader = str
                if self.type == bool:
                    value_reader = self._parse_bool_value
                elif self.type is not None:
                    value_reader = self.type
                self.values.append(value_reader(value))

    def _get_value(self) -> any | None:
        # for bool type with no values, return default
        if self.type == bool and not self.values:
            return self.default[0] if self.expect == "one" else self.default
        return (
            None
            if not self.values
            else self.values[0] if self.expect == "one" else self.values
        )

    def to_dict(self) -> dict:
        return {
            "long": self.long,
            "short": self.short,
            "default": self.default,
            "values": self.values,
            "type": self.type,
            "required": self.required,
            "accepted_values": self.accepted_values,
        }

    def request_value(self, message) -> None:
        value = prompt_user(message)

    def store_raw_values(self, args: list[str]) -> None:
        self.provided = True
        self._raw_values = [*args]


CLI_ARGUMENTS: list[CliArgument] = [
    CliArgument(
        "--print-args",
        short="-p",
        expect="many",
        accepted_values=["full", "all"],
        type=str,
        default="all",
    ),
    CliArgument("--help", short="-h", type=bool),
    CliArgument("--silent", short="-s", type=bool),
    CliArgument("--confirm", short="-c", type=bool),
]


class CliArgumentParser:

    _logger: Logger.Logger = None
    _config: Config.Config = None
    _module: ModuleType = None
    _simple_module_name: str = None
    _module_name: str = None
    _cli_args: dict[str, CliArgument] = dict()
    _short_cli_args_mapping: dict[str, str] = dict()

    def __init__(
        self, module: ModuleType, cli_arguments: list[CliArgument] | None = None
    ):

        self._module = module
        self._simple_module_name = self._module.__name__.split(".")[-1]
        self._module_name = self._module.__name__

        self._config = Config.get().create(self._simple_module_name + "-module")
        self._logger = Logger.get(
            self._module_name + ".logger",
            create_config_dict=Config.get("logger").to_dict(),
            stream=sys.stdout,
        )

        self._cli_args = dict()
        self._short_cli_args = dict()
        self.add_args(*CLI_ARGUMENTS)

        build_parser_func = getattr(self._module, "build_parser")
        build_parser_func(self)

    def print_args(self):
        if "full" in self._get_arg("--print-args"):
            self._logger.debug(
                " CLI Arguments: ",
                self._cli_args,
                force_inline=lambda k: "accepted_values" in k,
            )
        elif "all" in self._get_arg("--print-args"):
            self._logger.debug(
                " CLI Arguments: ",
                {
                    k: v
                    for k, v in self._cli_args.items()
                    if v.values is not None and k != "--print-args"
                },
            )
        else:
            self._logger.debug(
                " CLI Arguments: ",
                {
                    k: v
                    for k, v in self._cli_args.items()
                    if k[2:] in self._get_arg("--print-args")
                },
                force_inline=lambda k: "accepted_values" in k,
            )

    def add_args(
        self,
        *arguments: CliArgument,
    ):
        for argument in arguments:
            self._add_arg(argument)

    def _add_arg(
        self,
        argument: CliArgument,
    ):
        self._cli_args[argument.long] = argument
        self._cli_args["--print-args"].accepted_values.append(argument.long[2:])
        if argument.short:
            if argument.short in self._cli_args:
                raise CliError(f"Duplicate short argument {argument.short}")
            elif not re.search(r"^-[a-zA-Z]$", argument.short):
                raise CliError(
                    f"Invalid short argument format {argument.short}. Only one letter allowed after '-'."
                )
            else:
                self._short_cli_args_mapping[argument.short] = argument.long

    def get_arg(self, flag: str) -> any:
        """Get argument by long form."""
        return self._get_arg(flag)

    def _get_arg(self, flag: str) -> any:
        """Get argument by long form."""
        if not flag.startswith("--"):
            raise CliError(
                f"Unexpected flag {flag}. Expected long form starting with '--'."
            )
        elif not flag in self._cli_args:
            raise CliError(f"Unknown flag {flag}.")
        return self._cli_args[flag]._get_value()

    def parse_args(self, args: list[str] = []) -> None:
        errors = self._parse_args(args)
        if errors:
            if self.get_arg("--silent"):
                raise CliError(
                    "CLI argument parsing failed in silent mode:\n/;_cross/;/ "
                    + "\n/;_cross/;/ ".join([str(e) for e in errors])
                )
            while len(errors) > 0:
                solved_args = []
                while len(errors) > 0:
                    solved_args.extend(errors.pop(0).solve())
                errors = self._parse_args(solved_args)

    def _parse_args(self, args: list[str] = []) -> list[CliError]:
        """Parse arguments."""
        parsed_args = args.copy()
        hits: list[str] = []
        errors: list[CliError] = []

        def consume_flag() -> Tuple[str, list[str]]:
            from itertools import takewhile

            nonlocal parsed_args
            arg = parsed_args[0]
            values = list(takewhile(lambda x: not x.startswith("-"), parsed_args[1:]))
            parsed_args = parsed_args[len(values) + 1 :]
            hits.append(arg)
            return arg, values

        def hit(argument: CliArgument) -> bool:
            return argument.long in hits or argument.short in hits

        while len(parsed_args) > 0:
            try:
                res = consume_flag()
                flag = res[0]
                values = res[1]
                if not flag.startswith("--"):
                    if len(flag) > 2 and values:
                        raise CliError(
                            f"Combinated short flags {flag} cannot have values."
                        )
                    for flag in flag[1:]:
                        short_flag = "-" + flag
                        if not short_flag in self._short_cli_args_mapping:
                            raise CliError(f"Unknown short flag {short_flag}.")
                        else:
                            self._cli_args[
                                self._short_cli_args_mapping[short_flag]
                            ].store_raw_values(values)
                else:
                    if not flag in self._cli_args:
                        raise CliError(f"Unknown flag {flag}.")
                    self._cli_args[flag].store_raw_values(values)
            except CliError as e:
                errors.append(e)

        # Validate arguments
        for argument in self._cli_args.values():
            try:
                argument._validate()
                argument._parse_final_values()
            except CliError as e:
                errors.append(e)

        return errors
