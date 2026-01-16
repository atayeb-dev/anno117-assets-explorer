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
        prompter.type = "success"
        prompter.prompts = [
            self.argument_name,
            " Provided value: ",
            self.argument._get_value(),
        ]

    def solve(self, prompter: CLiPrompter) -> any:
        if self.argument._parser._module.get_arg("--silent"):
            raise CliError(f"Silent failure: {self}")
        self.argument._reset()
        prompter.use_request(self)
        return prompter.request_value()


class CliMissingRequest(CliArgumentRequest):
    def __init__(self, argument: CliArgument):
        super().__init__(argument)

    def prepare_prompter(self, prompter: CLiPrompter) -> None:
        prompter.type = "error"
        prompter.allow_default = False
        accepted_values = self.argument.accepted_values
        if isinstance(accepted_values, str):
            accepted_values = f"/;cm/{accepted_values}/;"
        prompter.prompts = [
            self.argument_name,
            " Missing value(s) ",
            ". Accepted: ",
            accepted_values,
            ": ",
        ]


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


class CliConfirmRequest(CliArgumentRequest):
    def __init__(self, argument: CliArgument):
        super().__init__(argument)

    def prepare_prompter(self, prompter: CLiPrompter) -> None:
        prompter.type = "prompt"
        prompter.allow_default = True
        prompter.prompts = [
            self.argument_name,
            " Confirm default: ",
            self.argument.default,
            " or override: ",
        ]

    def prepare_end_prompter(self, prompter: CLiPrompter) -> None:
        prompter.type = "success"
        if not self.argument.use_default:
            prompter.prompts = [
                self.argument_name,
                " Overridden by:  ",
                self.argument._get_value(),
            ]
        else:
            prompter.prompts = [
                self.argument_name,
                " Using default:  ",
                self.argument._get_value(),
            ]

    def solve(self, prompter):
        if self.argument._parser._module.get_arg("--auto-confirm"):
            prompter.use_request(self)
            self.argument.use_default = True
            return prompter.end_request()
        else:
            return super().solve(prompter)


