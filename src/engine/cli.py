"""
Command-line argument parsing for Atayeb Assets Explorer.

Provides a custom ArgumentParser that raises exceptions instead of exiting.
"""

# ============================================================
# IMPORTS
# ============================================================


from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src import Logger, Config

import re, sys
from pathlib import Path
from types import ModuleType
from typing import Callable, Tuple, Literal
from tkinter import Tk, filedialog


def logger() -> Logger.Logger:
    from src import Logger

    return Logger.get("cli", fallback=True)


class CliError(Exception):

    def __init__(self, message: str):
        super().__init__(message)

    def solve(self) -> list[str]:
        logger().critical(f"Solve error: {self}")


class CliHelpRequested(CliError):
    pass


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
            self.argument.clean_invalid_values()  # FIXME: maybe use reset instead, see with usage what fits better
            self.argument.prompt_for_value(
                f"{self.argument._raw_values} Please provide valid value(s) for argument {self.argument.long} (accepted: {self.argument.accepted_values}): "
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


class CliFile(Path):
    pass


class CliDir(Path):
    pass


class CliArgument:

    _parser: CliArgumentParser

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
        if long in ["--values"]:
            raise CliError("You don't want to name an argument '--values'")
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
                self.accepted_values = ["Y", "Yes", "N", "No", "True", "False"]
                self.accepted_values.extend(v.lower() for v in [*self.accepted_values])
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

    def read_raw_from_config(self) -> None:
        config_value = self._parser._module._config.get(self.long)
        if config_value is not None:
            import shlex

            self._raw_values = (
                [str(c) for c in config_value]
                if isinstance(config_value, list)
                else (
                    shlex.split(config_value)
                    if isinstance(config_value, str)
                    else [str(config_value)]
                )
            )
            logger().debug(
                f"Read argument {self.long} raw values from config: {self._raw_values}"
            )
            self.provided = True

    def reset(self) -> None:
        self.provided = False
        self.values = None
        self._raw_values = None

    def clean_invalid_values(self) -> None:
        self._raw_values = [
            v for v in self._raw_values if v not in self._invalid_raw_values()
        ]

    def _validate(self, read_config: bool = True) -> None:
        if not self.provided and read_config:
            self.read_raw_from_config()
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
        if self.long == "--help" and self._get_value():
            raise CliHelpRequested("Help requested")

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

        if self.expect == "one":
            if self.type == CliFile:
                filepath = sanitize(
                    filedialog.askopenfilename(title=f"{title} (single file)")
                )
            else:
                filepath = sanitize(
                    filedialog.askdirectory(title=f"{title} (single directory)")
                )
        else:
            if self.type == CliFile:
                filepaths = filedialog.askopenfilenames(
                    title=f"{title} (multiple files)"
                )
            elif self.type == CliDir:
                filepaths = []
                loop = 0
                while one_file_path := filedialog.askdirectory(
                    title=f"{title} (multiple directories, {loop} selected, cancel to finish)"
                ):
                    loop += 1
                    filepaths.append(one_file_path)
            filepath = (
                " ".join(sanitize(filepath) for filepath in filepaths)
                if filepaths
                else None
            )

        root.destroy()
        root.update()
        logger().print()  # New line after GUI dialog
        return filepath

    def prompt_user(self, message: str) -> str:
        """Prompt user for input with a message."""

        logger().prompt(f"{message}", end="")

        if self.type in [CliFile, CliDir] and self._parser._module._config.get(
            "cli.gui_file_dialogs", False
        ):
            input_value = self._select_file_gui(title=message)
        else:
            input_value = input().strip()
        if input_value == "":
            input_value = self.default
        logger().clean_lines(1)
        logger().prompt(f"{message}", end="", instant=True)

        if input_value is None or (
            self.type == bool and not self._parse_bool_value(input_value)
        ):
            logger().error(f"{input_value}", instant=True)
        elif input_value == "":
            logger().print(f"/;cw;di/(empty)/;", instant=True)
        else:
            logger().success(f"{input_value}", instant=True)

        return input_value

    def prompt_for_value(self, message) -> None:
        raw_value = self.prompt_user(message)
        try:
            if raw_value:
                import shlex

                self.store_raw_values(shlex.split(raw_value))
            elif not self.required:
                self.reset()
            self._validate(read_config=False)
            self._parse_final_values()
        except CliArgumentError as e:
            e.solve()

    def store_raw_values(self, args: list[str]) -> None:
        self.provided = True
        if self._raw_values is None:
            self._raw_values = []
        self._raw_values.extend(args)


class CliArgumentParser:

    def __init__(self, module: CliModule):
        self._module = module
        self._cli_args = dict[str, CliArgument]()
        self._short_cli_args_mapping = dict[str, str]()

        # Default cli arguments
        self.add_args(
            CliArgument(
                "--print-args",
                short="-p",
                expect="many",
                accepted_values=["all", "provided", "full"],
                type=str,
                default="provided",
            ),
            CliArgument("--help", short="-h", type=bool),
            CliArgument("--silent", short="-s", type=bool),
            CliArgument("--confirm", short="-c", type=bool),
        )

    def print_args(self):

        def obtain(arg: CliArgument):
            return (
                arg._get_value() if not "full" in self._get_arg("--print-args") else arg
            )

        if "all" in self._get_arg("--print-args"):
            logger().debug(
                " CLI Arguments: ",
                {k: obtain(v) for k, v in self._cli_args.items()},
                force_inline="accepted_values",
            )
        elif "provided" in self._get_arg("--print-args"):
            logger().debug(
                " CLI Arguments: ",
                {
                    k: obtain(v)
                    for k, v in self._cli_args.items()
                    if v.provided and k != "--print-args"
                },
                force_inline="accepted_values",
            )
        else:
            logger().debug(
                " CLI Arguments: ",
                {
                    k: obtain(v)
                    for k, v in self._cli_args.items()
                    if k[2:] in self._get_arg("--print-args")
                },
                force_inline="accepted_values",
            )

    def add_args(
        self,
        *arguments: CliArgument,
    ):
        for argument in arguments:
            argument._parser = self
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
                if isinstance(e, CliHelpRequested):
                    raise e
                errors.append(e)

        return errors


class CliModule:
    """
    Abstract base class for CLI modules.

    Provides common functionality for parsing arguments and executing module logic.
    Subclasses should override build_parser() and run() methods.
    """

    def __init__(self):
        """Initialize CLI module with arguments."""
        from src import Config

        self._module: ModuleType = sys.modules[self.__class__.__module__]
        self._simple_module_name: str = self._module.__name__.split(".")[-1]
        self._module_name: str = self._module.__name__
        try:
            self._config = Config.get(self.get_config_key())
        except Config.ConfigError:
            self._config = Config.create(self.get_config_key())
            logger().debug(
                f"Created config for module '{self._module_name}': ", verbose_only=True
            )
            self._config.print(
                output=lambda *args, **kwargs: logger().debug(
                    *args, **kwargs, verbose_only=True
                )
            )

        self._parser = CliArgumentParser(self)
        self.prepare()

    def get_config_key(self) -> str:
        """Get the config key associated with this module."""
        return self._simple_module_name + "_module"

    def get_config(self) -> Config.Config:
        """Get the Config instance associated with this module."""
        return self._config

    def help(self) -> str | None:
        """Return help text for the module."""
        return None

    def add_args(self, *arguments: CliArgument) -> None:
        """Add CLI arguments to the parser."""
        if self._parser is None:
            raise CliError("Parser not initialized yet.")
        self._parser.add_args(*arguments)

    def get_arg(self, flag: str) -> any:
        """Get argument value by long flag."""
        if self._parser is None:
            raise CliError("Parser not initialized yet.")
        return self._parser.get_arg(flag)

    def prepare(self) -> None:
        """
        Hook for subclasses to register CLI arguments.
        Override this method to add custom arguments.
        """
        pass

    def run(self) -> int | None:
        """
        Hook for subclasses to implement module logic.
        Override this method to implement custom behavior.

        Args:
            parser: The CliArgumentParser instance with parsed arguments.

        Returns:
            Exit code (0 on success, non-zero on failure).
        """
        raise NotImplementedError("Subclasses must implement run() method")

    def finalize(self) -> None:
        """
        Hook for subclasses to implement any finalization logic after run.
        Override this method to implement custom behavior.
        """
        pass

    def execute(self, module_args: list[str] = []) -> int:
        """Execute the module: parse arguments and run."""
        try:
            from src import Config

            Config.reload_for_module(self)
            for a in self._parser._cli_args.values():
                a.reset()
            self._config.reload()
            self._parser.parse_args(module_args)
            if self.get_arg("--print-args"):
                self._parser.print_args()
            result = self.run()
            return result if isinstance(result, int) else 0
        except CliHelpRequested:
            if help_text := self.help():
                logger().prompt("Help requested!")
                logger().print(help_text)
            else:
                logger().critical("Nothing can help you now...")
            return 0
        finally:
            Config.reload_for_module()
            self.finalize()
