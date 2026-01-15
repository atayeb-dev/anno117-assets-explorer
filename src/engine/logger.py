# ============================================================
# ANSI Logging Utility
# ============================================================

from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING, Callable, cast

if TYPE_CHECKING:
    from src import Config

import random, re, sys
from io import StringIO
from time import sleep
from typing import Literal, TextIO, Tuple
from src import utilities


class KrakenError(Exception):
    """Special exception to represent a kraken in the logger."""

    pass


_ANSI_CODES = {
    "r": [0],  # reset
    "h": [8],  # hide
    "cr": [31],  # red
    "cg": [32],  # green
    "cy": [33],  # yellow
    "cb": [34],  # blue
    "cm": [35],  # magenta
    "cc": [36],  # cyan
    "cw": [37],  # white
    "bo": [1],  # bold
    "it": [3],  # italic
    "di": [2],  # dim
}

# Markers and pattern /;pattern/
_ANSI_MARK = "/;"
_S_END_MARK = _ANSI_MARK[::-1]
_ansi_pattern = (
    lambda tag: f"{_ANSI_MARK}{tag}{_S_END_MARK if tag.split('/')[0] in _s_keys_matches.keys() else _ANSI_MARK[0]}"
)
# Specials: /;pattern/args;/
# https://www.compart.com/en/unicode/
_enclose = lambda c, *args: f"{c}" if not args[0] else f"/;{';'.join(args)}/{c}/;"
_specials = {
    "__kraken/;/": lambda *args: f"/;__kraken/--;/;__kraken/--;/;/",
    "_cross/s;;/": lambda *args: _enclose("✗", *args),
    "_check/s;;/": lambda *args: _enclose("✓", *args),
    "_arrow/s;;/": lambda *args: _enclose("→", *args),
    "_wrench/s;;/": lambda *args: _enclose("🛠", *args),
    "_repeat/c;i;/": lambda *args: f"{args[0]*max(1,int(args[1]))}",
}
_s_keys_matches = dict([(key.split("/")[0], val) for key, val in _specials.items()])
_ansi_text = lambda codes: f"\x1b[{';'.join(str(c) for c in codes)}m"
_ansi_tag_text = (
    lambda tag: f"\x1b[{';'.join(str(c) for c in [_ANSI_CODES[t][0] for t in tag.split(';')])}m"
)


def _detect_ansi_pattern(string: str) -> Tuple[str, str]:

    if not string.startswith(_ANSI_MARK):
        return ("", string)

    test_str = string[len(_ANSI_MARK) :]
    hit = False
    ansi_codes = []
    max_lookahead_error = 20
    lookahead_error = lambda: (
        string[:max_lookahead_error]
        + ("..." if len(string) > max_lookahead_error else "")
    )

    max_code_len = max(len(key) for key in _specials)  # arbitrary
    max_lookahead = max_code_len + 1  # +1 for trailing / or ;
    lookahead = test_str[0:max_lookahead]

    # search specials then shortcuts then single
    tags = _s_keys_matches.keys() | _ANSI_CODES.keys()
    for tag in tags:
        if lookahead.startswith(f"{tag}"):
            hit = tag
            if lookahead.startswith(f"{tag}/"):
                pattern = ""
                text = ""
                if tag in _s_keys_matches.keys():
                    # lookup to backward marker after "/"
                    lookahead = test_str[len(f"{tag}/") :].split(_S_END_MARK)
                    if len(lookahead) < 2:
                        raise SyntaxError(
                            f"Missing special trailing end marker {_S_END_MARK} in: {lookahead_error()}"
                        )
                    lookahead = lookahead[0]
                    args = lookahead.split(";")
                    pattern = _ansi_pattern(f"{tag}/{lookahead}")
                    text = _s_keys_matches[tag](*args)
                else:
                    pattern = _ansi_pattern(tag)
                    text = _ansi_text(_ANSI_CODES[tag])
                return (pattern, text)
            break

    if hit and f";" not in lookahead:
        raise SyntaxError(
            f"Invalid pattern in: {lookahead_error()}. Hit {hit} with missing trailing ';' or '/'"
        )

    # lookahead for combinations.
    lookahead = test_str[0:max_lookahead].split("/")[0]
    tags = lookahead.split(";")
    ansi_codes = []
    for tag in tags:
        # Numeric code
        if tag.isdigit():
            ansi_codes.append(int(tag))
        # Maybe /;some random text
        elif tag not in _ANSI_CODES.keys():
            # consider it a single reset tag '/;'
            return (_ANSI_MARK, _ansi_text(_ANSI_CODES["r"]))
        # Compose shortcuts
        else:
            ansi_codes.extend(_ANSI_CODES[tag])
        # End on trailing mark
        if f"{tag}/" in lookahead + "/":
            return (_ansi_pattern(lookahead), _ansi_text(ansi_codes))
    # Strict trailing mark
    raise SyntaxError(
        f"Invalid pattern in: {lookahead_error()}. Hit {_ansi_pattern(lookahead)} with missing trailing '/'"
    )


