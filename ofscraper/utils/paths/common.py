import os
import pathlib

import arrow

import ofscraper.const.constants as consts
import ofscraper.utils.args.globals as global_args
import ofscraper.utils.config.data as data
import ofscraper.utils.constants as constants
import ofscraper.utils.profiles.data as profile_data


def getcachepath():
    profile = get_profile_path()
    name = "cache_json" if data.cache_mode_helper() == "json" else "cache_sql"
    path = profile / f"{name}"
    path = pathlib.Path(os.path.normpath(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_auth_file():
    return get_profile_path() / constants.getattr("authFile")


def get_username():
    return pathlib.Path.home().name


def getDB():
    return get_profile_path() / "db.lock"


def get_config_home():
    return get_config_path().parent


def get_config_path():
    configPath = global_args.getArgs().config
    defaultPath = pathlib.Path.home() / consts.configPath / consts.configFile
    ofscraperHome = pathlib.Path.home() / consts.configPath

    if configPath == None or configPath == "":
        return defaultPath
    configPath = pathlib.Path(configPath)
    # check if path exists
    if configPath.is_file():
        return configPath
    elif configPath.is_dir():
        return configPath / consts.configFile
    # enforce that configpath needs some extension
    elif configPath.suffix == "":
        return configPath / consts.configFile

    elif str(configPath.parent) == ".":
        return ofscraperHome / configPath
    return configPath


def getlogpath():
    logDate = global_args.getArgs().log_dateformat
    path = None
    if not data.get_appendlog():
        path = (
            get_config_home()
            / "logging"
            / f'{data.get_main_profile()}_{arrow.now().format("YYYY-MM-DD")}'
            / f"ofscraper_{data.get_main_profile()}_{logDate}.log"
        )
    else:
        path = (
            get_config_home()
            / "logging"
            / f"ofscraper_{data.get_main_profile()}_{logDate}.log"
        )
    path = pathlib.Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_profile_path(name=None):
    if name:
        return get_config_home() / name
    elif not global_args.getArgs().profile:
        return get_config_home() / profile_data.get_current_config_profile()
    return get_config_home() / global_args.getArgs().profile


def get_save_location(config=None):
    if config == None:
        return constants.getattr("SAVE_PATH_DEFAULT")
    return (
        config.get("save_location")
        or config.get("file_options", {}).get("save_location")
        or config.get("save_location")
        or constants.getattr("SAVE_PATH_DEFAULT")
    )


def get_config_folder():
    out = get_config_path().parent
    out.mkdir(exist_ok=True, parents=True)
    return out