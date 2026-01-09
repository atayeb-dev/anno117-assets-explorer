# import copy
# import json
# import re

# from pathlib import Path
# from typing import Literal, cast
# from glom import glom

# import src.engine.cli as Cli
# import src.engine.logger as Logger
# import src.utilities as utilities

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src import Logger


from pathlib import Path
import copy, json, re
from typing import Literal, cast

from src import utilities
from src import Cli

_global_config_file_path = Path.cwd() / "config.json"
_config_file_path = (
    lambda file_prefix: Path.cwd() / "config" / f"{file_prefix}-config.json"
)


def logger() -> Logger.Logger:
    from src import Logger

    return Logger.get("config", fallback=True)


def _read_config_from_file(read_path: Path) -> dict:
    try:
        if not read_path or not read_path.is_file():
            logger().error(
                f"Path: {read_path} is not a file.",
                verbose_only=True,
            )
        else:
            with open(read_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            logger().success(
                f"Loaded config from {read_path.absolute()}", verbose_only=True
            )
            return config
    except Exception as e:
        logger().error(
            f"Failed to load config file: {read_path.absolute()}: {e}",
            verbose_only=True,
        )
    return {}


def _dump_dict_to_file(write_path: Path, config: dict):
    write_config = utilities.deep_merge_dicts(
        _read_config_from_file(write_path), config
    )
    try:
        """Dump the current configuration to a file."""
        write_path.parent.mkdir(parents=True, exist_ok=True)
        with open(write_path, "w", encoding="utf-8") as f:
            json.dump(write_config, f, indent=4)
    except Exception:
        logger().error(f"Failed to write config file: {write_path.absolute()}")


class ConfigError(Exception):
    pass


class Config:

    def __init__(
        self,
        key: str,
        trust: Literal["file", "dict"] = "file",
        config_dict: dict = {},
    ):
        self._key = key
        logger().debug(f"Creating '{self._key}'.", verbose_only=True)

        self._merged_config_dict = {}
        self._specific_config_dict = {}

        self.nested = "." in key
        self.specify_file_path(reload=False)
        self.reload(trust=trust, config_dict=config_dict)
        logger().success(f"Config '{self._key}' initialized.", verbose_only=True)

    def _update(
        self,
        trust: Literal["file", "dict"] = "file",
        config_dict: dict = {},
    ) -> dict:

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
        update_config_dict = utilities.nest_dict(update_config_dict, self._key)
        specific_config_dict = utilities.nest_dict(specific_config_dict, self._key)

        # If nested, keep only the relevant sub-dict from specific config file
        if self.nested:
            specific_config_file_dict = utilities.nest_dict(
                utilities.dict_path(specific_config_file_dict, self._key, default={}),
                self._key,
            )
        else:
            # Create the nested structure for merging
            specific_config_file_dict = utilities.nest_dict(
                specific_config_file_dict, self._key
            )
        # Extract only the relevant sub-dict from global config file keeping nesting
        global_config_file_dict = utilities.nest_dict(
            utilities.dict_path(global_config_file_dict, self._key, default={}),
            self._key,
        )

        # Get a merged version of global and specific config files
        merged_config_file_dict = utilities.deep_merge_dicts(
            copy.deepcopy(global_config_file_dict),
            copy.deepcopy(specific_config_file_dict),
        )

        # Merge according to trust order
        if trust == "file":
            self._specific_config_dict = utilities.deep_merge_dicts(
                copy.deepcopy(update_config_dict),
                copy.deepcopy(specific_config_dict),
                copy.deepcopy(specific_config_file_dict),
            )
            self._merged_config_dict = utilities.deep_merge_dicts(
                copy.deepcopy(self._specific_config_dict),
                copy.deepcopy(merged_config_file_dict),
            )
        elif trust == "dict":
            self._specific_config_dict = utilities.deep_merge_dicts(
                copy.deepcopy(specific_config_file_dict),
                copy.deepcopy(specific_config_dict),
                copy.deepcopy(update_config_dict),
            )
            self._merged_config_dict = utilities.deep_merge_dicts(
                copy.deepcopy(merged_config_file_dict),
                copy.deepcopy(self._specific_config_dict),
            )

        # Always d-nest to keep only actual config dicts
        self._specific_config_dict = utilities.dict_path(
            self._specific_config_dict, self._key
        )
        self._merged_config_dict = utilities.dict_path(
            self._merged_config_dict, self._key
        )

        # Sanity check
        if self._specific_config_dict is None or self._merged_config_dict is None:
            raise ConfigError(f"Failed to extract config dict for key '{self._key}'.")

        logger().debug(
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
        logger().debug(f"<<< UPDATED {self._key} CONFIG", verbose_only=True)

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

    def reload_for_module(self, module: Cli.CliModule | None = None):
        if not self.nested:
            raise ConfigError("Cannot reload config for module when key is not nested.")
        unload = module is None
        if unload:
            self.specify_file_path()
            logger().debug(
                f"Module config for '{self._key}' unloaded.", verbose_only=True
            )
        else:
            self.specify_file_path(get(module.get_config_key())._config_file)
            logger().debug(
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
            utilities.dict_path(self._merged_config_dict, key, default=default)
        )

    def get_path(self, key: str) -> Path:
        return Path(Path.cwd() / self.get(f"paths.{key}", ""))

    def print(self, output: lambda *args, **kwargs: None = None) -> None:
        if output is None:
            output = logger().print
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

    def dump(self, target: Literal["specific", "global"] = "specific") -> None:
        """Dump the current configuration to a file."""
        dump_file = (
            _global_config_file_path if target == "global" else self._config_file
        )
        dump_dict = (
            self._specific_config_dict
            if target == "specific"
            else self._merged_config_dict
        )
        dump_data = (
            utilities.nest_dict(dump_dict, self._key)
            if self.nested or target == "global"
            else dump_dict
        )

        _dump_dict_to_file(dump_file, dump_data)
        logger().success(f"Config {self._key} dumped to '{dump_file}'.")

    def delete_file(self) -> None:
        """Delete the configuration file."""
        if self.nested:
            raise ConfigError("Cannot delete config file from nested config.")
        config_path = self._config_file
        if config_path.is_file():
            config_path.unlink()
            logger().success(f"Config file '{config_path.absolute()}' deleted.")
        else:
            logger().error(f"Failed to delete config file: '{config_path.absolute()}'.")

    def to_dict(self) -> dict:
        return copy.deepcopy(self._specific_config_dict)


def dump(*keys: str, target: Literal["specific", "global"] = "specific") -> None:
    from src import _configs

    if not keys:
        raise ConfigError("Provide at least one config key to dump.")
    cfgs = [v for k, v in _configs.items() if k in keys]
    for cfg in cfgs:
        cfg.dump(target=target)


def reload_for_module(module: Cli.CliModule | None = None) -> None:
    from src import _configs

    for cfg in _configs.values():
        if cfg.nested:
            cfg.reload_for_module(module)


def get(key: str) -> Config:
    from src import _configs

    if not key or key not in _configs:
        raise ConfigError(f"Config {key} not found.")
    return _configs[key]


def create(
    key: str = "",
    config_dict: dict = {},
    trust: str = "file",
) -> Config:
    from src import _configs

    if not key or key in _configs:
        raise ConfigError(f"Config {key} already exists.")
    _configs[key] = Config(key, config_dict=config_dict, trust=trust)
    return _configs[key]


class ConfigModule(Cli.CliModule):

    def prepare(self):
        self.add_args(
            Cli.CliArgument(
                "--names",
                short="-n",
                required=True,
                type=lambda p: p.replace("-", "_"),
                expect="many",
            ),
            Cli.CliArgument(
                "--global",
                short="-g",
                expect="many",
                accepted_values=["print", "dump", "merge"],
            ),
            Cli.CliArgument("--file", short="-f", expect="many"),
            Cli.CliArgument("--print", short="-p", type=bool),
            Cli.CliArgument("--dump", short="-d", type=bool),
            Cli.CliArgument("--merge", short="-m", type=bool),
            Cli.CliArgument("--reload", short="-r", accepted_values=["file", "dict"]),
            Cli.CliArgument("--global", short="-g", type=bool),
        )

    def run(self) -> int | None:
        if self.get_arg("--names"):
            for name in self.get_arg("--names"):
                cfg = get(name)
                if self.get_arg("--file"):
                    cfg.specify_file_path(self.get_arg("--file"), reload=False)
                if self.get_arg("--reload"):
                    cfg.reload(trust=self.get_arg("--reload"))
                if self.get_arg("--print"):
                    cfg.print()
                if self.get_arg("--dump"):
                    cfg.dump()
                if self.get_arg("--merge"):
                    cfg.merge()