_default_kwargs = {
    "animate": False,
    "flush_rate": [5, 15],
    "ansi": True,
    "verbose": True,
    "verbose_only": False,
    "data_print": {
        "max_inline": 160,
        "compact": False,
        "force_inline": False,
        "decorate_items": True,
        "styles": {
            "enable": True,
            "sep": "cw;di",
            "obji": "cb;di",
            "objk": "cg;bo",
            "arri": "cb;di",
            "str": "cw;it",
            "bool": "cc",
            "path": "cc;it",
            "num": "cb",
            "unkn": "cr;di",
        },
    },
    "debug": {
        "fallback": False,
        "print_indent_chars": False,
    },
}


class LoggerKwargs:

    def __init__(self, logger: Logger, **kwargs):
        self._logger = logger
        self._kwargs = kwargs

    def get(self, dict_path: str):

        # Get value in knwargs first
        value = utilities.dict_path(self._kwargs, dict_path)
        if value is not None:
            return value

        # Prepare default fallback
        if self._logger._name == "default":
            # We are in default logger, use hardcoded defaults
            default = utilities.dict_path(_default_kwargs, dict_path)
            if default is None:
                raise RuntimeError(f"Missing Logger default kwarg key: '{dict_path}'")
        else:
            # Get default from default logger
            default = LoggerKwargs(get("default")).get(dict_path)

        # Get value from config with default fallback
        if self._logger._config is not None:
            return self._logger._config.get(dict_path, default=default)
        return default


