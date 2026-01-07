# ============================================================
# ANSI Logging Utility
# ============================================================
import copy
from io import StringIO
import random
import re
import sys
from time import sleep
from typing import TextIO, Tuple
from glom import glom
import src.engine.logger as Logger


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


_default_config = {
    "animate": False,
    "flush_rate": [5, 15],
    "max_inline": 160,
    "verbose": True,
    "styles": {
        "sep": "cw;di",
        "obji": "cb;di",
        "objk": "cg;bo",
        "arri": "cb;di",
        "str": "cw;it",
        "bool": "cc",
        "num": "cb",
        "unkn": "cr;di",
    },
    "debug": {
        "enable": False,
        "print_indent_chars": True,
    },
}


class DataPrinter:

    _logger: Logger
    _default_inline = lambda self, dl: len(self._logger._indents[-1]) + len(
        str(dl)
    ) < self._logger._safe_get_config("max_inline")

    def __init__(self, logger: Logger):
        self._logger = logger

    def build_simple_style(self, style: str, text: str) -> str:
        style_config = self._logger._safe_get_config(f"styles.{style}")
        if style_config is None:
            return text
        return f"/;{style_config}/{text}/;"

    def full_current_path(self) -> str:
        return ".".join(map(str, self._logger._current_path))

    def decorate(self, decoration: str, type: str = "") -> str:
        path = self._logger._current_path
        style_config = lambda key: self._logger._safe_get_config(f"styles.{key}")
        build = lambda style, text: self.build_simple_style(style, text)
        if decoration == "start" or decoration == "end":
            str_decoration = ""
            if type == "list":
                str_decoration = "[" if decoration == "start" else "]"
            elif type == "dict":
                str_decoration = "{" if decoration == "start" else "}"
            return build("sep", str_decoration)
        elif decoration == "comma":
            return build("sep", ",")
        elif decoration == "item":
            if isinstance(path[-1], int):
                return build("arri", f" {str(path[-1])} ")
            else:
                return f" /;_arrow/{style_config("obji")};//; "
        elif decoration == "key":
            return build("objk", str(path[-1]) + build("sep", ":"))
        return ""

    def decorate_value(self, value: any) -> str:
        build = lambda style, text: self.build_simple_style(style, text)
        if isinstance(value, bool):
            return build("bool", str(value))
        elif isinstance(value, int) or isinstance(value, float):
            return build("num", str(value))
        elif isinstance(value, str):
            return build("str", f"'{str(value)}'")
        else:
            return build("unkn", f"{str(value)}")

    def _write_dict(
        self, d: dict, force_inline=lambda k: False, compact=lambda k: False
    ) -> None:
        self._logger.write(self.decorate("start", type="dict"))
        self._logger._indent()
        inline = self._default_inline(d) or force_inline(self.full_current_path())
        inlining = inline
        compacting = compact(self.full_current_path())
        for key, item in d.items():
            self._logger._current_path.append(key)
            first = key == list(d.keys())[0]
            last = key == list(d.keys())[-1]
            if first:
                inlining = True
            if not inlining:
                self._logger._new_line(" ")
            if not inline and not compacting:
                self._logger.write(self.decorate("item"))
            self._logger.write(self.decorate("key"))
            if not compacting:
                self._logger.write(" ")
            self._write_value(item, force_inline=force_inline, compact=compact)
            if not last:
                self._logger.write(self.decorate("comma"))
                if not compacting:
                    self._logger.write(" ")
            self._logger._current_path.pop()
            inlining = inline
        self._logger.write(self.decorate("end", type="dict"))
        self._logger._dindent()

    def _write_list(
        self, l: list, force_inline=lambda k: False, compact=lambda k: False
    ) -> None:
        self._logger.write(self.decorate("start", type="list"))
        self._logger._indent()
        inline = self._default_inline(l) or force_inline(self.full_current_path())
        inlining = inline
        compacting = compact(self.full_current_path())
        for i, item in enumerate(l):
            self._logger._current_path.append(i)
            first = i == 0
            last = i == len(l) - 1
            if first:
                inlining = True
            if not inlining:
                self._logger._new_line(" ")
            if not inline and not compacting:
                self._logger.write(self.decorate("item"))
            self._write_value(item, force_inline=force_inline, compact=compact)
            if not last:
                self._logger.write(self.decorate("comma"))
                if not compacting:
                    self._logger.write(" ")
            self._logger._current_path.pop()
            inlining = inline
        self._logger.write(self.decorate("end", type="list"))
        self._logger._dindent()

    def _write_value(
        self, v: any, force_inline=lambda k: False, compact=lambda k: False
    ) -> None:
        from src.engine.config import Config as Config
        from src.engine.cli import CliArgument

        if isinstance(v, dict):
            self._write_dict(v, force_inline=force_inline, compact=compact)
        elif isinstance(v, list):
            self._write_list(v, force_inline=force_inline, compact=compact)
        elif isinstance(v, Config):
            self._write_dict(v.to_dict(), force_inline=force_inline, compact=compact)
        elif isinstance(v, CliArgument):
            self._write_dict(v.to_dict(), force_inline=force_inline, compact=compact)
        else:
            self._logger.write(self.decorate_value(v))


