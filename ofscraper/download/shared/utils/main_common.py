import pathlib
import arrow
import ofscraper.db.operations as operations
import ofscraper.download.common.common as common
import ofscraper.download.common.globals as common_globals
import ofscraper.download.common.log as common_logs
import ofscraper.download.common.paths as common_paths
import ofscraper.utils.dates as dates
import ofscraper.utils.system.system as system


async def handle_result_main(result, ele, username, model_id):
    total, temp, placeholderObj = result
    path_to_file = placeholderObj.trunicated_filepath
    await common.size_checker(temp, ele, total)
    common_globals.log.debug(
        f"{common_logs.get_medialog(ele)} {await ele.final_filename} size match target: {total} vs actual: {pathlib.Path(temp).absolute().stat().st_size}"
    )
    common_globals.log.debug(
        f"{common_logs.get_medialog(ele)} renaming {pathlib.Path(temp).absolute()} -> {path_to_file}"
    )
    common_paths.moveHelper(temp, path_to_file, ele)
    common_paths.addGlobalDir(placeholderObj.filedir) if system.get_parent_process() \
    else common_paths.addLocalDir(placeholderObj.filedir)
    if ele.postdate:
        newDate = dates.convert_local_time(ele.postdate)
        common_globals.log.debug(
            f"{common_logs.get_medialog(ele)} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}"
        )
        common_paths.set_time(path_to_file, newDate)
        common_globals.log.debug(
            f"{common_logs.get_medialog(ele)} Date set to {arrow.get(path_to_file.stat().st_mtime).format('YYYY-MM-DD HH:mm')}"
        )

    if ele.id:
        await operations.download_media_update(
            ele,
            filename=path_to_file,
            model_id=model_id,
            username=username,
            downloaded=True,
            hashdata=await common.get_hash(path_to_file, mediatype=ele.mediatype),
        )
    await common.set_profile_cache_helper(ele)
    common.add_additional_data(placeholderObj, ele)

    return ele.mediatype, total