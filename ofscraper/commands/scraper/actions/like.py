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

import functools
import logging
import time

import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.context.exit as exit
import ofscraper.utils.live.screens as progress_utils
from rich.markup import escape
from rich.text import Text


log = logging.getLogger("shared")
like_str = "Performing Like Action on {name}"
unlike_str = "Performing Unlike Action on {name}"


@exit.exit_wrapper
def process_like(posts=None, model_id=None, task=None, username=None, **kwargs):
    progress_utils.switch_api_progress()
    progress_utils.update_activity_task(description=like_str.format(name=username))
    logging.getLogger("shared_other").warning(like_str.format(name=username))
    unfavorited_posts = get_posts_for_like(posts)
    posts = pre_filter(posts)
    post_ids = get_post_ids(unfavorited_posts)
    return like(model_id, username,post_ids)


@exit.exit_wrapper
def process_unlike(posts=None, model_id=None, task=None, username=None, **kwargs):
    progress_utils.switch_api_progress()
    progress_utils.update_activity_task(description=unlike_str.format(name=username))
    logging.getLogger("shared_other").warning(unlike_str.format(name=username))
    favorited_posts = get_posts_for_unlike(posts)
    posts = pre_filter(posts)
    post_ids = get_post_ids(favorited_posts)
    return unlike(model_id, username,post_ids)


def get_posts_for_unlike(post):
    return filter_for_favorited(post)


def get_posts_for_like(post):
    return filter_for_unfavorited(post)


def filter_for_unfavorited(posts: list) -> list:
    # output = list(filter(lambda x: x.favorited is False and x.opened, posts))
    output = list(filter(lambda x: x.opened, posts))

    log.debug(f"[bold]Number of unliked post[/bold] {len(output)}")
    return output


def filter_for_favorited(posts: list) -> list:
    # output = list(filter(lambda x: x.favorited is True and x.opened, posts))
    output = list(filter(lambda x: x.opened, posts))

    log.debug(f"[bold]Number of liked post[/bold] {len(output)}")
    return output


def pre_filter(posts):
    seen = set()
    return [post for post in posts if post.id not in seen and not seen.add(post.id)]


def get_post_ids(posts: list) -> list:
    return list(map(lambda x: x.id, posts))


def like(model_id, username,ids: list):
   return _like(model_id,username, ids, True)


def unlike(model_id,username, ids: list):
    return _like(model_id, username,ids, False)


def _like(model_id, username,ids: list, like_action: bool):
    like_str = (
        "Posts toggled from unlike to like...\n"
        if like_action
        else "Posts toggled from like to unlike...\n"
    )

    like_func = _toggle_like_requests if like_action else _toggle_unlike_requests
    with progress_utils.setup_like_progress_live():
        with sessionManager.sessionManager(
            sem=1,
            backend="httpx",
            retries=constants.getattr("API_LIKE_NUM_TRIES"),
            wait_min=constants.getattr("OF_MIN_WAIT_API"),
            wait_max=constants.getattr("OF_MAX_WAIT_API"),
        ) as c:
            tasks = []
            task = progress_utils.add_like_task(f"checked posts...\n", total=len(ids))
            task2 = progress_utils.add_like_task(like_str, total=None)

            [tasks.append(functools.partial(like_func, c, id, model_id)) for id in ids]
            count = 1

            stable_sleep_duration=constants.getattr("STABLE_SLEEP_DURATION_LIKE")
            sleep_duration_50=constants.getattr("SLEEP_DURATION_LIKE_50")
            sleep_duration_60=constants.getattr("SLEEP_DURATION_LIKE_60")
            sleep_duration_common=constants.getattr("COMMON_MULTIPLE_SLEEP_DURATION_LIKE")

            for count, func in enumerate(tasks):
                out = func()
                if out == 0:
                    sleep_duration = 0
                elif count + 1 % 60 == 0 and count + 1 % 50 == 0:
                    sleep_duration = sleep_duration_common
                elif count % 60 == 0:
                    sleep_duration = sleep_duration_60  # Divisible by 60 - 1 second sleep
                elif count % 50 == 0:
                    sleep_duration = sleep_duration_50   # Divisible by 50 - 30 seconds sleep
                else:
                    sleep_duration =  stable_sleep_duration
                if out == 1:
                    progress_utils.increment_like_task(task2)
                progress_utils.increment_like_task(task)
                time.sleep(sleep_duration)
                title="Liked" if like_action else "Unliked"
                liked=progress_utils.get_like_task(task2).completed
                post=progress_utils.get_like_task(task).completed
                action=title.lower()
                text_out=f"[bold]\\[{username}][/bold] [bold]\\[Action {title}][/bold] ({post} post checked, {liked} post changes to {action})"
            progress_utils.remove_like_task(task)
            progress_utils.remove_like_task(task2)
    log.warning(text_out)
    return text_out

def _toggle_like_requests(c, id, model_id):


    sleeper=sessionManager.SessionSleep(
        sleep=constants.getattr("SESSION_429_SLEEP_STARTER_VAL"),
        difmin=constants.getattr("SESSION_429_LIKE_INCREASE_SLEEP_TIME_DIF"),
    )
    if not read_args.retriveArgs().force_like and cache.get(f"liked_status_{id}", None):
        log.debug(f"ID: {id} marked as liked in cache")
        return 0
    sleep_duration = constants.getattr("DOUBLE_TOGGLE_SLEEP_DURATION_LIKE")
    favorited, id = _like_request(c, id, model_id,sleeper)
    if favorited:
        log.debug(f"ID: {id} changed to liked")
        out = 1
    else:
        log.debug(f"ID: {id} restored to liked")
        time.sleep(sleep_duration)
        _like_request(c, id, model_id,sleeper)
        out = 2
    cache.set(f"liked_status_{id}", True)
    return out


def _toggle_unlike_requests(c, id, model_id):
    sleeper=sessionManager.SessionSleep(
        sleep=constants.getattr("SESSION_429_SLEEP_STARTER_VAL"),
        difmin=constants.getattr("SESSION_429_LIKE_INCREASE_SLEEP_TIME_DIF")
    )
    if (
        not read_args.retriveArgs().force_like
        and cache.get(f"liked_status_{id}", None) == False
    ):
        log.debug(f"ID: {id} marked as unliked in cache")

        return 0
    sleep_duration = constants.getattr("DOUBLE_TOGGLE_SLEEP_DURATION_LIKE")
    favorited, id = _like_request(c, id, model_id,sleeper)
    if not favorited:
        log.debug(f"ID: {id} changed to unliked")
        out = 1
    else:
        log.debug(f"ID: {id} restored to unlike")
        time.sleep(sleep_duration)
        _like_request(c, id, model_id,sleeper)
        out = 2
    cache.set(f"liked_status_{id}", False)
    return out


def _like_request(c, id, model_id,sleeper):
   
    with c.requests(
        constants.getattr("favoriteEP").format(id, model_id),
        method="post",sleeper=sleeper,
        retries=constants.getattr("LIKE_MAX_RETRIES")
    ) as r:
        return r.json_()["isFavorite"], r.json_()["id"]