class CLiPrompter:

    def __init__(
        self,
    ):
        self.requests = 0
        self.type: Literal[
            "error",
            "success",
            "prompt",
        ] = "prompt"
        self.prompts: list[any] = []
        self.allow_default: bool = False
        self.request: CliArgumentRequest = None
        self.argument: CliArgument = None

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

    def use_request(self, request: CliArgumentRequest) -> None:
        self.request = request
        self.argument = request.argument

    def prompt(self, end: str = "\n") -> any:
        if self.type in ["success"]:
            method = "success"
        elif self.type in ["error"]:
            method = "error"
        else:
            method = "prompt"
        logger().__getattribute__(method)(*self.build_prompt(), end=end)

    def build_prompt(self) -> list[any]:

        prompt_parts: list[any] = copy.deepcopy(self.prompts)
        if self.type == "prompt":
            prompt_parts[0] = f"/;cb/{prompt_parts[0]}/;"
        elif self.type == "error":
            prompt_parts[0] = f"/;cr/{prompt_parts[0]}/;"
        elif self.type == "success":
            prompt_parts[0] = f"/;cg/{prompt_parts[0]}/;"
        return prompt_parts

    def end_request(self) -> any:
        self.request.prepare_end_prompter(self)
        self.prompt()
        return self.argument._get_value()

    def request_value(self) -> any:
        input_value: str | any = ""
        self.requests += 1
        if self.requests > 3:
            logger().debug(
                f"Too many failed attempts for argument {self.argument.long}"
            )
            raise CliHelpRequest(
                "You are doing it wrong"
            )  # Too many failed attempts, raise help for user.

        self.request.prepare_prompter(self)
        self.prompt(end="")

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
            try:
                input_value = input().strip()
            except EOFError as e:
                input_value = None if self.argument.use_default else ""

        # Fallback to default if allowed
        if self.allow_default and not input_value:
            if input_value is not None:
                self.argument.use_default = True
                return self.end_request()
            else:
                input_value = ""

        try:
            raw_values = self.argument._parse_raw_input(input_value)
            self.argument._validate_raw_values(raw_values)
        except CliArgumentRequest as e:
            return e.solve(prompter=self)

        return self.end_request()


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

        self.long = long
        self.short = short
        self.default = default
        self.expect = expect
        self.type = type
        self.required = required
        self.accepted_values = accepted_values
        self.values: list[any] = []
        self.use_default: bool = False
        self.config_default: any = None

    def _finalize(self):
        # Read any value from config to override default
        config_value = self._read_from_config()
        if config_value is not None:
            logger().debug(
                f"Setting argument {self.long} default from config: ",
                config_value,
                verbose_only=True,
            )
            self.config_default = config_value
        # prepare bool type handling
        if self.type == bool:
            if not self.accepted_values:
                self.accepted_values = ["Y", "Yes", "N", "No", "True", "False"]
                self.accepted_values.extend(v.lower() for v in [*self.accepted_values])
            if self.default is None:
                self.default = False
        # Check Path type
        if self.type == Path:
            raise CliError("Use AppPath for Path type arguments.")

        # Check default value coherence
        if self.default is not None:
            if not isinstance(self.default, list) and self.expect == "many":
                raise CliError(
                    "Default value must be a list for 'many' expected arguments."
                )
            elif isinstance(self.default, list) and self.expect == "one":
                raise CliError(
                    "Default value must not be a list for 'one' expected arguments."
                )

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
                raise CliMissingRequest(self)
        elif len(self._invalid_raw_values(raw_values)) > 0:
            raise CliInvalidRequest(self, raw_values)
        values = [self._parse_raw_value(v) for v in raw_values]
        if store:
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
        self.use_default = False

    def _get_value(self) -> any | None:
        if self.use_default:
            # Assume default is genuine.
            # Config default preceeds normal default
            if self.config_default is not None:
                return self.config_default
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
                accepted_values=["config", "provided", "all"],
                type=str,
            ),
            CliArgument("--blank", short="-b", type=bool),
            CliArgument("--auto-confirm", short="-a", type=bool),
            CliArgument("--help", short="-h", type=bool),
            CliArgument("--silent", short="-s", type=bool),
        )
        self._raw_flags: dict[str, list[str]] = {}

    def clear_config_defaults(self):
        for arg in self._cli_args.values():
            arg.config_default = None

    def print_args(self):

        args: list[CliArgument] = []
        print_args_values = self._cli_args["--print-args"]._get_value()

        # Add config args.
        if "config" in print_args_values:
            args.extend([a for a in self._cli_args.values() if a.config_default])

        # Add provided args.
        if "provided" in print_args_values:
            args.extend(
                [a for a in self._cli_args.values() if a.long in self._raw_flags.keys()]
            )

        # Add all args.
        if "all" in print_args_values:
            args.extend([a for a in self._cli_args.values()])

        # Add specific flag args.
        for flag in print_args_values:
            if flag not in ["config", "provided", "all"]:
                args.append(self._cli_args[f"--{flag}"])

        # Remove duplicates.
        args = list(dict.fromkeys(args))

        print_args = []
        for provided_arg in args:
            try:
                if provided_arg.long in self._raw_flags.keys():
                    value = provided_arg._validate_raw_values(
                        self._raw_flags[provided_arg.long], store=False
                    )
                else:
                    value = provided_arg._get_value()
            except CliError as e:
                value = f"{e}"
            print_args.append(
                {
                    "long": provided_arg.long,
                    "short": provided_arg.short,
                    "value": value,
                    "default": provided_arg.default,
                    "config_default": provided_arg.config_default,
                    "accepted_values": provided_arg.accepted_values,
                }
            )
        logger().prompt(
            " CLI Arguments: ",
            print_args,
            data_print={"force_inline": "accepted_values"},
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

    def get_arg(self, flag: str) -> any:

        # Check flag.
        self.check_flag(flag)

        # Get argument and build prompter
        arg = self._cli_args[flag]
        prompter = CLiPrompter()

        # Check we already indicated to use default.
        if arg.use_default:
            return arg._get_value()

        # Check if the argument is provided by flags.
        provided = False
        if flag in self._raw_flags:
            try:
                # Consume the flag.
                provided = True
                raw_value = self._raw_flags[flag]
                del self._raw_flags[flag]

                # Validate the argument
                arg._validate_raw_values(raw_value)

            except CliArgumentRequest as e:
                e.solve(prompter)

        # Check value integrity.
        value = arg._get_value()

        # Update provided state to reflect if a value is present.
        provided = provided or (value is not None)

        # If the arg is provided without value, confirm default.
        if provided and value is None:
            prompter.allow_default = True
            return CliConfirmRequest(arg).solve(prompter=prompter)

        # If the arg is not provided but has a config default, confirm usage.
        if not provided and arg.config_default:
            prompter.allow_default = True
            return CliConfirmRequest(arg).solve(prompter=prompter)

        # If the arg is not provided, use default.
        if not provided:
            arg.use_default = True
            # Check for required arg.
            if arg.required and arg.default is None:
                return CliMissingRequest(arg).solve(prompter=prompter)

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
            if self.get_arg("--blank"):
                logger().prompt("Blank run requested")
                self._parser.clear_config_defaults()
            if self.get_arg("--print-args"):
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
