"""
Command-line argument parsing for Atayeb Assets Explorer.

Provides a custom ArgumentParser that raises exceptions instead of exiting.
"""

# ============================================================
# IMPORTS
# ============================================================


from __future__ import annotations
import copy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src import Logger, Config

import re, sys
from pathlib import Path
from types import ModuleType
from typing import Callable, Tuple, Literal
from tkinter import Tk, filedialog
from src import AppPath


def logger() -> Logger.Logger:
    from src import Logger

    return Logger.get("cli", fallback=True)


class CliError(Exception):

    def __init__(self, message: str):
        super().__init__(message)

    def solve(self) -> None:
        logger().critical(f"Solve error: {self}")


class CliHelpRequest(CliError):
    pass


class CliArgumentRequest(CliError):

    def __init__(self, argument: CliArgument):
        self.argument = argument
        self.argument_name = argument.long
        if argument.short:
            self.argument_name += f"/{argument.short}"
        self.argument_name = f"[{self.argument_name}]"
        super().__init__(self.raw_message())

    def raw_message(self) -> str:
        return str(f"CliArgumentError: {type(self).__name__} in {self.argument_name}")

    def prepare_prompter(self, prompter: CLiPrompter) -> None:
        prompter.type = "error"
        prompter.allow_default = False
        prompter.prompts = [f"{self}"]

    def prepare_end_prompter(self, prompter: CLiPrompter) -> None:
        pass

    def solve(self, prompter: CLiPrompter) -> any:
        if self.argument._parser._module.get_arg("--silent"):
            raise CliError(f"Silent failure: {self}")
        self.argument._reset()
        return prompter.request_value(self)


class CliMissingRequest(CliArgumentRequest):
    def __init__(self, argument: CliArgument):
        super().__init__(argument)


class CliInvalidRequest(CliArgumentRequest):
    def __init__(self, argument: CliArgument, values: list[str]):
        self.values = values
        super().__init__(argument)

    def prepare_prompter(self, prompter: CLiPrompter) -> None:
        prompter.type = "error"
        prompter.allow_default = False
        invalid_values = self.argument._invalid_raw_values(self.values)
        accepted_values = self.argument.accepted_values
        if isinstance(accepted_values, str):
            accepted_values = f"/;cm/{accepted_values}/;"
        prompter.prompts = [
            self.argument_name,
            " Invalid value(s) ",
            invalid_values,
            ". Accepted: ",
            accepted_values,
            ": ",
        ]

    def prepare_end_prompter(self, prompter: CLiPrompter) -> None:
        prompter.prompts = [
            *prompter.prompts,
            self.argument._get_value(),
        ]


class CliConfirmRequest(CliArgumentRequest):
    def __init__(self, argument: CliArgument):
        super().__init__(argument)

    def prepare_prompter(self, prompter: CLiPrompter) -> None:
        prompter.type = "confirm"
        prompter.allow_default = True
        prompter.prompts = [
            self.argument_name,
            " Confirm ",
            self.argument.default,
            " or override: ",
        ]

    def prepare_end_prompter(self, prompter: CLiPrompter) -> None:
        if not self.argument.use_default:
            prompter.prompts = [
                *prompter.prompts,
                self.argument._get_value(),
            ]
        else:
            prompter.type = "success"
            prompter.prompts = [*prompter.prompts[:-1]]