class DataPrinter:

    def __init__(self, logger: Logger):
        self._logger = logger

    def _default_inline(self, dl: dict | list) -> bool:
        # Check we are checking from the inline-checker logger itself
        if self._logger._name == "inline-checker":
            return True
        # Create a temporary logger to measure length.
        logger = Logger(
            "inline-checker",
            stream=StringIO(),
        )
        # Write the data to the temporary logger forcing inline mode
        logger.write(
            dl,
            ansi=False,
            animate=False,
            data_print={
                "force_inline": True,
                "compact": self._logger._kwargs.get("data_print.compact"),
                "styles": {"enable": False},
            },
        )

        max_inline = self._logger._kwargs.get("data_print.max_inline")
        remaining = max_inline - len(self._logger._indents[-1])
        to_write = len(cast(StringIO, logger._stream).getvalue())
        if to_write > remaining:
            return False
        return True

    def get_style(self, style: str) -> str:
        return self._logger._kwargs.get(f"data_print.styles.{style}")

    def build_simple_style(self, style: str, text: str) -> str:
        if not self._logger._kwargs.get("data_print.styles.enable"):
            return text
        return f"/;{self.get_style(style)}/{text}/;"

    def full_current_path(self) -> str:
        return ".".join(map(str, self._logger._current_path))

    def force_inline(self) -> bool:
        force_inline = self._logger._kwargs.get("data_print.force_inline")
        if isinstance(force_inline, bool):
            return force_inline
        elif isinstance(force_inline, str) and force_inline:
            return re.search(rf"{force_inline}", self.full_current_path()) is not None
        return False

    def compact(self) -> bool:
        compact = self._logger._kwargs.get("data_print.compact")
        if isinstance(compact, bool):
            return compact
        elif isinstance(compact, str) and compact:
            return re.search(rf"{compact}", self.full_current_path()) is not None
        return False

    def decorate(self, decoration: str, type: str = "") -> str:
        path = self._logger._current_path
        if decoration == "start" or decoration == "end":
            str_decoration = ""
            if type == "list":
                str_decoration = "[" if decoration == "start" else "]"
            elif type == "dict":
                str_decoration = "{" if decoration == "start" else "}"
            return self.build_simple_style("sep", str_decoration)
        elif decoration == "comma":
            return self.build_simple_style("sep", ",")
        elif decoration == "item":
            if self._logger._kwargs.get("data_print.decorate_items"):
                if isinstance(path[-1], int):
                    return self.build_simple_style("arri", f" {str(path[-1])} ")
                else:
                    return f" /;_arrow/{self.get_style("obji")};//; "
        elif decoration == "key":
            return self.build_simple_style(
                "objk", str(path[-1]) + self.build_simple_style("sep", ":")
            )
        return ""

    def decorate_value(self, value: any) -> str:
        if isinstance(value, bool):
            return self.build_simple_style("bool", str(value))
        elif isinstance(value, int) or isinstance(value, float):
            return self.build_simple_style("num", str(value))
        elif isinstance(value, str):
            return self.build_simple_style("str", f"'{str(value)}'")
        elif isinstance(value, Path):
            return self.build_simple_style("path", f"{str(value)}")
        else:
            return self.build_simple_style("unkn", f"{str(value)}")

    def _write_dict(self, d: dict) -> None:
        self._logger._write(self.decorate("start", type="dict"))
        self._logger._indent()
        inline = self._default_inline(d) or self.force_inline()
        inlining = inline
        compacting = self.compact()
        for key, item in d.items():
            self._logger._current_path.append(key)
            first = key == list(d.keys())[0]
            last = key == list(d.keys())[-1]
            if first:
                inlining = True
            if not inlining:
                self._logger._new_line(" ")
            if not inline and not compacting:
                self._logger._write(self.decorate("item"))
            self._logger._write(self.decorate("key"))
            if not compacting:
                self._logger._write(" ")
            self._write_value(item)
            if not last:
                self._logger._write(self.decorate("comma"))
                if not compacting:
                    self._logger._write(" ")
            self._logger._current_path.pop()
            inlining = inline
        self._logger._write(self.decorate("end", type="dict"))
        self._logger._dindent()

    def _write_list(self, l: list) -> None:
        self._logger._write(self.decorate("start", type="list"))
        self._logger._indent()
        inline = self._default_inline(l) or self.force_inline()
        inlining = inline
        compacting = self.compact()
        for i, item in enumerate(l):
            self._logger._current_path.append(i)
            first = i == 0
            last = i == len(l) - 1
            if first:
                inlining = True
            if not inlining:
                self._logger._new_line(" ")
            if not inline and not compacting:
                self._logger._write(self.decorate("item"))
            self._write_value(item)
            if not last:
                self._logger._write(self.decorate("comma"))
                if not compacting:
                    self._logger._write(" ")
            self._logger._current_path.pop()
            inlining = inline
        self._logger._write(self.decorate("end", type="list"))
        self._logger._dindent()

    def _write_value(self, v: any) -> None:
        if isinstance(v, dict):
            self._write_dict(v)
        elif isinstance(v, list):
            self._write_list(v)
        elif hasattr(v, "to_dict") and callable(getattr(v, "to_dict")):
            self._write_dict(v.to_dict())
        else:
            self._logger._write(self.decorate_value(v))


