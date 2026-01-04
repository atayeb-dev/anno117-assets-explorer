import json
from pathlib import Path
import re

from glom import glom

import src.engine.logger as Logger
from src.utils import deep_merge_dicts

_global_config: GlobalConfig = None
_default_logger: Logger.Logger = None
_config_logger: Logger.Logger = None

_default_config_file = "config.json"
_file_pattern = lambda prefix: f"config/{prefix}-{_default_config_file}"


def _silent_read_config_from_file(path: str | Path) -> dict:

    read_path = Path.cwd() / path
    with open(read_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config


def _read_config_from_file(path: str | Path) -> dict:
    global _config_logger
    try:
        config = _silent_read_config_from_file(path)
        _config_logger.success(
            f"Loaded config from {(Path.cwd() / path).relative_to(Path.cwd())}"
        )
        return config
    except Exception as e:
        pass
    return {}


def _write_config_to_file(path: str | Path, config: dict, silent=False) -> Path:
    global _config_logger
    try:
        write_path = Path(path)
        """Dump the current configuration to a file."""
        with open(write_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception:
        if not silent:
            _config_logger.error(f"Failed to write config to {write_path.absolute()}")
        pass
    return {}


def _update_config(_config: Config, trust="File", config_dict: dict = {}) -> dict:
    global _global_config

    config_file = _read_config_from_file(_file_pattern(_config._name))
    _global_config_dict = _glom_get(
        _global_config._config_dict.copy(), _config._name
    ).copy()

    merges = [_config._initial_config_dict.copy()]
    if trust == "file":
        merges.append(config_dict.copy())
        merges.append(_global_config_dict)
        merges.append(config_file)
    elif trust == "dict":
        merges.append(_global_config_dict)
        merges.append(config_file)
        merges.append(config_dict.copy())
    else:
        raise RuntimeError(f"Unknown trust source: {trust}")
    while len(merges) > 1:
        deep_merge_dicts(merges[0], merges[1])
        merges.pop(1)
    return merges[0]


def _glom_get(d: dict, path: str, default={}):
    return glom(d, path, default=default)


class Config:

    _name: str
    _initial_config_dict: dict
    _config_dict: dict

    def __init__(
        self,
        name: str,
        trust: str = "file",
        config_dict: dict = {},
    ):
        global _config_logger
        self._name = re.sub(r"[.-]", "_", name.strip())
        self._initial_config_dict = config_dict.copy()
        self.reload(trust=trust, config_dict=config_dict)
        _config_logger.success(f"Config '{self._name}' initialized.")

    def reload(
        self,
        trust: str = "file",
        config_dict: dict = {},
    ):
        self._config_dict = _update_config(self, trust=trust, config_dict=config_dict)

    def get(self, key: str = "", default=None) -> any | None:
        if key == "":
            return self._config_dict.copy()
        return _glom_get(self._config_dict.copy(), key, default=default)

    def get_path(self, key: str) -> Path:
        return Path(Path.cwd() / self.get(f"paths.{key}", ""))

    def validate(self, key: str, dir=False) -> Path:
        path = self.get_path(key, default=None)
        if path is None:
            raise FileNotFoundError("Select a file")
        if dir:
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
        else:
            if not path.exists() or not path.is_file():
                raise FileNotFoundError("Select a file")
        return path

    def dump(self) -> None:
        """Dump the current configuration to a file."""
        global _config_logger
        _write_config_to_file(_file_pattern(self._name), self._config_dict)
        _config_logger.success(
            f"Config {self._name} dumped to '{_file_pattern(self._name)}'."
        )

    def merge(self) -> None:
        """Merge global config into this config."""
        global _config_logger
        global _global_config
        if self._name not in _global_config._config_dict:
            _global_config._config_dict[self._name] = {}
        deep_merge_dicts(_global_config._config_dict[self._name], self._config_dict)
        _config_logger.success(f"Config {self._name} merged in global.")

    def to_dict(self) -> dict:
        return self._config_dict.copy()


class GlobalConfig:
    _config_dict = None
    _cached_configs: dict[str, Config] = {}

    def __init__(self):
        self._name = "global_config"
        try:
            self._config_dict = _silent_read_config_from_file(_default_config_file)
            _default_logger.success(f"Loaded global config from {_default_config_file}")
        except FileNotFoundError:
            _default_logger.error(
                f"No global config file found at {_default_config_file}"
            )
        except Exception as e:
            _default_logger.error(f"Failed to initialize global config: {e}")
        if self._config_dict is None:
            self._config_dict = {}

    def create(
        self,
        name: str = "",
        config_dict: dict = {},
        trust: str = "file",
    ) -> Config:
        if not name or name in self._cached_configs:
            raise RuntimeError("Config name must be unique and non-empty.")
        self._cached_configs[name] = Config(name, config_dict=config_dict, trust=trust)
        return self._cached_configs[name]

    def get(self, name: str = "") -> Config | dict:
        if name == "":
            return self._config_dict.copy()
        if name not in self._cached_configs:
            raise RuntimeError(f"Config '{name}' not found in global.")
        return self._cached_configs[name]

    def dump(self, name: str = "") -> None:
        global _config_logger
        if not name:
            _write_config_to_file(_default_config_file, self._config_dict)
            _config_logger.success(f"Global config dumped to '{_default_config_file}'.")
            return
        if name not in self._cached_configs:
            _config_logger.error(f"Config '{name}' not found in global.")
        else:
            self._cached_configs[name].dump()

    def merge(self, name: str = "") -> None:
        global _config_logger
        if not name:
            for cfg in self._cached_configs.values():
                cfg.merge()
            _config_logger.success(f"Global config merged from cached configs.")
            return
        if name not in self._cached_configs:
            _config_logger.error(f"Config '{name}' not found in global.")
        else:
            self._cached_configs[name].dump()


def init():
    global _global_config
    global _default_logger
    global _config_logger

    # Keep default loader we may need it.
    _default_logger = Logger.get("default")

    # Use the default logger during load
    _config_logger = _default_logger

    # Load the beast.
    _global_config = GlobalConfig()

    # Create logger configuration from logging's default and swap logger.
    _config_logger = Logger.get(create_config_dict=_default_logger._config_dict.copy())


def get(name: str = "") -> Config | GlobalConfig:
    global _global_config
    return _global_config if name == "" else _global_config.get(name)
