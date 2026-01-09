# Utilities
from . import utils as utilities

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
    _loggers["default"] = Logger.create_default(verbose)

    # Initialize global config. Setup the config logger to use the default logger
    _loggers["config"] = _loggers["default"]

    # load the default logger config, keep verbosity.
    _loggers["default"].load_config(trust="dict", config_dict={"verbose": verbose})

    # Create engine loggers
    engine_logger_configs = {
        "cli": {"animate": True},
        "traceback": {"styles": {"objk": "cr", "str": "cm"}},
        # Swaps the config logger to use its own logger, remove the verbosity.
        "config": {"verbose": False},
    }
    for name, config_dict in engine_logger_configs.items():
        _loggers[name] = Logger.create(
            name=name, stream=_loggers["default"]._stream, config_dict=config_dict
        )

    # Reload the default logger from its config file.
    _loggers["default"].reload_config()

    # Swap the config logger to use its own logger, remove the verbosity.
    # _loggers["config"] = Logger.create("config", {"verbose": False})


# Exports
__all__ = [name for name in dir() if not name.startswith("_")]
