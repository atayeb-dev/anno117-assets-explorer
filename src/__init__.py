# Standard library imports
import sys

# Utilities
from . import utils as utilities

# App path
from . import app_path as AppPath

# Engine modules
from .engine import logger as Logger
from .engine import cli as Cli
from .engine import config as Config

# Engine globals
_loggers: dict[str, Logger.Logger] = {}
_configs: dict[str, Config.Config] = {}
_modules: dict[str, Cli.CliModule] = {}


# Engine initialization
def init_engine(verbose: bool = False) -> None:
    global _loggers, _configs, _modules

    # Create default logger
    _loggers["default"] = Logger.create_default(stream=sys.stdout, verbose=verbose)

    # load the default logger config, keep verbosity.
    _loggers["default"].load_config(trust="dict", config_dict={"verbose": verbose})

    # Engine loggers default configs
    engine_logger_configs = {
        "traceback": {
            "dict": {
                "animate": False,
                "verbose": True,
                "data_print": {"styles": {"objk": "cr", "str": "cm"}},
            },
            "stream": sys.stderr,
        },
        "cli": {"dict": {"animate": True, "verbose": False}, "stream": sys.stdout},
        # init config last to preserve default logger while loading.
        "config": {"dict": {"verbose": False}, "stream": sys.stdout},
    }

    # Create engine loggers
    for name, logger in engine_logger_configs.items():
        Logger.create(
            name=name,
            stream=logger["stream"],
            config_dict=logger["dict"],
        )

    # Reload the default logger from its the config file.
    _loggers["default"].reload_config()

    # Dump all loggers config to global config file.
    for logger in _loggers.values():
        logger.get_config().dump(target="global")


# Exports
__all__ = [name for name in dir() if not name.startswith("_")]
