import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.constants as const


def get_like_area():
    post = None
    all_choices = ["Archived", "Timeline", "Pinned", "Streams"]
    all_choices.append("Label") if const.getattr("INCLUDE_LABELS_ALL") else None
    if len(read_args.retriveArgs().like_area) == 0:
        post = set(read_args.retriveArgs().posts)
    else:
        post = set(read_args.retriveArgs().like_area)
    if "All" in post:
        post.update(set(all_choices))
    return finalize_choice(all_choices, post)


def get_download_area():
    post = None
    all_choices = [
        "Highlights",
        "Archived",
        "Messages",
        "Timeline",
        "Pinned",
        "Stories",
        "Purchased",
        "Profile",
        "Streams",
    ]
    all_choices.append("Label") if const.getattr("INCLUDE_LABELS_ALL") else None
    if len(read_args.retriveArgs().download_area) == 0:
        post = set(read_args.retriveArgs().posts)
    else:
        post = set(read_args.retriveArgs().download_area)
    if "All" in post:
        post.update(set(all_choices))
    return finalize_choice(all_choices, post)


def finalize_choice(all_choices, post):
    out = set(post)
    if ("Labels*" or "Labels+") in post:
        post.update(set(all_choices))
        post.update({"Labels"})
        post.discard("Labels*")
        post.discard("Labels+")
        out = set(
            list(
                filter(
                    lambda x: x != "All"
                    and x[0] != "-"
                    and f"-{x}" not in post
                    and x in all_choices + ["Labels"],
                    post,
                )
            )
        )
    return out


def get_final_posts_area():
    final_post_areas = set()
    args = read_args.retriveArgs()
    if "download" in args.action:
        final_post_areas.update(get_download_area())
    if args.command == "metadata":
        final_post_areas.update(get_download_area())
    if "like" in args.action or "unlike" in args.action:
        final_post_areas.update(get_like_area())
    return final_post_areas
