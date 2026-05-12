#!/usr/bin/env python3
"""
Fetch photo tweets from an X/Twitter user without the official API.

Primary workflow:
1. Reuse a saved twikit cookies file when available.
2. Optionally perform a fresh login and save cookies.
3. Fetch the user's tweet timeline.
4. Keep only original tweets with photo media.
5. Normalize media URLs to `name=orig`.
6. Download images and persist a flat JSON manifest:

[
  {
    "filename": "2049840657125232930_1.jpg",
    "tweet_time": "2026-04-30T10:12:34Z"
  }
]

Example:
  python tools/fetch_x_images_unofficial.py ^
    --user ASU_virtual ^
    --out-dir x_images/ASU_virtual ^
    --json-out data/asu_virtual_x_images.json ^
    --cookies-file token/x_cookies_ASU_virtual.json ^
    --max-tweets 500 ^
    --since 2025-01-01 ^
    --until 2026-05-10

First login:
  python tools/fetch_x_images_unofficial.py ^
    --user ASU_virtual ^
    --login ^
    --auth-info-1 your_username ^
    --auth-info-2 your_email ^
    --password your_password
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import traceback
import urllib.parse
import urllib.request
from http.cookies import SimpleCookie
from dataclasses import dataclass
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path
from typing import Any, Iterable, Optional


DEFAULT_OUT_DIR = Path("x_images") / "ASU_virtual"
DEFAULT_JSON_OUT = Path("data") / "asu_virtual_x_images.json"
DEFAULT_COOKIES_FILE = Path("token") / "x_cookies_ASU_virtual.json"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
CONTENT_TYPE_TO_EXT = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


@dataclass(frozen=True)
class ImageRecord:
    filename: str
    tweet_time: str


class TwikitTransactionCompat:
    def __init__(self) -> None:
        self.home_page_response = None
        self._delegate: Any = None
        self.key = None
        self.key_bytes = None
        self.animation_key = None

    async def init(self, session: Any, headers: dict[str, str]) -> None:
        try:
            from x_client_transaction import ClientTransaction as XClientTransaction
            from x_client_transaction.utils import (
                get_ondemand_file_url,
                handle_x_migration_async,
            )
        except ImportError as exc:
            raise RuntimeError(
                "XClientTransaction is not installed. Install it with "
                "`pip install XClientTransaction`."
            ) from exc

        home_page_response = await handle_x_migration_async(session)
        ondemand_file_url = get_ondemand_file_url(home_page_response)
        ondemand_file_response = await session.request(
            method="GET",
            url=ondemand_file_url,
            headers=headers,
        )

        delegate = XClientTransaction(
            home_page_response=home_page_response,
            ondemand_file_response=ondemand_file_response.text,
        )
        self.home_page_response = home_page_response
        self._delegate = delegate
        self.key = delegate.key
        self.key_bytes = delegate.key_bytes
        self.animation_key = delegate.animation_key

    def generate_transaction_id(self, method: str, path: str) -> str:
        if self._delegate is None:
            raise RuntimeError("Transaction generator is not initialized.")
        return self._delegate.generate_transaction_id(method=method, path=path)


def patch_twikit_user_compat() -> None:
    try:
        import twikit.user as twikit_user_module
    except ImportError:
        return

    modules: list[Any] = [twikit_user_module]
    try:
        import twikit.guest.user as twikit_guest_user_module
        modules.append(twikit_guest_user_module)
    except ImportError:
        pass

    def patch_user_class(module: Any) -> None:
        user_cls = getattr(module, "User", None)
        if user_cls is None or getattr(user_cls, "_asu_pinwall_patched", False):
            return

        original_init = user_cls.__init__

        def wrapped_init(self: Any, client: Any, data: dict) -> None:
            if isinstance(data, dict):
                legacy = data.setdefault("legacy", {})
                entities = legacy.setdefault("entities", {})
                description = entities.setdefault("description", {})
                description.setdefault("urls", [])

                optional_defaults = {
                    "withheld_in_countries": [],
                    "pinned_tweet_ids_str": [],
                    "verified": False,
                    "possibly_sensitive": False,
                    "can_dm": False,
                    "can_media_tag": False,
                    "want_retweets": False,
                    "default_profile": False,
                    "default_profile_image": False,
                    "has_custom_timelines": False,
                    "followers_count": 0,
                    "fast_followers_count": 0,
                    "normal_followers_count": 0,
                    "friends_count": 0,
                    "favourites_count": 0,
                    "listed_count": 0,
                    "media_count": 0,
                    "statuses_count": 0,
                    "is_translator": False,
                    "translator_type": "",
                    "location": "",
                    "description": "",
                    "name": "",
                    "screen_name": "",
                    "profile_image_url_https": "",
                    "created_at": "",
                }
                for key, value in optional_defaults.items():
                    legacy.setdefault(key, value)

                data.setdefault("is_blue_verified", False)
                data.setdefault("rest_id", "")

            original_init(self, client, data)

        user_cls.__init__ = wrapped_init
        user_cls._asu_pinwall_patched = True

    for module in modules:
        patch_user_class(module)


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def debug_object_state(label: str, obj: Any) -> None:
    try:
        state = vars(obj)
    except TypeError:
        state = None
    eprint(f"[DEBUG] {label} type={type(obj)!r}")
    if state is None:
        eprint(f"[DEBUG] {label} has no __dict__")
        return
    for key in sorted(state):
        value = state[key]
        if callable(value):
            rendered = f"<callable {getattr(value, '__name__', type(value).__name__)}>"
        else:
            rendered = repr(value)
        if len(rendered) > 500:
            rendered = rendered[:500] + "...<truncated>"
        eprint(f"[DEBUG] {label}.{key} = {rendered}")


def get_entry_id(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    entry_id = item.get("entryId")
    return entry_id if isinstance(entry_id, str) else ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch photo tweets for an X/Twitter user through twikit "
            "with login cookies, then save original images locally."
        )
    )
    parser.add_argument("--user", required=True, help="X username without @.")
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help=f"Directory to save images. Default: {DEFAULT_OUT_DIR}",
    )
    parser.add_argument(
        "--json-out",
        default=str(DEFAULT_JSON_OUT),
        help=f"Manifest JSON output path. Default: {DEFAULT_JSON_OUT}",
    )
    parser.add_argument(
        "--cookies-file",
        default=str(DEFAULT_COOKIES_FILE),
        help=f"twikit cookies file path. Default: {DEFAULT_COOKIES_FILE}",
    )
    parser.add_argument(
        "--max-tweets",
        type=int,
        default=500,
        help="Maximum number of timeline tweets to scan. Default: 500",
    )
    parser.add_argument(
        "--fetch-all",
        action="store_true",
        help=(
            "Keep paginating through the full timeline history until X stops "
            "returning more pages. When omitted, --max-tweets stays the main limit."
        ),
    )
    parser.add_argument(
        "--tweet-type",
        choices=["Media", "Tweets", "Replies", "Likes"],
        default="Media",
        help=(
            "Which user timeline to scan from twikit. Default: Media, "
            "which is best for image tweet collection."
        ),
    )
    parser.add_argument(
        "--since",
        default=None,
        help="Keep tweets on/after this date or datetime (YYYY-MM-DD or ISO 8601).",
    )
    parser.add_argument(
        "--until",
        default=None,
        help="Keep tweets on/before this date or datetime (YYYY-MM-DD or ISO 8601).",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Perform login and refresh the cookies file before fetching.",
    )
    parser.add_argument(
        "--auth-info-1",
        default=None,
        help="Login identifier 1, typically username or phone.",
    )
    parser.add_argument(
        "--auth-info-2",
        default=None,
        help="Login identifier 2, typically email.",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="X account password. Prefer environment variables for safety.",
    )
    parser.add_argument(
        "--locale",
        default="en-US",
        help="twikit client locale. Default: en-US",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help=(
            "Proxy URL for twikit/httpx, for example "
            "http://127.0.0.1:7890 or socks5://127.0.0.1:1080. "
            "If omitted, falls back to HTTPS_PROXY or HTTP_PROXY when present."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Download timeout in seconds. Default: 30",
    )
    parser.add_argument(
        "--download-delay",
        type=float,
        default=0.0,
        help="Optional delay between image downloads in seconds. Default: 0",
    )
    parser.add_argument(
        "--cookie-header-file",
        default=None,
        help=(
            "Path to a local text file containing a raw Cookie header value "
            "copied from your browser for x.com. The script will import it "
            "into twikit and save it to --cookies-file."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed exception information for debugging.",
    )
    parser.add_argument(
        "--debug-sample",
        type=int,
        default=0,
        help=(
            "Print debug summaries for the first N fetched tweets, including "
            "reply/retweet flags and media types. Default: 0"
        ),
    )
    parser.add_argument(
        "--stop-after-empty-pages",
        type=int,
        default=3,
        help=(
            "In incremental mode, stop after this many consecutive pages without "
            "new or repaired photo entries. Default: 3"
        ),
    )
    return parser.parse_args()


def normalize_username(username: str) -> str:
    return username.lstrip("@").strip()


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_user_datetime(value: Optional[str], *, is_until: bool) -> Optional[datetime]:
    if not value:
        return None

    raw = value.strip()
    if not raw:
        return None

    if "T" not in raw:
        parsed_date = datetime.strptime(raw, "%Y-%m-%d").date()
        if is_until:
            dt = datetime(
                parsed_date.year,
                parsed_date.month,
                parsed_date.day,
                23,
                59,
                59,
                999999,
                tzinfo=timezone.utc,
            )
        else:
            dt = datetime(
                parsed_date.year,
                parsed_date.month,
                parsed_date.day,
                tzinfo=timezone.utc,
            )
        return dt

    normalized = raw.replace("Z", "+00:00")
    return ensure_utc(datetime.fromisoformat(normalized))


def format_tweet_time(value: datetime) -> str:
    return ensure_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_existing_manifest(path: Path) -> list[ImageRecord]:
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    records: list[ImageRecord] = []
    if not isinstance(payload, list):
        raise ValueError(f"Manifest must be a list: {path}")

    for item in payload:
        if not isinstance(item, dict):
            continue
        filename = item.get("filename")
        tweet_time = item.get("tweet_time")
        if isinstance(filename, str) and isinstance(tweet_time, str):
            records.append(ImageRecord(filename=filename, tweet_time=tweet_time))
    return records


def parse_cookie_header(cookie_header: str) -> dict[str, str]:
    # Browser-exported Cookie headers often contain JSON-like values such as
    # g_state={...}. SimpleCookie may stop parsing partway through those values
    # and silently drop auth cookies that appear later in the header.
    fallback: dict[str, str] = {}
    for item in cookie_header.split(";"):
        part = item.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        fallback[key] = value

    parsed = SimpleCookie()
    try:
        parsed.load(cookie_header)
    except Exception:
        return fallback

    cookies = {key: morsel.value for key, morsel in parsed.items()}
    cookies.update(fallback)
    return cookies


def import_cookie_header_if_present(
    client: Any,
    cookie_header_file: Optional[str],
    cookies_file: Path,
) -> bool:
    if not cookie_header_file:
        return False

    path = Path(cookie_header_file)
    if not path.exists():
        raise RuntimeError(f"Cookie header file does not exist: {path}")

    cookie_header = path.read_text(encoding="utf-8").strip()
    if not cookie_header:
        raise RuntimeError(f"Cookie header file is empty: {path}")

    cookies = parse_cookie_header(cookie_header)
    if not cookies:
        raise RuntimeError(
            f"Failed to parse cookies from header file: {path}"
        )
    missing_auth_keys = [key for key in ("auth_token", "ct0") if key not in cookies]
    if missing_auth_keys:
        raise RuntimeError(
            "Cookie header is missing required X auth cookies: "
            + ", ".join(missing_auth_keys)
        )

    client.set_cookies(cookies, clear_cookies=True)
    cookies_file.parent.mkdir(parents=True, exist_ok=True)
    client.save_cookies(str(cookies_file))
    return True


def write_manifest(path: Path, records: Iterable[ImageRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {"filename": record.filename, "tweet_time": record.tweet_time}
        for record in records
    ]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def get_attr(obj: Any, *names: str) -> Any:
    if obj is None:
        return None
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj.get(name)
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def is_retweet(tweet: Any) -> bool:
    if get_attr(tweet, "retweeted_tweet", "retweeted_status") is not None:
        return True

    referenced = get_attr(tweet, "referenced_tweets")
    if isinstance(referenced, list):
        for item in referenced:
            ref_type = str(get_attr(item, "type") or "").lower()
            if ref_type == "retweeted":
                return True

    return bool(get_attr(tweet, "is_retweet"))


def is_reply(tweet: Any) -> bool:
    if bool(get_attr(tweet, "is_reply")):
        return True
    if get_attr(tweet, "in_reply_to", "in_reply_to_status_id", "reply_to") is not None:
        return True

    referenced = get_attr(tweet, "referenced_tweets")
    if isinstance(referenced, list):
        for item in referenced:
            ref_type = str(get_attr(item, "type") or "").lower()
            if ref_type == "replied_to":
                return True

    return False


def extract_tweet_id(tweet: Any) -> Optional[str]:
    value = get_attr(tweet, "id", "tweet_id")
    if value is None:
        return None
    return str(value)


def parse_tweet_time(tweet: Any) -> Optional[datetime]:
    created_at_datetime = get_attr(tweet, "created_at_datetime")
    if isinstance(created_at_datetime, datetime):
        return ensure_utc(created_at_datetime)

    raw = get_attr(tweet, "created_at")
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return ensure_utc(raw)

    text = str(raw).strip()
    if not text:
        return None

    try:
        if text.endswith("Z"):
            return ensure_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
        if "+" in text[10:] or text.endswith("00:00"):
            return ensure_utc(datetime.fromisoformat(text))
        return ensure_utc(datetime.strptime(text, "%a %b %d %H:%M:%S %z %Y"))
    except ValueError:
        return None


def within_range(
    tweet_time: datetime,
    *,
    since: Optional[datetime],
    until: Optional[datetime],
) -> bool:
    if since and tweet_time < since:
        return False
    if until and tweet_time > until:
        return False
    return True


def normalize_media_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

    if "name" in query:
        query["name"] = ["orig"]
    else:
        query.setdefault("name", ["orig"])

    path = parsed.path
    suffix = Path(path).suffix.lower().lstrip(".")
    if "format" not in query and suffix in IMAGE_EXTENSIONS:
        query["format"] = ["jpg" if suffix == "jpeg" else suffix]

    new_query = urllib.parse.urlencode(query, doseq=True)
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


def infer_extension_from_url(url: str) -> Optional[str]:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

    fmt = query.get("format", [None])[0]
    if isinstance(fmt, str) and fmt:
        fmt = fmt.lower()
        return "jpg" if fmt == "jpeg" else fmt

    suffix = Path(parsed.path).suffix.lower().lstrip(".")
    if suffix in IMAGE_EXTENSIONS:
        return "jpg" if suffix == "jpeg" else suffix
    return None


def infer_extension_from_response(response: Any) -> Optional[str]:
    content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    return CONTENT_TYPE_TO_EXT.get(content_type)


def extract_media_items(tweet: Any) -> list[Any]:
    media = get_attr(tweet, "media")
    if isinstance(media, list):
        return media
    if isinstance(media, tuple):
        return list(media)
    return []


def is_photo_media(media: Any) -> bool:
    media_type = str(get_attr(media, "type", "media_type") or "").lower()
    class_name = media.__class__.__name__.lower()
    return media_type == "photo" or class_name == "photo"


def extract_media_url(media: Any) -> Optional[str]:
    for key in ("media_url_https", "media_url", "expanded_url", "url"):
        value = get_attr(media, key)
        if isinstance(value, str) and value.startswith("http"):
            return value
    return None


def tweet_debug_summary(tweet: Any) -> str:
    tweet_id = extract_tweet_id(tweet) or "unknown"
    tweet_time = parse_tweet_time(tweet)
    time_text = format_tweet_time(tweet_time) if tweet_time else "unknown"
    reply_flag = is_reply(tweet)
    retweet_flag = is_retweet(tweet)
    media_items = extract_media_items(tweet)
    media_bits: list[str] = []
    for media in media_items:
        media_type = str(get_attr(media, "type", "media_type") or "unknown")
        media_url = extract_media_url(media) or ""
        media_bits.append(f"{media_type}:{media_url[:100]}")
    text = str(get_attr(tweet, "full_text", "text") or "").replace("\n", " ")
    text = text[:120]
    media_text = "; ".join(media_bits) if media_bits else "none"
    return (
        f"id={tweet_id} time={time_text} reply={reply_flag} "
        f"retweet={retweet_flag} media_count={len(media_items)} "
        f"media=[{media_text}] text={text}"
    )


def collect_photo_entries(
    tweet: Any,
    *,
    since: Optional[datetime],
    until: Optional[datetime],
) -> list[tuple[str, datetime, int, str]]:
    tweet_id = extract_tweet_id(tweet)
    tweet_time = parse_tweet_time(tweet)
    if not tweet_id or not tweet_time:
        return []

    if not within_range(tweet_time, since=since, until=until):
        return []
    if is_retweet(tweet) or is_reply(tweet):
        return []

    entries: list[tuple[str, datetime, int, str]] = []
    photo_index = 0

    for media in extract_media_items(tweet):
        if not is_photo_media(media):
            continue
        media_url = extract_media_url(media)
        if not media_url or "pbs.twimg.com" not in media_url:
            continue
        photo_index += 1
        entries.append((tweet_id, tweet_time, photo_index, normalize_media_url(media_url)))

    return entries


def resolve_filename(tweet_id: str, index: int, url: str, response_ext: Optional[str]) -> str:
    ext = infer_extension_from_url(url) or response_ext or "jpg"
    ext = "jpg" if ext == "jpeg" else ext
    return f"{tweet_id}_{index}.{ext}"


def record_stem(filename: str) -> str:
    return Path(filename).stem


def download_with_extension(
    url: str,
    out_dir: Path,
    tweet_id: str,
    index: int,
    timeout: int,
) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://x.com/",
        },
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        response_ext = infer_extension_from_response(response)
        filename = resolve_filename(tweet_id, index, url, response_ext)
        destination = out_dir / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "wb") as handle:
            handle.write(response.read())
    return filename


async def build_client(locale: str, proxy: Optional[str]) -> Any:
    try:
        from twikit import Client
    except ImportError as exc:
        raise RuntimeError(
            "twikit is not installed. Install it first with `pip install twikit`."
        ) from exc

    patch_twikit_user_compat()
    client = Client(locale, proxy=proxy)
    try:
        client.client_transaction = TwikitTransactionCompat()
    except Exception:
        pass
    return client


def resolve_login_value(cli_value: Optional[str], *env_names: str) -> Optional[str]:
    if cli_value:
        return cli_value
    for env_name in env_names:
        value = os.environ.get(env_name)
        if value:
            return value
    return None


async def maybe_login(client: Any, args: argparse.Namespace, cookies_file: Path) -> None:
    if not args.login:
        return

    auth_info_1 = resolve_login_value(args.auth_info_1, "X_AUTH_INFO_1", "X_USERNAME")
    auth_info_2 = resolve_login_value(args.auth_info_2, "X_AUTH_INFO_2", "X_EMAIL")
    password = resolve_login_value(args.password, "X_PASSWORD")

    if not auth_info_1:
        auth_info_1 = input("X auth_info_1 (username/phone): ").strip()
    if not auth_info_2:
        auth_info_2 = input("X auth_info_2 (email): ").strip()
    if not password:
        password = getpass("X password: ")

    if not auth_info_1 or not auth_info_2 or not password:
        raise RuntimeError("Login requires auth_info_1, auth_info_2, and password.")

    cookies_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        await client.login(
            auth_info_1=auth_info_1,
            auth_info_2=auth_info_2,
            password=password,
            cookies_file=str(cookies_file),
        )
    except Exception as exc:
        raise RuntimeError(
            f"twikit login failed: {type(exc).__name__}: {exc!r}"
        ) from exc


def load_cookies_if_present(client: Any, cookies_file: Path) -> None:
    if cookies_file.exists():
        client.load_cookies(str(cookies_file))


async def get_user_by_screen_name(client: Any, username: str) -> Any:
    getter = getattr(client, "get_user_by_screen_name", None)
    if getter is None:
        raise RuntimeError("twikit client does not expose get_user_by_screen_name().")
    return await getter(username)


def extract_user_id(user: Any) -> Optional[str]:
    value = get_attr(user, "id", "rest_id")
    if value is None:
        return None
    return str(value)


async def get_first_page(client: Any, user_id: str) -> Any:
    raise RuntimeError("Internal error: get_first_page requires tweet_type.")


async def get_first_page_with_type(client: Any, user_id: str, tweet_type: str) -> Any:
    getter = getattr(client, "get_user_tweets", None)
    if getter is None:
        raise RuntimeError("twikit client does not expose get_user_tweets().")

    try:
        return await getter(user_id, tweet_type)
    except TypeError:
        return await getter(user_id)


def page_to_items(page: Any) -> list[Any]:
    if page is None:
        return []
    if isinstance(page, list):
        return page
    if isinstance(page, tuple):
        return list(page)
    if hasattr(page, "__iter__"):
        try:
            return list(page)
        except TypeError:
            return []
    return []


async def get_next_page(page: Any) -> Any:
    next_method = getattr(page, "next", None)
    if not callable(next_method):
        return None
    return await next_method()


def extract_cursor_from_entries(entries: list[Any], cursor_kind: str) -> Optional[str]:
    for item in entries:
        if not isinstance(item, dict):
            continue
        entry_id = get_entry_id(item)
        if cursor_kind not in entry_id:
            continue
        content = item.get("content")
        if not isinstance(content, dict):
            continue
        value = content.get("value")
        if isinstance(value, str) and value:
            return value
    return None


def score_tweet_entry_list(items: Any) -> int:
    if not isinstance(items, list):
        return -1
    score = 0
    for item in items:
        entry_id = get_entry_id(item)
        if entry_id.startswith(("tweet", "profile-conversation", "profile-grid")):
            score += 1
    return score


def iter_nested_lists(obj: Any) -> Iterable[list[Any]]:
    if isinstance(obj, list):
        yield obj
        for item in obj:
            yield from iter_nested_lists(item)
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from iter_nested_lists(value)


def select_media_items_from_response(instructions: list[Any], entries: list[Any]) -> list[Any]:
    candidates: list[list[Any]] = []

    if entries:
        first_content = get_attr(entries[0], "content")
        nested_items = get_attr(first_content, "items")
        if isinstance(nested_items, list):
            candidates.append(nested_items)

    module_items = find_dict_values(instructions, "moduleItems")
    for value in module_items:
        if isinstance(value, list):
            candidates.append(value)

    items_values = find_dict_values(instructions, "items")
    for value in items_values:
        if isinstance(value, list):
            candidates.append(value)

    entries_values = find_dict_values(instructions, "entries")
    for value in entries_values:
        if isinstance(value, list):
            candidates.append(value)

    best_items: list[Any] = []
    best_score = -1
    for candidate in candidates:
        score = score_tweet_entry_list(candidate)
        if score > best_score:
            best_items = candidate
            best_score = score

    if best_score > 0:
        return best_items
    return []


def find_dict_values(obj: Any, key: str) -> list[Any]:
    values: list[Any] = []
    if isinstance(obj, dict):
        if key in obj:
            values.append(obj[key])
        for value in obj.values():
            values.extend(find_dict_values(value, key))
    elif isinstance(obj, list):
        for item in obj:
            values.extend(find_dict_values(item, key))
    return values


async def fetch_media_page_compat(
    client: Any,
    user_id: str,
    cursor: Optional[str],
    *,
    count: int = 40,
) -> tuple[list[Any], Optional[str]]:
    try:
        from twikit.tweet import tweet_from_data
        from twikit.utils import find_dict
    except ImportError as exc:
        raise RuntimeError("twikit internals are unavailable for media pagination.") from exc

    response, _ = await client.gql.user_media(user_id, count, cursor)
    instructions_ = find_dict(response, "instructions", True)
    if not instructions_:
        return [], None

    instructions = instructions_[0]
    if not isinstance(instructions, list) or not instructions:
        return [], None

    tail_entries = get_attr(instructions[-1], "entries")
    entries = tail_entries if isinstance(tail_entries, list) else []
    next_cursor = extract_cursor_from_entries(entries, "cursor-bottom")
    items = select_media_items_from_response(instructions, entries)

    results: list[Any] = []
    for item in items:
        entry_id = get_entry_id(item)
        if not entry_id.startswith(("tweet", "profile-conversation", "profile-grid")):
            continue

        if entry_id.startswith("profile-conversation"):
            content = get_attr(item, "content")
            tweets = get_attr(content, "items")
            if not isinstance(tweets, list) or not tweets:
                continue
            replies = []
            for reply in tweets[1:]:
                tweet_object = tweet_from_data(client, reply)
                if tweet_object is None:
                    continue
                replies.append(tweet_object)
            item = tweets[0]
        else:
            replies = None

        tweet = tweet_from_data(client, item)
        if tweet is None:
            continue
        tweet.replies = replies
        results.append(tweet)

    return results, next_cursor


async def collect_timeline_tweets(
    client: Any,
    username: str,
    max_tweets: Optional[int],
    tweet_type: str,
    *,
    since: Optional[datetime],
    fetch_all: bool,
    existing_stems: set[str],
    out_dir: Path,
    stop_after_empty_pages: int,
) -> tuple[list[Any], int]:
    user = await get_user_by_screen_name(client, username)
    user_id = extract_user_id(user)
    if not user_id:
        raise RuntimeError(f"Could not resolve user id for @{username}.")

    collected: list[Any] = []
    pages_scanned = 0
    consecutive_empty_pages = 0

    if tweet_type == "Media":
        cursor: Optional[str] = None
        while max_tweets is None or len(collected) < max_tweets:
            page_items, next_cursor = await fetch_media_page_compat(
                client,
                user_id,
                cursor,
            )
            if not page_items:
                break

            pages_scanned += 1
            remaining = None if max_tweets is None else max_tweets - len(collected)
            page_slice = page_items if remaining is None else page_items[:remaining]
            collected.extend(page_slice)
            eprint(
                f"[INFO] Media page {pages_scanned}: "
                f"{len(page_slice)} tweets, total scanned={len(collected)}"
            )

            if not fetch_all:
                page_new_entries = 0
                for tweet in page_slice:
                    for tweet_id, _, photo_index, _ in collect_photo_entries(
                        tweet,
                        since=since,
                        until=None,
                    ):
                        stable_stem = f"{tweet_id}_{photo_index}"
                        if stable_stem not in existing_stems or not list(out_dir.glob(f"{stable_stem}.*")):
                            page_new_entries += 1

                if page_new_entries == 0:
                    consecutive_empty_pages += 1
                else:
                    consecutive_empty_pages = 0

                if consecutive_empty_pages >= stop_after_empty_pages:
                    break

            if max_tweets is not None and len(collected) >= max_tweets:
                break

            if since:
                page_times = [tweet_time for tweet in page_slice if (tweet_time := parse_tweet_time(tweet))]
                if page_times and min(page_times) < since:
                    break

            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor

        return collected, pages_scanned

    page = await get_first_page_with_type(client, user_id, tweet_type)
    if page is not None:
        debug_object_state("first_page", page)

    while page is not None and (max_tweets is None or len(collected) < max_tweets):
        items = page_to_items(page)
        if not items:
            break

        pages_scanned += 1
        remaining = None if max_tweets is None else max_tweets - len(collected)
        page_slice = items if remaining is None else items[:remaining]
        collected.extend(page_slice)

        if not fetch_all:
            page_new_entries = 0
            for tweet in page_slice:
                for tweet_id, _, photo_index, _ in collect_photo_entries(
                    tweet,
                    since=since,
                    until=None,
                ):
                    stable_stem = f"{tweet_id}_{photo_index}"
                    if stable_stem not in existing_stems or not list(out_dir.glob(f"{stable_stem}.*")):
                        page_new_entries += 1

            if page_new_entries == 0:
                consecutive_empty_pages += 1
            else:
                consecutive_empty_pages = 0

            if consecutive_empty_pages >= stop_after_empty_pages:
                break

        if max_tweets is not None and len(collected) >= max_tweets:
            break

        if since:
            page_times = [tweet_time for tweet in page_slice if (tweet_time := parse_tweet_time(tweet))]
            if page_times and min(page_times) < since:
                break

        page = await get_next_page(page)

    return collected, pages_scanned


def merge_records(existing: list[ImageRecord], new_records: list[ImageRecord]) -> list[ImageRecord]:
    merged: dict[str, ImageRecord] = {record.filename: record for record in existing}
    for record in new_records:
        merged[record.filename] = record
    return sorted(merged.values(), key=lambda item: (item.tweet_time, item.filename))


async def run(args: argparse.Namespace) -> int:
    username = normalize_username(args.user)
    out_dir = Path(args.out_dir)
    json_out = Path(args.json_out)
    cookies_file = Path(args.cookies_file)
    since = parse_user_datetime(args.since, is_until=False)
    until = parse_user_datetime(args.until, is_until=True)
    proxy = args.proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")

    if args.max_tweets < 1:
        raise RuntimeError("--max-tweets must be >= 1.")
    if args.stop_after_empty_pages < 1:
        raise RuntimeError("--stop-after-empty-pages must be >= 1.")

    existing_records = load_existing_manifest(json_out)
    existing_by_stem = {record_stem(record.filename) for record in existing_records}

    client = await build_client(args.locale, proxy)
    imported_cookies = import_cookie_header_if_present(
        client,
        args.cookie_header_file,
        cookies_file,
    )
    load_cookies_if_present(client, cookies_file)
    await maybe_login(client, args, cookies_file)

    if not cookies_file.exists():
        eprint(
            "[WARN] Cookies file does not exist yet. "
            "If fetch fails, rerun with --login to create one."
        )
    elif imported_cookies:
        eprint(f"[INFO] Imported cookies from: {Path(args.cookie_header_file).resolve()}")
        eprint(f"[INFO] Saved twikit cookies to: {cookies_file.resolve()}")

    try:
        tweet_limit = None if args.fetch_all else args.max_tweets
        tweets, pages_scanned = await collect_timeline_tweets(
            client,
            username,
            tweet_limit,
            args.tweet_type,
            since=since,
            fetch_all=args.fetch_all,
            existing_stems=existing_by_stem,
            out_dir=out_dir,
            stop_after_empty_pages=args.stop_after_empty_pages,
        )
    except Exception as exc:
        raise RuntimeError(
            "Failed to fetch the timeline with twikit. "
            "Your cookies may be expired, or X may have changed its internal API. "
            "Try rerunning with --login. "
            "If that still fails, use the planned Playwright fallback. "
            f"Root cause: {type(exc).__name__}: {exc!r}"
        ) from exc

    eprint(f"[INFO] Scanned {len(tweets)} tweets from @{username} across {pages_scanned} pages.")
    if args.debug_sample > 0:
        for index, tweet in enumerate(tweets[: args.debug_sample], start=1):
            eprint(f"[DEBUG {index}] {tweet_debug_summary(tweet)}")

    new_records: list[ImageRecord] = []
    skipped_existing = 0
    downloaded = 0
    repaired_manifest_only = 0
    filtered_photo_entries = 0

    for tweet in tweets:
        for tweet_id, tweet_time, photo_index, media_url in collect_photo_entries(
            tweet,
            since=since,
            until=until,
        ):
            filtered_photo_entries += 1
            stable_stem = f"{tweet_id}_{photo_index}"
            matching_local_files = list(out_dir.glob(f"{stable_stem}.*"))
            tweet_time_text = format_tweet_time(tweet_time)

            if stable_stem in existing_by_stem and matching_local_files:
                skipped_existing += 1
                continue

            if stable_stem not in existing_by_stem and matching_local_files:
                new_records.append(
                    ImageRecord(
                        filename=matching_local_files[0].name,
                        tweet_time=tweet_time_text,
                    )
                )
                existing_by_stem.add(stable_stem)
                repaired_manifest_only += 1
                continue

            filename = download_with_extension(
                media_url,
                out_dir,
                tweet_id,
                photo_index,
                args.timeout,
            )

            existing_by_stem.add(stable_stem)
            new_records.append(
                ImageRecord(
                    filename=filename,
                    tweet_time=tweet_time_text,
                )
            )
            downloaded += 1

            if args.download_delay > 0:
                await asyncio.sleep(args.download_delay)

    merged_records = merge_records(existing_records, new_records)
    write_manifest(json_out, merged_records)

    eprint(f"[INFO] Candidate photo entries: {filtered_photo_entries}")
    eprint(f"[INFO] Downloaded new images: {downloaded}")
    eprint(f"[INFO] Repaired manifest-only records: {repaired_manifest_only}")
    eprint(f"[INFO] Skipped existing images: {skipped_existing}")
    eprint(f"[OK] Images saved to: {out_dir.resolve()}")
    eprint(f"[OK] Manifest saved to: {json_out.resolve()}")
    print(
        json.dumps(
            [
                {"filename": record.filename, "tweet_time": record.tweet_time}
                for record in merged_records
            ],
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    args = parse_args()
    try:
        raise SystemExit(asyncio.run(run(args)))
    except KeyboardInterrupt:
        eprint("[WARN] Interrupted by user.")
        raise SystemExit(130)
    except Exception as exc:
        message = str(exc).strip() or f"{type(exc).__name__}: {exc!r}"
        eprint(f"[ERROR] {message}")
        if args.verbose:
            traceback.print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