class Logger:

    def __init__(
        self,
        name: str,
        stream: TextIO = sys.stdout,
    ):
        self._name = name
        self._stream = stream
        self._indents: list[str] = [""]
        self._indents_buffer: TextIO = StringIO()
        self._data_printer = DataPrinter(self)
        self._current_path: list[str | int] = ["root"]
        self._config = None
        self._kwargs: LoggerKwargs = None

    def get_config_key(self) -> str:
        return f"loggers.{self._name}"

    def load_config(
        self,
        trust: Literal["file", "dict"] = "file",
        config_dict: dict = {},
    ):
        if self._config is not None:
            raise RuntimeError("Logger config already loaded.")
        from src import Config

        self._config = Config.create(
            self.get_config_key(), trust=trust, config_dict=config_dict
        )

    def reload_config(
        self,
        trust: Literal["file", "dict"] = "file",
        config_dict: dict = {},
    ):
        if self._config is None:
            raise RuntimeError("Logger config not loaded yet.")
        self._config.reload(trust=trust, config_dict=config_dict)

    def get_config(self) -> Config.Config:
        if self._config is None:
            raise RuntimeError("Logger config not loaded yet.")
        return self._config

    def write(self, *args, **kwargs) -> None:
        try:
            def_stream = None
            self._kwargs = LoggerKwargs(self, **kwargs)
            self._indents = [""]
            self._current_path = ["root"]
            if "stream" in kwargs.keys():
                def_stream = self._stream
                self._stream = cast(TextIO, kwargs["stream"])
            if self._kwargs.get("debug.fallback"):
                if not self._fallback_checked:
                    self._fallback_checked = True
                    print("==")
                    print("Logger internal fallback mode active.")
                    print("==")
                print(*args, end="", file=self._stream)
            else:
                self._fallback_checked = False
                self._write(*args)
        except Exception as e:
            raise e
        finally:
            self._stream.flush()
            self._indents = [""]
            self._indents_buffer.seek(0)
            self._indents_buffer.truncate(0)
            self._kwargs = None
            if def_stream is not None:
                self._stream = def_stream

    def print(self, *args, **kwargs) -> None:
        if "end" not in kwargs:
            args = [*args, "\n"]
        else:
            args = [*args, kwargs["end"]]
            del kwargs["end"]
        return self.write(*args, **kwargs)

    def error(self, *args, **kwargs) -> None:
        args = [f"/;_cross/cr;/ ", *args]
        return self.print(*args, **kwargs)

    def critical(self, *args, **kwargs) -> None:
        args = [f"/;cr;bo//;_cross/;/ ", *args, "/;"]
        return self.print(*args, **kwargs)

    def success(self, *args, **kwargs) -> None:
        args = [f"/;_check/cg;/ ", *args]
        return self.print(*args, **kwargs)

    def prompt(self, *args, **kwargs) -> None:
        args = [f"/;_arrow/cb;bo;/ ", *args]
        return self.print(*args, **kwargs)

    def debug(self, *args, **kwargs) -> None:
        args = [f"/;cm;bo//;_wrench/;/ ", *args, "/;"]
        return self.print(*args, **kwargs)

    def _indent(self) -> None:
        indents_char = self._indents_buffer.getvalue()
        indents_char = re.sub(
            r"\x1b\[[0-9;]*m", "", indents_char
        )  # just in case some are still here.
        self._indents.append(indents_char)

    def _dindent(self) -> None:
        self._indents.pop()

    def _new_line(self, indent_char=" ") -> None:
        self._stream.write("\n")
        indents_char = self._indents[-1]

        if len(self._indents) > 1:
            if self._kwargs.get("debug.print_indent_chars"):
                self._stream.write(
                    _ansi_tag_text("cm;di")
                    + self._name
                    + ":"
                    + indents_char[len(self._name) + 1 :]
                    + _ansi_tag_text("r")
                )
            else:
                self._stream.write(indent_char * len(indents_char))
        elif len(self._indents[0]) > 0:
            raise RuntimeError(
                "Logger internal error: _indents stack corrupted (len > 1 with non-empty base)"
            )
        self._indents_buffer.seek(0)
        self._indents_buffer.truncate(0)
        self._indents_buffer.write(indents_char)

    def _write(self, *args) -> None:

        animate = self._kwargs.get("animate")
        flush_rate = self._kwargs.get("flush_rate")
        process_ansi = self._kwargs.get("ansi")
        verbose = self._kwargs.get("verbose")
        verbose_only = self._kwargs.get("verbose_only")

        if verbose_only and not verbose:
            return

        for arg in args:
            if not isinstance(arg, str):
                self._data_printer._write_value(arg)
            else:
                remaining = arg
                security_limit = len(remaining) + 10000
                loops = 0
                while remaining:
                    loops += 1
                    # Mange ANSI patterns on the fly
                    lookahead = remaining[0:2]
                    if process_ansi and lookahead == _ANSI_MARK:
                        ansi = _detect_ansi_pattern(remaining)
                        remaining = ansi[1] + remaining[len(ansi[0]) :]
                        # Do not let the kraken grow...
                        if loops > security_limit:
                            raise KrakenError(
                                f"Pattern recursion limit exceeded. You may have an kraken growing in {remaining[0:60]}!"
                            )
                        # Continue to provide recursive patterns
                        continue

                    # Get the char
                    char = remaining[0]

                    # Manage new lines
                    if char == "\n":
                        remaining = remaining[1:]
                        self._new_line(" ")
                        continue

                    # Optim: ansi codes => write all at once, do not add to indent buffer
                    if char == "\x1b":
                        lookahead = remaining[
                            0 : max(20, len(remaining))
                        ]  # 20 should be enough for ansi codes
                        ansi_match = re.match(r"\x1b\[[0-9;]*m", lookahead).group(0)
                        self._stream.write(ansi_match)
                        remaining = remaining[len(ansi_match) :]
                        continue

                    # Write the char
                    self._stream.write(char)
                    self._indents_buffer.write(char)

                    # Consume the char
                    remaining = remaining[1:]

                    # Check no animation mode
                    if not animate:
                        continue

                    # Flush based on flush rate
                    if len(remaining) == 0:
                        self._stream.flush()
                        continue
                    mod = max(1, random.randint(flush_rate[0], flush_rate[1]))
                    if len(remaining) % mod == 0:
                        self._stream.flush()
                        sleep(random.uniform(0.01, 0.03))


