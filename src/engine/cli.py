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

_cli_logger: Logger.Logger = None


def init():
    global _cli_logger
    # create default animated logger for CLI
    _cli_logger = Logger.get(
        "cli",
        stream=sys.stdout,
        create_config_dict={"animate": True},
    )


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
        argument_name = lambda arg: arg.long + (f"/{arg.short}" if arg.short else "")
        self.type = type
        message = f"Unexpected argument error: {type}"
        if type == "required":
            message = f"Missing required: {argument_name(argument)}"
        elif type == "missing_value":
            message = f"Missing value for: {argument_name(argument)}"
        elif type == "too_many_values":
            message = f"Too many values {argument._raw_values} for: {argument_name(argument)}. Expected only one."
        elif type == "unexpected_value":
            message = f"Unexpected value(s) {argument._invalid_raw_values()} for: {argument_name(argument)}, accepted values: {argument.accepted_values}"
        super().__init__(message)

    def solve(self):
        global _cli_logger
        if self.type == "required":
            self.argument.prompt_for_value(
                f"Please provide a value for required argument {self.argument.long}: "
            )
        elif self.type == "missing_value":
            self.argument.prompt_for_value(
                f"Please provide a value for argument {self.argument.long}: "
            )
        elif self.type == "too_many_values":
            self.argument.reset()
            return self.argument.prompt_for_value(
                f"Please provide only one value for {self.argument.long}: "
            )
        elif self.type == "unexpected_value":
            self.argument.clean_invalid_values()
            self.argument.prompt_for_value(
                f"Please provide valid value(s) for argument {self.argument.long} (accepted: {self.argument.accepted_values}): "
            )
        elif self.type.startswith("not_a_file"):
            self.argument.reset()
            return self.argument.prompt_for_value(
                f"Please provide valid file(s) path(s) for argument {self.argument.long}: "
            )
        elif self.type.startswith("not_a_dir"):
            self.argument.reset()
            return self.argument.prompt_for_value(
                f"Please provide valid directory(ies) path(s) for argument {self.argument.long}: "
            )


from typing import Literal


class CliFile(Path):
    pass