class Logger:

    def __init__(
        self,
        name="default",
        create_config_dict: dict = {},
        stream: TextIO = sys.stdout,
    ):
        self._name = name
        self._data_printer = DataPrinter(self)
        from src.utils import deep_merge_dicts

        if name == "default":
            self._config_dict = _default_config
        else:
            self._config_dict = _loggers["default"].get_config().to_dict()
        deep_merge_dicts(self._config_dict, create_config_dict)
        self._stream = stream
        self._config = None
        # Default logger config will be loaded after init
        if name != "default":
            self.load_config()

    def get_config_name(self) -> str:
        return f"logger-{self._name}"

    def load_config(self):
        if self._config is not None:
            raise RuntimeError("Logger config already loaded.")
        from src.engine.config import get as Config

        self._config = Config().create(
            self.get_config_name(), config_dict=self._config_dict
        )

    def get_config(self):
        return self._config

    def _dbg(self, *args, enabled=True) -> None:
        if enabled:
            print(*args)  # use default print function for internal debug

    def print(self, *args, **kwargs) -> None:
        if "end" not in kwargs:
            args = [*args, "\n"]
        else:
            args = [*args, kwargs["end"]]
            del kwargs["end"]
        self.write(*args, **kwargs)

    def error(self, *args, **kwargs) -> None:
        args = [f"/;_cross/cr;/ ", *args]
        self.print(*args, **kwargs)

    def critical(self, *args, **kwargs) -> None:
        args = [f"/;cr;bo//;_cross/;/ ", *args, "/;"]
        self.print(*args, **kwargs)

    def success(self, *args, **kwargs) -> None:
        args = [f"/;_check/cg;/ ", *args]
        self.print(*args, **kwargs)

    def prompt(self, *args, **kwargs) -> None:
        args = [f"/;_arrow/cb;bo;/ ", *args]
        self.print(*args, **kwargs)

    def debug(self, *args, **kwargs) -> None:
        args = [f"/;cm;bo//;_wrench/;/ ", *args, "/;"]
        self.print(*args, **kwargs)

    def clean_lines(self, lines: int = 1):
        while lines > 0:
            lines -= 1
            self._stream.write("\x1b[F\x1b[K")
        self._stream.flush()

    _safe_get_config = lambda self, key: (
        glom(self._config_dict, key) if self._config is None else self._config.get(key)
    )

    _indents: list[str] = [""]
    _indents_buffer: TextIO = StringIO()
    _print_indents_char: bool = False
    _wkwargs: dict = None
    _current_path: list[str | int] = ["root"]

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
            if self._print_indents_char:
                self._stream.write(indents_char)
            else:
                self._stream.write(indent_char * len(indents_char))
        elif len(self._indents[0]) > 0:
            raise RuntimeError(
                "Logger internal error: _indents stack corrupted (len > 1 with non-empty base)"
            )
        self._indents_buffer.seek(0)
        self._indents_buffer.truncate(0)
        self._indents_buffer.write(indents_char)

    def write(self, *args, **kwargs) -> None:

        animate = self._safe_get_config("animate")
        flush_rate = self._safe_get_config("flush_rate")

        def_kwargs = self._wkwargs is None
        def_stream = None
        if def_kwargs:
            self._wkwargs = kwargs.copy()
            self._indents = [""]
            self._current_path = ["root"]

            if "stream" in self._wkwargs.keys():
                def_stream = self._stream
                self._stream = self._wkwargs["stream"]

        instant = self._wkwargs.get("instant", kwargs.get("instant", False))
        force_inline = self._wkwargs.get(
            "force_inline", kwargs.get("force_inline", lambda k: False)
        )
        compact = self._wkwargs.get("compact", kwargs.get("compact", lambda k: False))
        process_ansi = self._wkwargs.get("ansi", kwargs.get("ansi", True))
        verbose_only = self._wkwargs.get(
            "verbose_only", kwargs.get("verbose_only", False)
        )

        if verbose_only and not self._safe_get_config("verbose"):
            return

        for arg in args:
            if not isinstance(arg, str):
                self._data_printer._write_value(
                    arg, force_inline=force_inline, compact=compact
                )
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
                                f"Pattern recursion limit exceeded. You may have an kraken growing in {remaining[0:100]}!"
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

                    # Check instant or no animation mode
                    if instant or not animate:
                        continue

                    # Flush based on flush rate
                    if len(remaining) == 0:
                        self._stream.flush()
                        continue
                    mod = max(1, random.randint(flush_rate[0], flush_rate[1]))
                    if len(remaining) % mod == 0:
                        self._stream.flush()
                        sleep(random.uniform(0.01, 0.03))

        if def_kwargs:
            self._stream.flush()
            self._indents = [""]
            self._wkwargs = None
            if def_stream is not None:
                self._stream = def_stream


_loggers: dict[str, Logger] = None


def init():
    global _loggers
    _loggers = {"default": Logger(name="default", stream=sys.stdout)}


def get(
    name: str = "default",
    stream: TextIO = None,
    create_config_dict: dict = None,
) -> Logger:
    """Get or create a logger by name."""
    global _loggers

    if not name in _loggers:
        if stream is None:
            raise RuntimeError(f"Provide stream to create logger.")
        _loggers[name] = Logger(
            name=name,
            stream=stream,
            create_config_dict=(
                create_config_dict if create_config_dict is not None else {}
            ),
        )
    else:
        import src.engine.config as Config

        if create_config_dict is not None:
            _loggers[name].get_config().reload(
                trust="dict", config_dict=create_config_dict
            )
        if stream is not None:
            _loggers[name]._stream = stream
    return _loggers[name]
