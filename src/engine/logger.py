# ============================================================
# ANSI Logging Utility
# ============================================================
from io import StringIO
import random
import re
import sys
from time import sleep
from typing import TextIO, Tuple
import pprint
from glom import glom

ANSI_CODES = {
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
    "da": [2],  # dim
}

ANSI_STYLES = {
    # reset
    "r": ["r"],
    "res": ["r"],
    # logging
    "err": ["cr", "bo"],
    "prt": ["cw", "da"],
    "suc": ["cg", "bo"],
    "dbg": ["cg", "bo"],
}

ANSI_STYLES_CODES = {
    key: [ANSI_CODES[code][0] for code in codes] for key, codes in ANSI_STYLES.items()
}

_ANSI_CODES = {
    **ANSI_CODES,
    **ANSI_STYLES_CODES,
}

# Markers and pattern /;pattern/
_ANSI_MARK = "/;"
_S_END_MARK = _ANSI_MARK[::-1]
_ansi_pattern = (
    lambda tag: f"{_ANSI_MARK}{tag}{_S_END_MARK if tag.split('/')[0] in _s_keys_matches.keys() else _ANSI_MARK[0]}"
)
# Specials: /;pattern/args;/
_specials = {
    "__kraken/;/": lambda *args: f"/;__kraken// /;__kraken//",
    "_repeat/c;i;/": lambda *args: f"{args[0]*max(1,int(args[1]))}",
    "_cross/s;;/": lambda *args: f"✗",
    "_check/s;;/": lambda *args: f"✓" if not args[0] else f"/;{';'.join(args)}/✓/;",
    "_arrow/s;;/": lambda *args: "→" if not args[0] else f"/;{';'.join(args)}/→/;",
    "_farrow/s;;/": lambda *args: f"↳",
}
_s_keys_matches = dict([(key.split("/")[0], val) for key, val in _specials.items()])
_ansi_text = lambda codes: f"\033[{';'.join(str(c) for c in codes)}m"


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
    tags = _s_keys_matches.keys() | ANSI_STYLES_CODES.keys() | ANSI_CODES.keys()
    for tag in tags:
        if hit:
            break
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
        elif tag not in ANSI_CODES.keys():
            # consider it a single reset tag '/;'
            return (_ANSI_MARK, _ansi_text(_ANSI_CODES["r"]))
        # Compose shortcuts
        else:
            ansi_codes.extend(ANSI_CODES[tag])
        # End on trailing mark
        if f"{tag}/" in lookahead + "/":
            return (_ansi_pattern(lookahead), _ansi_text(ansi_codes))
    # Strict trailing mark
    raise SyntaxError(
        f"Invalid pattern in: {lookahead_error()}. Hit {_ansi_pattern(lookahead)} with missing trailing '/'"
    )


_default_config = {
    "animate": False,
    "slow_mode": False,
    "flush_rate": [0, 0],
    "strict_logging": False,
    "styles": {
        "sep": "cw;da",
        "obji": "cb;da",
        "objk": "cg;bo",
        "arri": "cb;da",
        "str": "cw;it",
        "bool": "cc",
        "num": "cb",
    },
}