class CliDir(Path):
    pass


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
        self.type = type
        self.required = required
        self.accepted_values = accepted_values

        self.values: list[any] | None = None
        self._raw_values: list[str] | None = None
        self.provided: bool = False
        self._finalize()

    def _finalize(self):
        # prepare bool type handling
        if self.type == bool:
            if not self.accepted_values:
                self.accepted_values = ["y", "yes", "n", "no", "true", "false"]
            if self.default is None:
                self.default = False
        # wrap default values in array if needed
        if not isinstance(self.default, list) and self.default is not None:
            self.default = [self.default]
        # Check Path type
        if self.type == Path:
            raise CliError("Use CliFile or CliDir for Path type arguments.")

    def to_dict(self) -> dict:
        return self.__dict__

    def _invalid_raw_values(self) -> list[str]:
        return (
            [v for v in self._raw_values if v not in self.accepted_values]
            if self.accepted_values
            else []
        )

    def reset(self) -> None:
        self.provided = False
        self.values = None
        self._raw_values = None

    def clean_invalid_values(self) -> None:
        self._raw_values = [
            v for v in self._raw_values if v not in self._invalid_raw_values()
        ]

    def _validate(self):
        if not self.provided:
            if self.required:
                raise CliArgumentError(self, "required")
        else:
            if self.expect == "one" and len(self._raw_values) > 1:
                raise CliArgumentError(self, "too_many_values")
            elif len(self._raw_values) == 0 and self.default is None:
                raise CliArgumentError(self, "missing_value")
            elif len(self._invalid_raw_values()) > 0:
                raise CliArgumentError(self, "unexpected_value")
            elif self.type == CliFile:
                file_path = CliFile(Path.cwd() / self._raw_values[0])
                if not file_path.is_file():
                    raise CliArgumentError(self, f"not_a_file: {file_path.absolute()}")
            elif self.type == CliDir:
                dir_path = CliDir(Path.cwd() / self._raw_values[0])
                if not dir_path.is_dir():
                    raise CliArgumentError(self, f"not_a_dir: {dir_path.absolute()}")

    def _parse_bool_value(self, value: str) -> bool:
        if value.lower() in ["y", "yes", "true"]:
            return True
        elif value.lower() in ["n", "no", "false"]:
            return False
        raise CliError(f"Unexpected boolean value: {value}")

    def _parse_final_values(self):
        # Only process provided
        if not self.provided:
            return
        self.values = []
        if len(self._raw_values) == 0:
            _cli_logger.debug(
                f"No values provided for {self.long}, using default: {self.default}"
            )
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
                    value_reader = lambda v: self._parse_bool_value(v)
                elif self.type == Path:
                    value_reader = lambda v: Path.cwd() / v
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

    def _select_file_gui(self, title: str) -> str:
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()

        def sanitize(s: str) -> str:
            return f"'{s}'" if s else None

        # FIXME: tkinter can't open multi-dir dialog
        if self.type == CliFile:
            if self.expect == "one":
                filepath = filedialog.askopenfilename(title=title)
                filepath = sanitize(filepath)
            else:
                filepaths = filedialog.askopenfilenames(title=title)
                filepath = (
                    " ".join(sanitize(filepath) for filepath in filepaths)
                    if filepaths
                    else None
                )
        elif self.type == CliDir:
            filepath = filedialog.askdirectory(title=title)
            filepath = sanitize(filepath)

        root.destroy()
        root.update()
        _cli_logger.print()  # New line after GUI dialog
        return filepath

    def prompt_user(self, message: str) -> str:
        """Prompt user for input with a message."""
        global _cli_logger

        _cli_logger.prompt(f"{message}", end="")

        if self.type in [CliFile, CliDir]:
            input_value = self._select_file_gui(title=message)
        else:
            input_value = input().strip()
        if input_value == "":
            input_value = self.default
        _cli_logger.clean_lines(1)
        _cli_logger.prompt(f"{message}", end="", instant=True)

        if input_value is None or (
            self.type == bool and not self._parse_bool_value(input_value)
        ):
            _cli_logger.error(f"{input_value}", instant=True)
        elif input_value == "":
            _cli_logger.print(f"/;cw;di/(empty)/;", instant=True)
        else:
            _cli_logger.success(f"{input_value}", instant=True)

        return input_value

    def prompt_for_value(self, message) -> None:
        raw_value = self.prompt_user(message)
        try:
            if raw_value:
                import shlex

                self.store_raw_values(shlex.split(raw_value))
            elif not self.required:
                self.reset()
            self._validate()
            self._parse_final_values()
        except CliArgumentError as e:
            e.solve()

    def store_raw_values(self, args: list[str]) -> None:
        self.provided = True
        if self._raw_values is None:
            self._raw_values = []
        self._raw_values.extend(args)


CLI_ARGUMENTS: list[CliArgument] = [
    CliArgument(
        "--print-args",
        short="-p",
        expect="many",
        accepted_values=["all", "provided"],
        type=str,
        default="provided",
    ),
    CliArgument("--help", short="-h", type=bool),
    CliArgument("--silent", short="-s", type=bool),
    CliArgument("--confirm", short="-c", type=bool),
]


class CliArgumentParser:

    def __init__(
        self, module: ModuleType, cli_arguments: list[CliArgument] | None = None
    ):

        self._module = module
        self._simple_module_name = self._module.__name__.split(".")[-1]
        self._module_name = self._module.__name__
        self._config = Config.get().create(self._simple_module_name + "-module")
        self._cli_args = dict[str, CliArgument]()
        self._short_cli_args_mapping = dict[str, str]()

        self.add_args(*CLI_ARGUMENTS)

        build_parser_func = getattr(self._module, "build_parser")
        build_parser_func(self)

    def print_args(self):
        global _cli_logger
        if "all" in self._get_arg("--print-args"):
            _cli_logger.debug(
                " CLI Arguments: ",
                self._cli_args,
                force_inline=lambda k: "accepted_values" in k,
            )
        elif "provided" in self._get_arg("--print-args"):
            _cli_logger.debug(
                " CLI Arguments: ",
                {
                    k: v
                    for k, v in self._cli_args.items()
                    if v.provided and k != "--print-args"
                },
                force_inline=lambda k: "accepted_values" in k,
            )
        else:
            _cli_logger.debug(
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
                errors.pop(0).solve()

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
