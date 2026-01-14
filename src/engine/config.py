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
import copy, re
from typing import Literal, cast

from src import utilities, AppPath, Cli

_merged_config_fpath = AppPath.fpath("config.json")
_specific_config_fpath = lambda file_name: AppPath.fpath(f"config/{file_name}.json")


def logger() -> Logger.Logger:
    from src import Logger

    return Logger.get("config", fallback=True)


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

    def _safe_read_json(self, path: AppPath.AppPath) -> dict:
        from src import Logger

        try:
            if path is None:
                return {}
            path.validate(action="r")
            data = path.read_json()
            logger().success(f"Config file '{path}' read.", verbose_only=True)
            return data
        except AppPath.AppPathError as e:
            logger().error(f"{e}", path, verbose_only=True)
            Logger.traceback(e, verbose_only=True)
            return {}

    def _safe_write_json(
        self, path: AppPath.AppPath, dict: dict, merge: bool = True
    ) -> None:
        from src import Logger

        try:
            if path is None:
                raise ConfigError("Trying to dump to None path.")
            path.validate(action="w")
            path.write_json(dict, merge=merge)
            logger().success(f"Config file '{path}' written.", verbose_only=True)
        except AppPath.AppPathError as e:
            logger().error(f"{e}", path, verbose_only=True)
            Logger.traceback(e, verbose_only=True)

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

        # Load both merged and specific config files
        merged_config_file_dict = self._safe_read_json(_merged_config_fpath)
        specific_config_file_dict = self._safe_read_json(self._config_fpath)

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

        # If nested and specified, extract also the nested dict from its parent dict, and re-nest
        nested_merged_config_file_dict = {}
        if isinstance(self.nested, str):
            nested_merged_config_file_dict = utilities.nest_dict(
                utilities.dict_path(
                    merged_config_file_dict, f"{self.nested}.{self._key}", default={}
                ),
                self._key,
            )

        # Extract only the relevant sub-dict from merged config file keeping nesting
        merged_config_file_dict = utilities.nest_dict(
            utilities.dict_path(merged_config_file_dict, self._key, default={}),
            self._key,
        )

        # Get a merged version of merged and specific dicts from files
        merged_config_file_dict = utilities.deep_merge_dicts(
            copy.deepcopy(merged_config_file_dict),
            copy.deepcopy(nested_merged_config_file_dict),
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
                "config_file": self._config_fpath,
                "nested": self.nested,
                "update_config_dict": update_config_dict,
                "specific_config_dict": specific_config_dict,
                "specific_config_file_dict": specific_config_file_dict,
                "nested_merged_config_file_dict": nested_merged_config_file_dict,
                "merged_config_file_dict": merged_config_file_dict,
                "merged_config_file_dict": merged_config_file_dict,
                "self.specific_config": self._specific_config_dict,
                "self.merged_config": self._merged_config_dict,
            },
            verbose_only=True,
        )
        logger().debug(f"<<< UPDATED {self._key} CONFIG", verbose_only=True)

    def specify_file_path(
        self, new_path: str | AppPath.AppPath = None, reload: bool = True
    ) -> None:
        if not new_path:
            self._config_fpath = (
                None if self.nested else _specific_config_fpath(self._key)
            )
        else:
            self._config_fpath = (
                AppPath.fpath(new_path) if isinstance(new_path, str) else new_path
            )
        if reload:
            self.reload()

    def reload_for_module(self, module: Cli.CliModule | None = None):
        if not self.nested:
            raise ConfigError("Cannot reload config for module when key is not nested.")
        unload = module is None
        if unload:
            self.nested = True
            self.specify_file_path()
            logger().debug(
                f"Module config for '{self._key}' unloaded.", verbose_only=True
            )
        else:
            self.nested = module.get_config_key()
            self.specify_file_path(get(self.nested)._config_fpath)
            logger().debug(
                f"Module config for '{self._key}' loaded from '{self._config_fpath}'.",
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

    def print(self, output: lambda *args, **kwargs: None = None) -> None:
        if output is None:
            output = logger().print
        output(
            {
                self._key: {
                    "nested": self.nested,
                    "config_file": self._config_fpath,
                    "specific": self._specific_config_dict,
                    "merged": self._merged_config_dict,
                }
            },
        )

    def dump(self, target: Literal["specific", "merged"] = "specific") -> None:
        """Dump the current configuration to a file."""

        # Determine dump file path
        dump_file = _merged_config_fpath if target == "merged" else self._config_fpath

        # Check dump file path
        if dump_file is None:
            raise ConfigError("Cannot dump non-specific nested config.")

        # Prepare dump dict
        dump_dict = self._specific_config_dict
        if target == "merged" or self.nested:
            dump_dict = utilities.nest_dict(
                # Use merged dict when dumping to merged.
                dump_dict if not target == "merged" else self._merged_config_dict,
                self._key,
            )

        # Dump to file
        self._safe_write_json(dump_file, dump_dict)

        # Update parent config RAM if nested
        if isinstance(self.nested, str):
            parent_cfg = get(self.nested)
            logger().debug(
                f"Updating parent config '{self.nested}' in RAM after dumping '{self._key}'.\nParent:",
                parent_cfg._specific_config_dict,
                "\n/;cm;bo/With:/;",
                dump_dict,
                verbose_only=True,
            )
            parent_cfg._specific_config_dict = utilities.deep_merge_dicts(
                parent_cfg._specific_config_dict, dump_dict
            )
            parent_cfg._merged_config_dict = utilities.deep_merge_dicts(
                parent_cfg._merged_config_dict, dump_dict
            )

        # Success.
        logger().success(f"Config {self._key} dumped to '{dump_file}'.")

    def to_dict(self) -> dict:
        return copy.deepcopy(self._specific_config_dict)


def dump(*keys: str, target: Literal["specific", "merged"] = "specific") -> None:
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
                "--merged",
                short="-g",
                expect="many",
                accepted_values=["print", "dump", "merge"],
            ),
            Cli.CliArgument("--file", short="-f", expect="many"),
            Cli.CliArgument("--print", short="-p", type=bool),
            Cli.CliArgument("--dump", short="-d", type=bool),
            Cli.CliArgument("--merge", short="-m", type=bool),
            Cli.CliArgument("--reload", short="-r", accepted_values=["file", "dict"]),
            Cli.CliArgument("--merged", short="-g", type=bool),
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