class CLiPrompter:

    def __init__(
        self,
        allow_defaults: bool,
    ):
        self.requests = 0
        self.type: Literal[
            "request",
            "solve",
            "error",
            "success",
            "default",
        ] = "request"
        self.basetype: Literal[
            "request",
            "solve",
        ] = "request"
        self.prompts: list[any] = []
        self.allow_default = allow_defaults

    def _select_file_gui(self, title: str) -> str:
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()

        def sanitize(s: str) -> str:
            return f"'{s}'" if s else None

        fpath_dialog = lambda prefix=False: sanitize(
            ("file:" if prefix else "")
            + filedialog.askopenfilename(title=f"{title} (single file)")
        )

        fpaths_dialog = lambda prefix=False: [
            sanitize(("file:" if prefix else "") + f)
            for f in filedialog.askopenfilenames(title=f"{title} (multiple files)")
        ]

        dpath_dialog = lambda prefix=False: sanitize(
            ("dir:" if prefix else "")
            + filedialog.askdirectory(title=f"{title} (single directory)")
        )

        if self.argument.expect == "one":
            if self.argument.type == AppPath.fpath:
                filepath = fpath_dialog()
            if self.argument.type == AppPath.dpath:
                filepath = dpath_dialog()
        else:
            if self.argument.type == AppPath.fpath:
                filepaths = fpaths_dialog()
            elif self.argument.type == AppPath.dpath:
                filepaths = []
                loop = 0
                initial_title = title
                while one_file_path := dpath_dialog():
                    loop += 1
                    if loop > 1:
                        title = f"{initial_title} ({loop} directories so far, Cancel to finish)"
                    filepaths.append(one_file_path)
            filepath = (
                " ".join(filepath for filepath in filepaths) if filepaths else None
            )

        root.destroy()
        root.update()
        logger().print()  # New line after GUI dialog
        return filepath

    def end_request(self, value=any) -> None:

        self.request.prepare_end_prompter(self)
        # prefix = f""
        # if value is None or value is False or self.type == "error":
        #     prefix = f"/;_cross/cr;/ "
        # else:
        #     prefix = f"/;_check/cg;/ "
        if self.type in ["success"]:
            method = "success"
        elif self.type in ["error"]:
            method = "error"
        else:
            method = "prompt"
        logger().__getattribute__(method)(*self.build_prompt(), animate=False)

    def build_prompt(self) -> list[any]:

        prompt_parts: list[any] = copy.deepcopy(self.prompts)
        if self.type == "confirm":
            prompt_parts[0] = f"/;cc/{prompt_parts[0]}/;"
        elif self.type == "error":
            prompt_parts[0] = f"/;cr/{prompt_parts[0]}/;"
        elif self.type == "success":
            prompt_parts[0] = f"/;cg/{prompt_parts[0]}/;"
        elif self.type == "default":
            prompt_parts[0] = f"/;cy/{prompt_parts[0]}/;"
        return prompt_parts

    def request_value(self, request: CliArgumentRequest) -> any:
        input_value: str | any = ""
        self.requests += 1
        if self.requests > 3:
            logger().debug(
                f"Too many failed attempts for argument {self.argument.long}"
            )
            raise CliHelpRequest(
                "You are doing it wrong"
            )  # Too many failed attempts, raise help for user.

        request.prepare_prompter(self)
        lines = logger().prompt(*self.build_prompt(), end="") + 1

        self.request = request
        self.argument = request.argument
        if self.argument.type == AppPath.AppPath:
            raise CliError(
                "AppPath not supported. Provide AppPath.fpath or AppPath.dpath, instead."
            )
        elif self.argument.type in [AppPath.fpath, AppPath.dpath]:
            if self.argument._parser._module._config.get("cli.gui_file_dialogs", False):
                input_value = self._select_file_gui(
                    title=f"Select {self.argument.long}"
                )

        if not input_value:
            input_value = input().strip()

        # Print and clean after input to reset the logger indents.
        logger().print()
        logger().clean_lines(1)

        if self.allow_default and not input_value:
            self.argument.use_default = True
            self.type = "default"
            logger().clean_lines(lines)
            self.end_request(value=self.argument._get_value())
            return self.argument._get_value()
        try:
            raw_values = self.argument._parse_raw_input(input_value)
            self.argument._validate_raw_values(raw_values)
        except CliArgumentRequest as e:
            # Need print + clean to avoid double prompt lines
            logger().print()
            logger().clean_lines(1)
            self.type = "error"
            logger().clean_lines(lines)
            self.end_request(value=raw_values)
            return e.solve(prompter=self)

        self.type = "success"
        self.end_request(value=self.argument._get_value())
        return self.argument._get_value()


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
        accepted_values: list[str] | str = None,
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
        self.values: list[any] = []
        self.use_default: bool = False
        self.provided: bool = False
        self.config_default: bool = False
        self.parsed_from_flags: bool = False

    def _finalize(self):
        # Read any value from config to override default
        config_value = self._read_from_config()
        if config_value is not None:
            logger().debug(
                f"Setting argument {self.long} default from config: ",
                config_value,
                verbose_only=False,
            )
            self.config_default = True
            self.default = config_value
        # prepare bool type handling
        if self.type == bool:
            if not self.accepted_values:
                self.accepted_values = ["Y", "Yes", "N", "No", "True", "False"]
                self.accepted_values.extend(v.lower() for v in [*self.accepted_values])
            if self.default is None:
                self.default = False
        # prepare AppPath type handling
        if self.type in [AppPath.fpath, AppPath.dpath]:
            if not self.accepted_values:
                self.accepted_values = AppPath.app_path_pattern
        # Check Path type
        if self.type == Path:
            raise CliError("Use AppPath for Path type arguments.")

    def to_dict(self) -> dict:
        return self.__dict__

    def _parse_raw_input(self, raw_input: str | None) -> list[str] | None:
        import shlex

        if raw_input:
            if self.expect == "one":
                return [raw_input]
            else:
                return shlex.split(raw_input)
        return []

    def _parse_bool_value(self, value: str) -> bool:
        if value.lower() in ["y", "yes", "true"]:
            return True
        elif value.lower() in ["n", "no", "false"]:
            return False
        raise CliArgumentRequest(self, "unexpected_value")

    def _parse_raw_value(self, raw_value: str) -> any:
        logger().debug(
            f"Parsing argument {self.long} value '{raw_value}' with type {self.type}",
            verbose_only=True,
        )
        if self.type == bool:
            return self._parse_bool_value(raw_value)
        elif self.type is not None:
            return self.type(raw_value)
        return raw_value

    def _validate_raw_values(self, raw_values: list[str], store=True) -> list[any]:
        if self.expect == "one" and len(raw_values) > 1:
            raise CliInvalidRequest(self, raw_values)
        elif len(raw_values) == 0:
            # assume a boolean flag without value as an activation
            if self.type == bool:
                raw_values.append("y")
            # check for required flag without value
            elif self.required and self.default is None:
                raise CliMissingRequest(self, raw_values)
        elif len(self._invalid_raw_values(raw_values)) > 0:
            raise CliInvalidRequest(self, raw_values)
        values = [self._parse_raw_value(v) for v in raw_values]
        if store:
            self.provided = True
            self.values = values
        return copy.deepcopy(values)

    def _read_from_config(self) -> any | None:
        config_value = self._parser._module._config.get(self.long)

        if config_value is None:
            return None

        if isinstance(config_value, str):
            config_raw_values = self._parse_raw_input(config_value)
            try:
                values = self._validate_raw_values(config_raw_values, store=False)
                return values[0] if values and self.expect == "one" else values
            except CliArgumentRequest:
                logger().critical(
                    f"Invalid {self.long} raw values from config: ",
                    config_raw_values,
                    verbose_only=True,
                )
                return None
        else:
            # Assume the configuration holds the good type
            logger().debug(
                f"Assuming {self.long} typed config value: ",
                {
                    "value": config_value,
                    "type": type(config_value).__name__,
                },
                verbose_only=True,
            )
            return config_value

    def _invalid_raw_values(self, raw_values: list[str]) -> list[str]:
        if isinstance(self.accepted_values, list):
            return [v for v in raw_values if v not in self.accepted_values]
        elif isinstance(self.accepted_values, str):
            pattern = re.compile(self.accepted_values)
            return [v for v in raw_values if not pattern.match(v)]
        return []

    def _reset(self) -> None:
        self.values = []
        self.provided = False
        self.use_default = False

    def _get_value(self) -> any | None:
        if self.use_default:
            # Assume default is genuine.
            return self.default
        return (
            None
            if not self.values
            else self.values[0] if self.expect == "one" else self.values
        )


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
        self._raw_flags: dict[str, list[str]] = {}

    def print_args(self):

        def obtain(arg: CliArgument):
            return (
                arg._get_value() if not "full" in self.get_arg("--print-args") else arg
            )

        if "all" in self.get_arg("--print-args"):
            logger().debug(
                " CLI Arguments: ",
                {k: obtain(v) for k, v in self._cli_args.items()},
                force_inline="accepted_values",
            )
        elif "provided" in self.get_arg("--print-args"):
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
                    if k[2:] in self.get_arg("--print-args")
                },
                force_inline="accepted_values",
            )

    def check_flag(self, flag: str) -> None:
        """Check if flag is valid."""
        if not flag.startswith("--"):
            raise CliError(
                f"Unexpected flag {flag}. Expected long form starting with '--'."
            )
        elif not flag in self._cli_args:
            raise CliError(f"Unknown flag {flag}.")

    def _add_arg(
        self,
        argument: CliArgument,
    ):
        argument._parser = self
        self._cli_args[argument.long] = argument
        self._cli_args["--print-args"].accepted_values.append(argument.long[2:])
        if argument.short:
            if argument.short in self._short_cli_args_mapping:
                raise CliError(f"Duplicate short argument {argument.short}")
            elif not re.search(r"^-[a-zA-Z]$", argument.short):
                raise CliError(
                    f"Invalid short argument format {argument.short}. Only one letter allowed after '-'."
                )
            else:
                self._short_cli_args_mapping[argument.short] = argument.long
        argument._finalize()

    def add_args(self, *arguments: CliArgument):
        for argument in arguments:
            self._add_arg(argument)

    def reset_arg(self, flag: str) -> any:
        """Reset argument value by long flag."""
        self.check_flag(flag)
        arg = self._cli_args[flag]
        arg._reset()
        if flag in self._raw_flags:
            del self._raw_flags[flag]

    def get_arg(self, flag: str, allow_default=True, confirm_default=False) -> any:

        # Check flag.
        self.check_flag(flag)

        # Get argument and build prompter
        arg = self._cli_args[flag]
        prompter = CLiPrompter(
            allow_defaults=allow_default,
        )

        # Check we already indicated to use default.
        if arg.use_default:
            return arg._get_value()

        # Check if the argument is provided by flags.
        provided = False
        if flag in self._raw_flags:
            try:
                # Validate the argument
                provided = True
                arg._validate_raw_values(self._raw_flags[flag])

            except CliArgumentRequest as e:
                e.solve(prompter)

        # Check value integrity.
        value = arg._get_value()

        # If the arg is provided without value, confirm default.
        if provided and value is None:
            prompter.allow_default = True
            return CliConfirmRequest(arg).solve(prompter=prompter)

        # If the arg is not provided but has a config default, confirm usage.
        if arg.config_default and not provided:
            prompter.allow_default = True
            return CliConfirmRequest(arg).solve(prompter=prompter)

        # If the arg is not provided, use default.
        if not provided:
            arg.use_default = True

        # Return the arg value.
        return arg._get_value()

    def parse_flags(self, args: list[str] = []):
        """Parse arguments."""
        parsed_args = args.copy()

        def consume_flag() -> Tuple[str, list[str]]:
            from itertools import takewhile

            nonlocal parsed_args
            arg = parsed_args[0]
            values = list(takewhile(lambda x: not x.startswith("-"), parsed_args[1:]))
            parsed_args = parsed_args[len(values) + 1 :]
            return arg, values

        # Consume all provided flags
        flags: list[Tuple[str, list[str]]] = []
        while len(parsed_args) > 0:
            flags.append(consume_flag())

        # Gather short flags
        short_flags = [f for f in flags if not f[0].startswith("--")]

        # Check for combined short flags
        combined_shorts_flags = [f for f in short_flags if len(f[0]) > 2]

        # Remove them from shorts
        short_flags = [f for f in short_flags if f not in combined_shorts_flags]

        # Check no values provided for combined shorts
        if any(len(f[1]) > 0 for f in combined_shorts_flags):
            raise CliError(
                f"Combinated short flags {combined_shorts_flags} cannot have values."
            )

        # Register combined shorts as single shorts
        for csf in combined_shorts_flags:
            for sf in csf[0][1:]:
                flag = "-" + sf
                if not flag in short_flags:
                    short_flags.insert(0, (flag, []))

        # Rebuild the short flags with long names
        for flag in short_flags:
            long_flag = self._short_cli_args_mapping.get(flag[0])
            if not long_flag:
                raise CliError(f"Unknown short flag {flag[0]}.")
            if flag in flags:
                flags.remove(flag)
            flags.append((long_flag, flag[1]))

        # Store raw flags
        self._raw_flags = {flag: copy.deepcopy(values) for flag, values in flags}

        # Check silent
        # while len(parsed_args) > 0:
        #     try:
        #         res = consume_flag()
        #         s = res[0]
        #         values = res[1]
        #         argument: CliArgument = None
        #         if not s.startswith("--"):
        #             if len(s) > 2 and values:
        #                 raise CliError(
        #                     f"Combinated short flags {s} cannot have values."
        #                 )
        #             for s in s[1:]:
        #                 short_flag = "-" + s
        #                 if not short_flag in self._short_cli_args_mapping:
        #                     raise CliError(f"Unknown short flag {short_flag}.")
        #                 else:
        #                     argument = self._cli_args[
        #                         self._short_cli_args_mapping[short_flag]
        #                     ]
        #         else:
        #             if not s in self._cli_args:
        #                 raise CliError(f"Unknown flag {s}.")
        #             argument = self._cli_args[s]

        #         argument._validate_raw_values(values)

        #     except CliError as e:
        #         if isinstance(e, CliArgumentError):
        #             try:
        #                 e.solve()
        #             except CliError as ce:
        #                 errors.append(ce)
        #         else:
        #             errors.append(e)

        # return errors


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

    def reset_arg(self, flag: str) -> any:
        """Get argument value by long flag."""
        if self._parser is None:
            raise CliError("Parser not initialized yet.")
        return self._parser.reset_arg(flag)

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
                a._reset()
            self._config.reload()
            self._parser.parse_flags(module_args)
            if self.get_arg("--help"):
                raise CliHelpRequest("Help requested")
            elif self.get_arg("--print-args"):
                self._parser.print_args()
            result = self.run()
            return result if isinstance(result, int) else 0
        except CliHelpRequest:
            if help_text := self.help():
                logger().prompt("Help requested!")
                logger().print(help_text)
            else:
                logger().critical("Nothing can help you now...")
            return 0
        finally:
            Config.reload_for_module()
            self.finalize()
