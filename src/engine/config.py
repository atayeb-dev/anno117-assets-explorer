import copy
import json
from pathlib import Path
import re

from glom import glom

from src.engine.cli import CliModule
import src.engine.logger as Logger
import src.utils as Utils

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


def _dump_config_to_file(write_path: Path, config: dict):
    global _config_logger
    write_config = Utils.deep_merge_dicts(_read_config_from_file(write_path), config)
    try:
        """Dump the current configuration to a file."""
        write_path.parent.mkdir(parents=True, exist_ok=True)
        with open(write_path, "w", encoding="utf-8") as f:
            json.dump(write_config, f, indent=4)
    except Exception:
        _config_logger.error(f"Failed to write config file: {write_path.absolute()}")


class ConfigError(Exception):
    pass


from typing import Literal


class Config:

    def __init__(
        self,
        key: str,
        trust: Literal["file", "dict"] = "file",
        config_dict: dict = {},
    ):
        global _config_logger

        self._key = key
        _config_logger.debug(f"Creating '{self._key}'.", verbose_only=True)

        self._merged_config_dict = {}
        self._specific_config_dict = {}

        self.nested = "." in key
        self.specify_file_path(reload=False)
        self.reload(trust=trust, config_dict=config_dict)
        _config_logger.success(f"Config '{self._key}' initialized.", verbose_only=True)

    def _update(
        self,
        trust: Literal["file", "dict"] = "file",
        config_dict: dict = {},
    ) -> dict:
        global _global_config

        # Copy the update config dict and current specific config dict
        update_config_dict = copy.deepcopy(config_dict)
        specific_config_dict = (
            # When trusting file, start fresh
            {}
            if trust == "file"
            else copy.deepcopy(self._specific_config_dict)
        )

        # Load both global and specific config files
        global_config_file_dict = _read_config_from_file(_global_config_file_path)
        specific_config_file_dict = _read_config_from_file(self._config_file)

        # Create the nested structure for merging
        update_config_dict = Utils.nest_dict(update_config_dict, self._key)
        specific_config_dict = Utils.nest_dict(specific_config_dict, self._key)

        # If nested, keep only the relevant sub-dict from specific config file
        if self.nested:
            specific_config_file_dict = Utils.nest_dict(
                Utils.ensure_get_dict(specific_config_file_dict, self._key), self._key
            )
        else:
            # Create the nested structure for merging
            specific_config_file_dict = Utils.nest_dict(
                specific_config_file_dict, self._key
            )
        # Extract only the relevant sub-dict from global config file keeping nesting
        global_config_file_dict = Utils.nest_dict(
            Utils.ensure_get_dict(global_config_file_dict, self._key), self._key
        )

        # Get a merged version of global and specific config files
        merged_config_file_dict = Utils.deep_merge_dicts(
            copy.deepcopy(global_config_file_dict),
            copy.deepcopy(specific_config_file_dict),
        )

        # Merge according to trust order
        if trust == "file":
            self._specific_config_dict = Utils.deep_merge_dicts(
                copy.deepcopy(update_config_dict),
                copy.deepcopy(specific_config_dict),
                copy.deepcopy(specific_config_file_dict),
            )
            self._merged_config_dict = Utils.deep_merge_dicts(
                copy.deepcopy(self._specific_config_dict),
                copy.deepcopy(merged_config_file_dict),
            )
        elif trust == "dict":
            self._specific_config_dict = Utils.deep_merge_dicts(
                copy.deepcopy(specific_config_file_dict),
                copy.deepcopy(specific_config_dict),
                copy.deepcopy(update_config_dict),
            )
            self._merged_config_dict = Utils.deep_merge_dicts(
                copy.deepcopy(merged_config_file_dict),
                copy.deepcopy(self._specific_config_dict),
            )

        # Always d-nest to keep only actual config dicts
        self._specific_config_dict = Utils.ensure_get_dict(
            self._specific_config_dict, self._key, default=None
        )
        self._merged_config_dict = Utils.ensure_get_dict(
            self._merged_config_dict, self._key, default=None
        )

        # Sanity check
        if self._specific_config_dict is None or self._merged_config_dict is None:
            raise ConfigError(f"Failed to extract config dict for key '{self._key}'.")

        _config_logger.debug(
            f">>> UPDATED {self._key} CONFIG\n",
            {
                "trust": trust,
                "config_file": self._config_file,
                "update_config_dict": update_config_dict,
                "specific_config_dict": specific_config_dict,
                "specific_config_file_dict": specific_config_file_dict,
                "global_config_file_dict": global_config_file_dict,
                "merged_config_file_dict": merged_config_file_dict,
                "self.specific_config": self._specific_config_dict,
                "self.merged_config": self._merged_config_dict,
            },
            verbose_only=True,
        )
        _config_logger.debug(f"<<< UPDATED {self._key} CONFIG", verbose_only=True)

    def specify_file_path(self, new_path: str | Path = "", reload: bool = True) -> None:
        if new_path == "":
            self._config_file = (
                None
                if self.nested
                else _config_file_path(re.sub(r"[._]", "-", self._key.strip()))
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
                _global_config.get(module.get_config_key())._config_file
            )
            _config_logger.debug(
                f"Module config for '{self._key}' loaded from '{self._config_file}'.",
                verbose_only=True,
            )

    def reload(
        self,
        trust: str = "file",
        config_dict: dict = {},
    ):
        self._update(trust=trust, config_dict=config_dict)

    def get(self, key: str = "", default=None) -> any | None:
        if key == "":
            return copy.deepcopy(self._merged_config_dict)
        return copy.deepcopy(
            Utils.ensure_get_dict(self._merged_config_dict, key, default=default)
        )

    def get_path(self, key: str) -> Path:
        return Path(Path.cwd() / self.get(f"paths.{key}", ""))

    def print(self, output: lambda *args, **kwargs: None = None) -> None:
        if output is None:
            output = _config_logger.print
        output(
            {
                self._key: {
                    "nested": self.nested,
                    "config_file": self._config_file,
                    "specific": self._specific_config_dict,
                    "merged": self._merged_config_dict,
                }
            },
        )

    def dump(self) -> None:
        """Dump the current configuration to a file."""
        if self.nested:
            _dump_config_to_file(
                self._config_file,
                Utils.nest_dict(self._specific_config_dict, self._key),
            )
        else:
            _dump_config_to_file(self._config_file, self._specific_config_dict)
        _config_logger.success(f"Config {self._key} dumped to '{self._config_file}'.")

    def delete_file(self) -> None:
        """Delete the configuration file."""
        if self.nested:
            raise ConfigError("Cannot delete config file from nested config.")
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
        global_config_target = Utils.ensure_get_dict(
            _global_config._config_dict, self._key, default=None
        )
        if global_config_target is None:
            global_config_target = Utils.ensure_nested_path(
                _global_config._config_dict, self._key
            )
        Utils.deep_merge_dicts(
            global_config_target,
            copy.deepcopy(self._specific_config_dict),
        )
        _config_logger.success(f"Config {self._key} merged in global.")

    def to_dict(self) -> dict:
        return copy.deepcopy(self._specific_config_dict)


class GlobalConfig:
    _config_dict = None
    _cached_configs: dict[str, Config] = {}

    def __init__(self):
        self._config_dict = _read_config_from_file(_global_config_file_path)

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
            _dump_config_to_file(_global_config_file_path, self._config_dict)
            _config_logger.success(
                f"Global config dumped to '{_global_config_file_path}'."
            )
            return
        if key not in self._cached_configs:
            _config_logger.error(f"Can't dump unknown config '{key}'.")
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
