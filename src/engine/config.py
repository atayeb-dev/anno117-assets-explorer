import json
from pathlib import Path
import re

from glom import glom

from src.engine.logger import get_logger as Logger
from src.utils import deep_merge_dicts

_global_config: GlobalConfig = None
_default_logger: Logger = None
_config_logger: Logger = None

_default_config_file = "config.json"
_file_pattern = lambda prefix: f"{prefix}-{_default_config_file}".removeprefix("-")


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
            f"Loaded config from {(Path.cwd() / path).relative_to(Path.cwd())}\n"
        )
        return config
    except Exception as e:
        _config_logger.error(f"No config located at: {path}")
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


class Config:

    _name: str
    _config_dict: dict

    def __init__(
        self,
        name: str,
        config_dict: dict,
        load_from_file: bool = True,
    ):
        self._name = re.sub(r"[.-]", "_", name.strip())
        self.reload(config_dict, load_from_file)

    def reload(
        self,
        config_dict: dict = None,
        load_from_file: bool = True,
    ):
        global _global_config
        global _config_logger
        if config_dict is None:
            config_dict = self._config_dict
        self._config_dict = config_dict.copy()
        merges = []
        if load_from_file:
            _config_logger.print(f"Reloading config '{self._name}' from file")
            merges.append(self._config_dict.copy())
            if self._name in _global_config._config_dict.keys():
                merges.append(_global_config._config_dict[self._name].copy())
            merges.append(_read_config_from_file(_file_pattern(self._name)))
        else:
            _config_logger.print(f"Reloading config '{self._name}' from dict")
            if self._name in _global_config._config_dict.keys():
                merges.append(_global_config._config_dict[self._name].copy())
            merges.append(_read_config_from_file(_file_pattern(self._name)))
            merges.append(self._config_dict.copy())
        while len(merges) > 1:
            deep_merge_dicts(merges[0], merges[1])
            merges.pop(1)
        self._config_dict = merges[0]

    def get(self, key: str, default=None) -> any | None:
        global _global_config
        """Get a configuration value by key."""
        if self is not _global_config:
            default = _global_config.get(key, default=default)
        return glom(self._config_dict, key, default=default)

    def get_path(self, key: str, default=None) -> Path:
        return Path(Path.cwd() / self.get(f"paths.{key}", default=""))

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

    def print(self) -> str:
        """Print the current configuration."""
        Logger(self.get("logger")).print(self._config_dict)

    def dump(self) -> None:
        """Dump the current configuration to a file."""
        _write_config_to_file(_file_pattern(self._name), self._config_dict)

    def merge_in_global(self) -> None:
        """Merge global config into this config."""
        deep_merge_dicts(self._global_config._config[self._name], self._config_dict)


class GlobalConfig(Config):
    _config_dict = None
    _cached_configs: dict[str, Config] = {}

    def __init__(self):
        self._name = "global_config"
        try:
            self._config_dict = _silent_read_config_from_file(_default_config_file)
            _default_logger.success(f"Loaded global config\n")
        except FileNotFoundError:
            _default_logger.error(
                f"No global config file found at {_default_config_file}"
            )
        except Exception as e:
            _default_logger.error(f"Failed to initialize global config: {e}")
        if self._config_dict is None:
            self._config_dict = {}

    def get_cached_config(
        self,
        name: str = "",
        config_dict: dict = {},
        load_from_file=True,
    ) -> Config:
        if not name:
            return self
        if name not in self._cached_configs:
            self._cached_configs[name] = Config(
                name, config_dict, load_from_file=load_from_file
            )
        return self._cached_configs[name]

    def print_config(self, name: str = "", force_inline: bool = False) -> None:
        global _config_logger
        if not name:
            _config_logger.print(self._config_dict, force_inline=force_inline)
            return
        if name not in self._cached_configs:
            _config_logger.error(f"Config '{name}' not found in global.")
        else:
            _config_logger.print(
                self._cached_configs[name]._config_dict, force_inline=force_inline
            )
            if self.get(name) is None:
                _config_logger.error(f"Config '{name}' not saved in global.")


def init_config():
    global _global_config
    global _default_logger
    global _config_logger

    # Keep default loader we may need it.
    _default_logger = Logger("default")

    # Use the default logger during load
    _config_logger = _default_logger

    # Load the beast.
    _global_config = GlobalConfig()

    # Create logger configuration from logging's default and swap logger.
    _config_logger = Logger(create_config_dict=_default_logger._config_dict.copy())


def get_config(prefix: str = "", config_dict: dict = {}, load_from_file=True) -> Config:
    global _global_config
    return _global_config.get_cached_config(
        prefix, config_dict, load_from_file=load_from_file
    )


def print_config(name: str = "", force_inline: bool = False) -> None:
    global _global_config
    _global_config.print_config(name, force_inline=force_inline)
