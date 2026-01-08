import json
from pathlib import Path
import re

from glom import glom

from src.engine.cli import CliModule
import src.engine.logger as Logger
from src.utils import deep_merge_dicts, ensure_nested_path
import copy

_global_config: GlobalConfig = None
_default_logger: Logger.Logger = None
_config_logger: Logger.Logger = None

_global_config_file_path = Path.cwd() / "config.json"
_config_file_path = (
    lambda file_prefix: Path.cwd() / "config" / f"{file_prefix}-config.json"
)


def _read_config_from_file(read_path: Path) -> dict:
    global _config_logger
    try:
        if not read_path or not read_path.is_file():
            _config_logger.error(
                f"Path: {read_path} is not a file.",
                verbose_only=True,
            )
        else:
            with open(read_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            _config_logger.success(
                f"Loaded config from {read_path.absolute()}", verbose_only=True
            )
            return config
    except Exception as e:
        _config_logger.error(
            f"Failed to load config file: {read_path.absolute()}: {e}",
            verbose_only=True,
        )
    return {}


def _write_config_to_file(write_path: Path, config: dict):
    global _config_logger
    try:
        """Dump the current configuration to a file."""
        write_path.parent.mkdir(parents=True, exist_ok=True)
        with open(write_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception:
        _config_logger.error(f"Failed to write config file: {write_path.absolute()}")


def _update_config(_config: Config, trust="File", config_dict: dict = {}) -> dict:
    global _global_config
    config_file = _read_config_from_file(_config._config_file)
    _global_config_dict = _glom_get(
        copy.deepcopy(_global_config._config_dict), _config._key
    )

    merges = [
        copy.deepcopy(
            _config._config_dict
            if _config._config_dict
            else _config._initial_config_dict
        ),
    ]
    if trust == "file":
        merges.append(copy.deepcopy(config_dict))
        merges.append(_global_config_dict)
        merges.append(config_file)
    elif trust == "dict":
        merges.append(_global_config_dict)
        merges.append(config_file)
        merges.append(copy.deepcopy(config_dict))
    else:
        raise RuntimeError(f"Unknown trust source: {trust}")
    while len(merges) > 1:
        deep_merge_dicts(merges[0], merges[1])
        merges.pop(1)
    return merges[0]


def _glom_get(d: dict, path: str, default={}):
    return glom(d, path, default=default)


class ConfigError(Exception):
    pass


class Config:

    def __init__(
        self,
        key: str,
        trust: str = "file",
        config_dict: dict = {},
    ):
        global _config_logger

        self._key = key
        self._initial_config_dict = copy.deepcopy(config_dict)
        self._module_config_dict = {}

        self.nested = "." in key
        self.specify_file_path(reload=False)
        self._config_dict = {}
        self.reload(trust=trust, config_dict=config_dict)
        _config_logger.success(f"Config '{self._key}' initialized.", verbose_only=True)

    def specify_file_path(self, new_path: str | Path = "", reload: bool = True) -> None:
        if new_path == "":
            self._config_file = (
                None
                if self.nested
                else _config_file_path(re.sub(r"[.]", "-", self._key.strip()))
            )
        else:
            self._config_file = Path.cwd() / new_path
        if reload:
            self.reload()

    def reload_for_module(self, module: CliModule | None = None):
        if not self.nested:
            raise ConfigError("Cannot reload config for module when key is not nested.")
        unload = module is None
        if unload:
            self.specify_file_path()
            _config_logger.debug(
                f"Module config for '{self._key}' unloaded.", verbose_only=True
            )
        else:
            self.specify_file_path(
                _global_config.get(module.get_config_name())._config_file
            )
            _config_logger.debug(
                f"Config '{self._key}' reloaded for module '{module.get_config_name()}'.",
                verbose_only=True,
            )

    def reload(
        self,
        trust: str = "file",
        config_dict: dict = {},
    ):
        self._config_dict = _update_config(self, trust=trust, config_dict=config_dict)

    def get(self, key: str = "", default=None) -> any | None:
        if key == "":
            return copy.deepcopy(self._config_dict)
        return _glom_get(copy.deepcopy(self._config_dict), key, default=default)

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
        _write_config_to_file(self._config_file, self._config_dict)
        _config_logger.success(f"Config {self._key} dumped to '{self._config_file}'.")

    def delete_file(self) -> None:
        """Delete the configuration file."""
        global _config_logger
        config_path = self._config_file
        if config_path.is_file():
            config_path.unlink()
            _config_logger.success(f"Config file '{config_path.absolute()}' deleted.")
        else:
            _config_logger.error(
                f"Failed to delete config file: '{config_path.absolute()}'."
            )

    def merge(self) -> None:
        """Merge global config into this config."""
        global _config_logger
        global _global_config
        if _glom_get(_global_config._config_dict, self._key, default=None) is None:
            ensure_nested_path(_global_config._config_dict, self._key)
        deep_merge_dicts(
            _glom_get(_global_config._config_dict, self._key, default=None),
            self._config_dict,
        )
        _config_logger.success(f"Config {self._key} merged in global.")

    def to_dict(self) -> dict:
        return copy.deepcopy(self._config_dict)


class GlobalConfig:
    _config_dict = None
    _cached_configs: dict[str, Config] = {}

    def __init__(self):
        self._config_dict = _read_config_from_file(_global_config_file_path)
        # try:
        #     self._config_dict = _silent_read_config_from_file(_global_config_file_path)
        #     _config_logger.success(
        #         f"Loaded global config from {_global_config_file_path}",
        #         verbose_only=True,
        #     )
        # except FileNotFoundError:
        #     _config_logger.error(
        #         f"No global config file found at {_global_config_file_path}",
        #         verbose_only=True,
        #     )
        # except Exception as e:
        #     _config_logger.error(
        #         f"Failed to initialize global config: {e}", verbose_only=True
        #     )
        # if self._config_dict is None:
        #     self._config_dict = {}

    def create(
        self,
        key: str = "",
        config_dict: dict = {},
        trust: str = "file",
    ) -> Config:
        if not key or key in self._cached_configs:
            raise ConfigError("Config key must be unique and non-empty.")

        self._cached_configs[key] = Config(key, config_dict=config_dict, trust=trust)
        return self._cached_configs[key]

    def get(self, key: str) -> Config | dict:
        if key not in self._cached_configs:
            raise ConfigError(f"Config '{key}' not found in global.")
        return self._cached_configs[key]

    def reload_for_module(self, module: CliModule | None = None) -> None:
        for cfg in self._cached_configs.values():
            if cfg.nested:
                cfg.reload_for_module(module)

    def dump(self, key: str = "") -> None:
        global _config_logger
        if not key:
            _write_config_to_file(_global_config_file_path, self._config_dict)
            _config_logger.success(
                f"Global config dumped to '{_global_config_file_path}'."
            )
            return
        if key not in self._cached_configs:
            _config_logger.error(f"Config '{key}' not found in global.")
        else:
            self._cached_configs[key].dump()

    def merge(self, key: str = "") -> None:
        global _config_logger
        if not key:
            for cfg in self._cached_configs.values():
                cfg.merge()
            _config_logger.success(f"Global config merged from cached configs.")
            return
        if key not in self._cached_configs:
            _config_logger.error(f"Config '{key}' not found in global.")
        else:
            self._cached_configs[key].merge()


def init_global():
    global _global_config
    global _default_logger
    global _config_logger

    # Keep default loader we may need it.
    _default_logger = Logger.get()

    # Use the default logger for initialization.
    _config_logger = _default_logger

    # Load the beast.
    _global_config = GlobalConfig()


def init_logger():
    global _config_logger
    _config_logger = Logger.get("config")


def get(name: str = "") -> Config | GlobalConfig:
    global _global_config
    return _global_config if name == "" else _global_config.get(name)