def create_default(stream: TextIO, verbose: bool = False) -> Logger:
    global _default_kwargs
    _default_kwargs["verbose"] = verbose
    return Logger(name="default", stream=stream)


def create(name: str, stream: TextIO = sys.stdout, config_dict: dict = {}) -> Logger:
    from src import _loggers

    """Create a new logger by name."""
    logger = Logger(name=name, stream=stream)
    if name in _loggers.keys():
        raise RuntimeError(f"Logger '{name}' already exists.")
    logger.load_config(config_dict=config_dict)
    _loggers[name] = logger
    return logger


def critical(message: str = "", ex: Exception = None, print_stack=True) -> str:
    logger = get("traceback", fallback=True)
    if message:
        logger.critical(f"{message}")
    elif ex is not None:
        logger.critical(f"({type(ex).__name__}) {ex} ")
    if print_stack and ex is not None:
        traceback(ex)


def traceback(ex: Exception, **kwargs) -> str:
    import traceback

    logger = get("traceback", fallback=True)
    for frame in traceback.extract_tb(ex.__traceback__)[::-1]:
        logger.debug(
            {frame.name: f"{frame.filename}:{frame.lineno}"},
            animate=False,
            data_print={"force_inline": True},
            **kwargs,
        )


def get(name: str = "default", fallback=False) -> Logger:
    from src import _loggers

    """Get or create a logger by name."""
    if not name in _loggers.keys():
        if fallback:
            default_logger = _loggers["default"]
            if default_logger is None:
                raise RuntimeError("Default logger not initialized.")
            default_logger.debug(
                f"Logger '{name}' not found. Falling back to default logger.",
                verbose_only=True,
            )
            return default_logger
        raise RuntimeError(f"Logger '{name}' not found. Use create() to create logger.")
    return _loggers[name]
