"""
Command-line argument parsing for Atayeb Assets Explorer.

Provides a custom ArgumentParser that raises exceptions instead of exiting.
"""

# ============================================================
# IMPORTS
# ============================================================

import argparse
from html import parser
from tabnanny import check
from types import ModuleType
from typing import Type

from src.config import get_file_path, get_value_or_none
from .log import clean, log, pp_log
from tkinter import Tk, filedialog


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
        log(f"{{arr/}}Using GUI file chooser for: {key}")
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
    stream: bool = False,
    silent=False,
) -> str:
    """Ask user to input text."""
    out_provide = lambda stream: log(
        f"{{arr/}}Please provide {{hul/[{key}]}}: ",
        stream=stream,
        nl=False,
    )
    out_autoconfirm = lambda stream: log(
        f"{{arr/}}Provided {{hul/[{key}]}}: ",
        stream=stream,
        nl=False,
    )

    input_value = ""
    if autoconfirm and default is not None:
        if not silent:
            out_autoconfirm(stream)
        input_value = default
    else:
        out_provide(stream)
        input_value = input().strip()
        clean(1)
        out_provide(False)

    if input_value == "":
        input_value = default

    if input_value is None:
        log(f"{{err0/ None}} ")
    elif input_value == "":
        log(f"{{hvl/empty}} ")
    else:
        log(f"{{succ0/}} {input_value}")

    return input_value


def prompt_for_arg(
    key: str = None,
    default=None,
    is_file: bool = False,
    autoconfirm: bool = False,
    stream: bool = False,
    silent: bool = False,
) -> str:
    if is_file:
        return select_file(
            key, default=default, autoconfirm=autoconfirm, stream=stream, silent=silent
        )
    else:
        return prompt(
            key, default=default, autoconfirm=autoconfirm, stream=stream, silent=silent
        )


# ============================================================
# ARGUMENT PARSING
# ============================================================

CLI_ARGUMENTS = [
    "help",
    "instant",
    "silent",
    "live",
    "confirm",
    "print_args",
]


class CliArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that raises exceptions instead of exiting."""

    def __init__(
        self, module: ModuleType, module_args: list[str] | None = None, *args, **kwargs
    ):
        log(f"CliArgumentParser initialized {args}, {kwargs}")
        self.simple_module_name = module.__name__.split(".")[-1]
        self.module_name = module.__name__
        self.module = module
        self.cli_params = dict()
        self.module_params = dict()
        self._init_args = module_args or []
        self.hint = False

        super().__init__(add_help=False, *args, **kwargs)
        for arg in CLI_ARGUMENTS:
            default = get_value_or_none(arg, prefix="cli.", default=False)
            self.add_argument(arg, default=default, action="store_true", cli=True)

        build_parser_func = getattr(self.module, "build_parser")
        build_parser_func(self)
        self._consume_module_args()

    def add_argument(self, long: str, cli: bool = False, **kwargs):
        """Add argument with short and long form, passing through all argparse options."""

        short_form = f"-{long[0]}"
        # Check if short form is already used
        if any(
            p["short"] == short_form
            for p in [*self.cli_params.values(), *self.module_params.values()]
        ):
            short_form = None  # Skip short form if conflict

        long_form = f"--{long.replace('_', '-')}"
        store = self.cli_params if cli else self.module_params
        store[long] = {
            "short": short_form,
            "long": long_form,
            "kwargs": kwargs,
        }

        # Add argument to argparse
        if short_form:
            super().add_argument(short_form, long_form, **kwargs)
        else:
            super().add_argument(long_form, **kwargs)

    def module_arg(self, key: str):
        from .config import ConfigPath
        from .log import log

        confirm_run = self.cli("confirm")
        silent_run = self.cli("silent")
        instant_run = self.cli("instant")
        live_run = self.cli("live")

        kwargs = self.module_params.get(key, {}).get("kwargs", {})
        type = kwargs["type"] if "type" in list(kwargs.keys()) else None

        argument_value = getattr(self.module_parsed, key, None)
        is_file = type is not None and isinstance(
            type(argument_value if argument_value is not None else ""), ConfigPath
        )

        if is_file:
            config_value = get_file_path(key, prefix=self.simple_module_name + ".")
        else:
            config_value = get_value_or_none(key, prefix=self.simple_module_name + ".")
        if not live_run:
            argument_value = argument_value if argument_value else config_value
        else:
            if not self.hint:
                log("{arr/}Leave inputs {hvl/(empty)} for {hul/default}")
                self.hint = True
            argument_value = prompt_for_arg(
                key,
                default=config_value,
                is_file=is_file,
                autoconfirm=not confirm_run,
                stream=not instant_run,
                silent=silent_run,
            )
        if argument_value is None:
            return None
        if type is not None:
            return type(argument_value)
        return argument_value

    def cli(self, flag: str) -> bool:
        """Get CLI parsed arguments."""
        return getattr(
            self.cli_parsed, flag, get_value_or_none(flag, prefix="cli.", default=False)
        )

    def check_if_module_arg(self, arg: str) -> bool:
        """Check if a module parameter exists."""
        long_check = arg.startswith("--")
        if long_check:
            log("checking: " + arg[2:].replace("-", "_"))
            return arg[2:].replace("-", "_") in list(self.module_params.keys())
        else:
            log("checking: " + arg[1:])
            return any(arg[1:] == p["short"] for p in list(self.module_params.values()))

    def _consume_module_args(self) -> None:
        """Parse arguments."""
        parsed = super().parse_args(self._init_args)
        filtered = {
            k: v for k, v in vars(parsed).items() if k in self.cli_params.keys()
        }
        self.cli_parsed = argparse.Namespace(**filtered)
        filtered = {
            k: v for k, v in vars(parsed).items() if k in self.module_params.keys()
        }
        self.module_parsed = argparse.Namespace(**filtered)

    def error(self, message):
        """Raise exception instead of exiting."""
        raise Exception(message)