class Logger:

    _pprint = lambda self, v: re.sub(r"[\s']+", "", pprint.pformat(v, compact=True))
    _lpprint = lambda self, v: len(self._pprint(v))

    _indents: list[str] = [""]
    _indent_mode: bool = False

    _max_inline = 120
    _config_fallback: dict = _default_config

    def __init__(
        self,
        name="default",
        create_config_dict: dict = _default_config,
        stream: TextIO = sys.stdout,
    ):
        self._name = name
        from src.utils import deep_merge_dicts

        self._config_dict = _default_config
        deep_merge_dicts(self._config_dict, create_config_dict)
        self._stream = stream
        # default logger is not tied to a condfiguration.
        if name == "default":
            self._config = None  # will need to be initialized. required for boot
        else:
            self.init_config()

    def init_config(self) -> None:

        # Avoid circular import
        from src.engine.config import get_config as Config

        self._config = Config(
            self._name,
            self._config_dict,
            load_from_file=True,
        )

    # call to default print
    def _dbg(self, *args, enabled=True) -> None:
        if enabled:
            print(*args)

    def print(self, *args, **kwargs) -> None:
        args = [*args, "\n"]
        self.write(*args, **kwargs)

    def error(self, *args, **kwargs) -> None:
        args = [f"/;cr//;err//;r/", *args, "\n"]
        self.write(*args, **kwargs)

    def success(self, *args, **kwargs) -> None:
        args = [f"/;cg//;suc//;r/", *args]
        self.write(*args, **kwargs)

    def prompt(self, *args, **kwargs) -> None:
        args = [f"/;cb//;prt//;r/", *args]
        self.write(*args, **kwargs)

    def debug(self, *args, **kwargs) -> None:
        args = [f"/;cy//;dbg//;r/", *args]
        self.write(*args, **kwargs)

    def clean_lines(self, instant=True, lines: int = 1):
        while lines > 0:
            lines -= 1
            self._stream.write("\033[F\033[K")
            if instant:
                self._stream.flush()

    _safe_get_config = lambda self, key: (
        glom(self._config_dict, key) if self._config is None else self._config.get(key)
    )

    _decorators_cache = {}
    _update_decorators_cache = lambda self: None
    _decorator = lambda self, key: self._safe_get_config(f"styles.{key}")

    def update_decorators_cache(self):

        self._decorators_cache = {
            key: self._safe_get_config(f"styles.{key}")
            for key in self._safe_get_config("styles").keys()
        }

    # decorators for printing structures
    _psep = lambda self, c: f"/;{self._decorator('sep')}/{c}/;"
    _pobji = lambda self, key: f" /;/;_arrow/{self._decorator('obji')};//; "
    _pobjk = (
        lambda self, key: f"/;/;{self._decorator('objk')}/{key}/;/;{self._decorator('sep')}/:/;"
    )
    _parri = lambda self, i: f" /;/;{self._decorator('arri')}/{str(i)}/; "
    _pval = lambda self, v: (
        f"/;/;{self._decorator('bool')}/{str(v)}/;"
        if isinstance(v, bool)
        else (
            f"/;/;{self._decorator('num')}/{str(v)}/;"
            if isinstance(v, int) or isinstance(v, float)
            else f"/;/;{self._decorator('str')}/'{str(v)}'/;"
        )
    )
    _indents_buffer: TextIO = StringIO()

    def _indent(self) -> None:
        indents_char = self._indents_buffer.getvalue()
        indents_char = re.sub(r"\x1b\[[0-9;]*m", "", indents_char)
        self._indents.append(indents_char)

    def _dindent(self) -> None:
        self._indents.pop()

    _print_indents_char: bool = False

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

    def _write_dict(self, d: dict, force_inline=False) -> None:
        self.write(self._psep("{"))
        self._indent()
        inline = len(self._indents[-1]) + self._lpprint(d) < self._max_inline
        if force_inline:
            inline = True
        inlining = inline
        for key, item in d.items():
            first = key == list(d.keys())[0]
            last = key == list(d.keys())[-1]
            if first:
                inlining = True
            if not inlining:
                self._new_line(" ")
            if not inline:
                self.write(self._pobji(key))
            self.write(self._pobjk(key))
            if not self._wkwargs.get("compact", False):
                self.write(" ")
            self._write_value(item, force_inline=inline)
            if not last:
                self.write(self._psep(","))
                if not self._wkwargs.get("compact", False):
                    self.write(" ")
            inlining = inline
        self.write(self._psep("}"))
        self._dindent()

    def _write_list(self, l: list, force_inline=False) -> None:
        self.write(self._psep("["))
        self._indent()
        inline = len(self._indents[-1]) + self._lpprint(l) < self._max_inline
        if force_inline:
            inline = True
        inlining = inline
        for i, item in enumerate(l):
            first = i == 0
            last = i == len(l) - 1
            if first:
                inlining = True
            if not inlining:
                self._new_line(" ")
            if not inline:
                self.write(self._parri(i))
            self._write_value(item, force_inline=force_inline)
            if not last:
                self.write(self._psep(","))
                if not self._wkwargs.get("compact", False):
                    self.write(" ")
            inlining = inline
        self.write(self._psep("]"))
        self._dindent()

    def _write_value(self, v: any, force_inline=False) -> None:
        if isinstance(v, dict):
            self._write_dict(v, force_inline=force_inline)
        elif isinstance(v, list):
            self._write_list(v, force_inline=force_inline)
        else:
            self.write(self._pval(v))

    _wkwargs = None

    def write(self, *args, **kwargs) -> None:

        animate = self._safe_get_config("animate")
        slow_mode = self._safe_get_config("slow_mode")
        flush_rate = self._safe_get_config("flush_rate")

        def_kwargs = self._wkwargs is None
        if def_kwargs:
            self._wkwargs = kwargs.copy()
            self._indents = [""]

        instant = self._wkwargs.get("instant", kwargs.get("instant", False))
        force_inline = self._wkwargs.get(
            "force_inline", kwargs.get("force_inline", False)
        )
        if def_kwargs and instant:
            self._dbg("Instant Logger.write started", enabled=True)

        for arg in args:
            if isinstance(arg, dict):
                self._write_dict(arg, force_inline=force_inline)
            elif isinstance(arg, list):
                self._write_list(arg, force_inline=force_inline)
            else:
                if not isinstance(arg, str):
                    if self._config.get("strict_logging", False):
                        raise RuntimeError(
                            f"Logger.write() only supports str, dict, and list types. Got {type(arg)} instead."
                        )
                    self.write(f"/;_cross/cr;/ Invalid log type /;cr/{type(arg)}/;")
                    continue
                remaining = arg
                security_limit = len(remaining) + 10000
                while remaining:
                    # Mange ANSI patterns on the fly
                    lookahead = remaining[0:2]
                    if lookahead == _ANSI_MARK:
                        ansi = _detect_ansi_pattern(remaining)
                        remaining = ansi[1] + remaining[len(ansi[0]) :]
                        # Do not let the kraken grow...
                        if len(remaining) > security_limit:
                            raise RuntimeError(
                                f"Pattern recursion limit exceeded. You may have an overflowing recursive pattern!"
                            )
                        # Continue to provide recursive patterns
                        continue
                    char = remaining[0]
                    remaining = remaining[1:]
                    if char == "\n":
                        self._new_line(" ")
                        continue
                    self._stream.write(char)
                    self._indents_buffer.write(char)
                    if char == " " or not animate or instant:
                        continue
                    if len(remaining) == 0:
                        self._stream.flush()
                        continue
                    mod = max(1, random.randint(flush_rate[0], flush_rate[1]))
                    if slow_mode:
                        mod = max(1, mod // 2)
                    if len(remaining) % mod == 0:
                        self._stream.flush()
                        sleep(random.uniform(0.02, 0.04 if slow_mode else 0.01))

        if def_kwargs:
            if instant:
                self._dbg("Instant Logger.write completed", enabled=True)
            reset_style = self._wkwargs.get(
                "reset_style", kwargs.get("reset_style", True)
            )
            if reset_style:
                self.write("/;")
            self._stream.flush()
            self._indents = [""]
            self._wkwargs = None


_loggers: dict[str, Logger] = None


def init_logging():
    global _loggers
    _loggers = {"default": Logger(name="default")}


def get_logger(
    name: str = "logger",
    stream: TextIO = sys.stdout,
    create_config_dict: dict = _default_config,
) -> Logger:
    """Get or create a logger by name."""
    global _loggers

    if not name in _loggers:
        _loggers[name] = Logger(
            name=name,
            stream=stream,
            create_config_dict=create_config_dict,
        )
        _loggers[name].write(f"Logger '{name}' by {__name__}: ")
        _loggers[name].print(
            {
                key: value
                for key, value in _loggers[name]._config._config_dict.items()
                if key not in ["styles"]
            },
            force_inline=True,
            compact=True,
        )
    return _loggers[name]
