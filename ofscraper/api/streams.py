r"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      
"""

import asyncio
import logging
import math
import traceback

import arrow

import ofscraper.api.common.logs as common_logs
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.settings as settings
from ofscraper.db.operations_.media import (
    get_streams_media,
    get_media_ids_downloaded_model,
)
from ofscraper.db.operations_.posts import (
    get_streams_post_info,
    get_youngest_streams_date,
)
from ofscraper.utils.context.run_async import run
from ofscraper.utils.logs.helpers import is_trace

log = logging.getLogger("shared")


sem = None


@run
async def get_streams_posts(model_id, username, forced_after=None, c=None):

    oldstreams = None
    if not settings.get_api_cache_disabled():
        oldstreams = await get_streams_post_info(model_id=model_id, username=username)
    else:
        oldstreams = []
    trace_log_old(oldstreams)

    log.debug(f"[bold]Streams Cache[/bold] {len(oldstreams)} found")
    oldstreams = list(filter(lambda x: x is not None, oldstreams))
    after = await get_after(model_id, username, forced_after)
    time_log(username, after)
    splitArrays = get_split_array(oldstreams, after)
    tasks = get_tasks(splitArrays, c, model_id, after)
    data = await process_tasks(tasks, model_id, after)
    return data


async def process_tasks(tasks, model_id, after):
    responseArray = []
    page_count = 0

    page_task = progress_utils.add_api_task(
        f"Streams Content Pages Progress: {page_count}", visible=True
    )
    seen = set()
    while tasks:
        new_tasks = []

        for task in asyncio.as_completed(tasks):
            try:
                result, new_tasks_batch = await task
                new_tasks.extend(new_tasks_batch)
                page_count = page_count + 1
                progress_utils.update_api_task(
                    page_task,
                    description=f"Streams Content Pages Progress: {page_count}",
                )

                new_posts = [
                    post
                    for post in result
                    if post["id"] not in seen and not seen.add(post["id"])
                ]
                log.debug(
                    f"{common_logs.PROGRESS_IDS.format('Streams')} {list(map(lambda x:x['id'],new_posts))}"
                )
                log.trace(
                    f"{common_logs.PROGRESS_RAW.format('Streams')}".format(
                        posts="\n\n".join(
                            map(
                                lambda x: f"{common_logs.RAW_INNER} {x}",
                                new_posts,
                            )
                        )
                    )
                )

                responseArray.extend(new_posts)

            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue
        tasks = new_tasks

    progress_utils.remove_api_task(page_task)

    log.debug(
        f"{common_logs.FINAL_IDS.format('Streams')} {list(map(lambda x:x['id'],responseArray))}"
    )
    trace_log_task(responseArray)
    log.debug(f"{common_logs.FINAL_COUNT.format('Streams')} {len(responseArray)}")

    set_check(responseArray, model_id, after)
    return responseArray


def get_split_array(oldstreams, after):
    if len(oldstreams) == 0:
        return []
    min_posts = max(
        len(oldstreams) // constants.getattr("REASONABLE_MAX_PAGE"),
        constants.getattr("MIN_PAGE_POST_COUNT"),
    )
    log.debug(f"[bold]Streams Cache[/bold] {len(oldstreams)} found")
    oldstreams = list(filter(lambda x: x is not None, oldstreams))
    postsDataArray = sorted(oldstreams, key=lambda x: x.get("created_at"))
    filteredArray = list(filter(lambda x: x.get("created_at") >= after, postsDataArray))

    splitArrays = [
        filteredArray[i : i + min_posts]
        for i in range(0, len(filteredArray), min_posts)
    ]
    return splitArrays


def get_tasks(splitArrays, c, model_id, after):
    tasks = []
    before = arrow.get(read_args.retriveArgs().before or arrow.now()).float_timestamp
    if len(splitArrays) > 2:
        tasks.append(
            asyncio.create_task(
                scrape_stream_posts(
                    c,
                    model_id,
                    required_ids=set([ele.get("created_at") for ele in splitArrays[0]]),
                    timestamp=splitArrays[0][0].get("created_at"),
                    offset=True,
                )
            )
        )
        [
            tasks.append(
                asyncio.create_task(
                    scrape_stream_posts(
                        c,
                        model_id,
                        required_ids=set(
                            [ele.get("created_at") for ele in splitArrays[i]]
                        ),
                        timestamp=splitArrays[i - 1][-1].get("created_at"),
                        offset=False,
                    )
                )
            )
            for i in range(1, len(splitArrays) - 1)
        ]
        # keeping grabbing until nothing left
        tasks.append(
            asyncio.create_task(
                scrape_stream_posts(
                    c,
                    model_id,
                    timestamp=splitArrays[-1][0].get("created_at"),
                    offset=True,
                    required_ids=set([before]),
                )
            )
        )
    # use the first split if less then 3
    elif len(splitArrays) > 0:
        tasks.append(
            asyncio.create_task(
                scrape_stream_posts(
                    c,
                    model_id,
                    timestamp=splitArrays[0][0].get("created_at"),
                    offset=True,
                    required_ids=set([before]),
                )
            )
        )
    # use after if split is empty i.e no db data
    else:
        tasks.append(
            asyncio.create_task(
                scrape_stream_posts(
                    c,
                    model_id,
                    timestamp=after,
                    offset=True,
                    required_ids=set([before]),
                )
            )
        )
    return tasks


def set_check(unduped, model_id, after):
    if not after:
        seen = set()
        all_posts = [
            post
            for post in cache.get(f"streams_check_{model_id}", default=[]) + unduped
            if post["id"] not in seen and not seen.add(post["id"])
        ]

        cache.set(
            f"streams_check_{model_id}",
            all_posts,
            expire=constants.getattr("THREE_DAY_SECONDS"),
        )
        cache.close()


async def get_after(model_id, username, forced_after=None):
    if forced_after is not None:
        return forced_after
    elif not settings.get_after_enabled():
        return 0
    elif read_args.retriveArgs().after != None:
        return read_args.retriveArgs().after.float_timestamp

    elif cache.get(f"{model_id}_full_streams_scrape"):
        log.info(
            "Used --after previously. Scraping all streams posts required to make sure content is not missing"
        )
        return 0

    curr = await get_streams_media(model_id=model_id, username=username)
    if len(curr) == 0:
        log.debug("Setting date to zero because database is empty")
        return 0
    curr_downloaded = await get_media_ids_downloaded_model(
        model_id=model_id, username=username
    )
    missing_items = list(
        filter(
            lambda x: x.get("downloaded") != 1
            and x.get("post_id") not in curr_downloaded
            and x.get("unlocked") != 0,
            curr,
        )
    )
    missing_items = list(sorted(missing_items, key=lambda x: x.get("posted_at") or 0))
    if len(missing_items) == 0:
        log.debug(
            "Using newest db date because,all downloads in db marked as downloaded"
        )
        return arrow.get(
            await get_youngest_streams_date(model_id=model_id, username=username)
        ).float_timestamp
    else:
        log.debug(
            f"Setting date slightly before earliest missing item\nbecause {len(missing_items)} posts in db are marked as undownloaded"
        )
        return arrow.get(missing_items[0]["posted_at"] or 0).float_timestamp


async def scrape_stream_posts(
    c, model_id, timestamp=None, required_ids=None, offset=False
) -> list:
    global sem
    posts = None
    if timestamp and (
        float(timestamp) > (read_args.retriveArgs().before).float_timestamp
    ):
        return [], []
    timestamp = float(timestamp) - 1000 if timestamp and offset else timestamp
    url = (
        constants.getattr("streamsNextEP").format(model_id, str(timestamp))
        if timestamp
        else constants.getattr("streamsEP").format(model_id)
    )
    log.debug(url)

    new_tasks = []
    posts = []
    try:
        task = progress_utils.add_api_job_task(
            f"[Streams] Timestamp -> {arrow.get(math.trunc(float(timestamp))).format(constants.getattr('API_DATE_FORMAT')) if timestamp is not None  else 'initial'}",
            visible=True,
        )
        async with c.requests_async(url,forced=constants.getattr("API_FORCE_KEY")) as r:

            posts = (await r.json_())["list"]
            log_id = f"timestamp:{arrow.get(math.trunc(float(timestamp))).format(constants.getattr('API_DATE_FORMAT')) if timestamp is not None  else 'initial'}"
            if not bool(posts):
                log.debug(f"{log_id} -> no posts found")
                return [], []

            log.debug(f"{log_id} -> number of streams post found {len(posts)}")
            log.debug(
                f"{log_id} -> first date {posts[0].get('createdAt') or posts[0].get('postedAt')}"
            )
            log.debug(
                f"{log_id} -> last date {posts[-1].get('createdAt') or posts[-1].get('postedAt')}"
            )
            log.debug(
                f"{log_id} -> found streams post IDs {list(map(lambda x:x.get('id'),posts))}"
            )
            log.trace(
                "{log_id} -> archive raw {posts}".format(
                    log_id=log_id,
                    posts="\n\n".join(
                        map(
                            lambda x: f"scrapeinfo archive: {str(x)}",
                            posts,
                        )
                    ),
                )
            )

            if max(map(lambda x: float(x["postedAtPrecise"]), posts)) >= max(
                required_ids
            ):
                pass
            elif float(timestamp or 0) >= max(required_ids):
                pass
            else:
                log.debug(f"{log_id} Required before change:  {required_ids}")
                [required_ids.discard(float(ele["postedAtPrecise"])) for ele in posts]
                log.debug(f"{log_id} Required after change: {required_ids}")

                if len(required_ids) > 0:
                    new_tasks.append(
                        asyncio.create_task(
                            scrape_stream_posts(
                                c,
                                model_id,
                                timestamp=posts[-1]["postedAtPrecise"],
                                required_ids=required_ids,
                                offset=False,
                            )
                        )
                    )
    except asyncio.TimeoutError as _:
        raise Exception(f"Task timed out {url}")
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E
    finally:
        progress_utils.remove_api_job_task(task)

    return posts, new_tasks


def trace_log_task(responseArray):
    if not is_trace():
        return
    chunk_size = constants.getattr("LARGE_TRACE_CHUNK_SIZE")
    for i in range(1, len(responseArray) + 1, chunk_size):
        # Calculate end index considering potential last chunk being smaller
        end_index = min(
            i + chunk_size - 1, len(responseArray)
        )  # Adjust end_index calculation
        chunk = responseArray[i - 1 : end_index]  # Adjust slice to start at i-1
        api_str = "\n\n".join(
            map(lambda post: f"{common_logs.RAW_INNER} {post}\n\n", chunk)
        )
        log.trace(f"{common_logs.FINAL_RAW.format('Streams')}".format(posts=api_str))
        # Check if there are more elements remaining after this chunk
        if i + chunk_size > len(responseArray):
            break  # Exit the loop if we've processed all elements


def trace_log_old(responseArray):
    if not is_trace():
        return
    chunk_size = constants.getattr("LARGE_TRACE_CHUNK_SIZE")
    for i in range(1, len(responseArray) + 1, chunk_size):
        # Calculate end index considering potential last chunk being smaller
        end_index = min(
            i + chunk_size - 1, len(responseArray)
        )  # Adjust end_index calculation
        chunk = responseArray[i - 1 : end_index]  # Adjust slice to start at i-1
        log.trace(
            "oldstreams {posts}".format(
                posts="\n\n".join(list(map(lambda x: f"oldstreams: {str(x)}", chunk)))
            )
        )
        # Check if there are more elements remaining after this chunk
        if i + chunk_size > len(responseArray):
            break  # Exit the loop if we've processed all elements


def time_log(username, after):
    log.info(
        f"""
Setting streams scan range for {username} from {arrow.get(after).format(constants.getattr('API_DATE_FORMAT'))} to {arrow.get(read_args.retriveArgs().before or arrow.now()).format((constants.getattr('API_DATE_FORMAT')))}
[yellow]Hint: append ' --after 2000' to command to force scan of all streams posts + download of new files only[/yellow]
[yellow]Hint: append ' --after 2000 --force-all' to command to force scan of all streams posts + download/re-download of all files[/yellow]

            """
    )