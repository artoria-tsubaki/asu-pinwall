#!/usr/bin/env python3
"""
Generate a per-date ASU tweet aggregation for every covered_by row.

The output format follows data/tweets_ASU_virtual_from_covered_by_note_check.json
but uses every row from data/bilibili_season_1741301_49333_covered_by.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional


DEFAULT_USER = "ASU_virtual"
DEFAULT_SOURCE = "data/bilibili_season_1741301_49333_covered_by.json"
DEFAULT_OUTPUT = "data/tweets_ASU_virtual_from_covered_by.json"
DEFAULT_FILTER = "all covered_by rows"
STRICT_HIT_DATE_START = "2022-03-08"
STRICT_HIT_DATE_END = "2024-03-23"


def quote_phrase(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_query(
    username: str,
    keywords: list[str],
    phrases: list[str],
    include_retweets: bool,
    include_replies: bool,
    extra_query: Optional[str],
) -> str:
    terms: list[str] = []
    terms.extend(k.strip() for k in keywords if k and k.strip())
    terms.extend(quote_phrase(p.strip()) for p in phrases if p and p.strip())

    query_parts = [f"from:{username}"]
    if terms:
        content_query = terms[0] if len(terms) == 1 else "(" + " OR ".join(terms) + ")"
        query_parts.append(content_query)
    if not include_retweets:
        query_parts.append("-is:retweet")
    if not include_replies:
        query_parts.append("-is:reply")
    if extra_query and extra_query.strip():
        query_parts.append(extra_query.strip())

    return " ".join(query_parts)


def coerce_entities(entities: Any) -> Any:
    if entities is None:
        return None
    if isinstance(entities, dict):
        return entities
    return getattr(entities, "data", None) or {}


def media_to_dict(media: Any) -> dict[str, Any]:
    return {
        "media_key": getattr(media, "media_key", None),
        "type": getattr(media, "type", None),
        "url": getattr(media, "url", None),
        "preview_image_url": getattr(media, "preview_image_url", None),
        "width": getattr(media, "width", None),
        "height": getattr(media, "height", None),
        "public_metrics": getattr(media, "public_metrics", None),
        "alt_text": getattr(media, "alt_text", None),
    }


def referenced_tweet_to_dict(item: Any) -> dict[str, Any]:
    return {
        "id": str(getattr(item, "id", "")),
        "type": getattr(item, "type", None),
    }


def user_to_dict(user: Any) -> dict[str, Any]:
    return {
        "id": str(getattr(user, "id", "")),
        "name": getattr(user, "name", None),
        "username": getattr(user, "username", None),
    }


def tweet_to_dict(
    tweet: Any,
    username: str,
    media_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    attachments = tweet.attachments or {}
    media_keys = attachments.get("media_keys", []) if attachments else []
    return {
        "id": str(tweet.id),
        "url": f"https://twitter.com/{username}/status/{tweet.id}",
        "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
        "text": tweet.text,
        "lang": getattr(tweet, "lang", None),
        "source": getattr(tweet, "source", None),
        "author_id": str(getattr(tweet, "author_id", "")) if getattr(tweet, "author_id", None) else None,
        "conversation_id": (
            str(tweet.conversation_id) if getattr(tweet, "conversation_id", None) else None
        ),
        "in_reply_to_user_id": (
            str(tweet.in_reply_to_user_id)
            if getattr(tweet, "in_reply_to_user_id", None)
            else None
        ),
        "possibly_sensitive": getattr(tweet, "possibly_sensitive", None),
        "public_metrics": getattr(tweet, "public_metrics", None),
        "entities": coerce_entities(getattr(tweet, "entities", None)),
        "referenced_tweets": [
            referenced_tweet_to_dict(item)
            for item in (getattr(tweet, "referenced_tweets", None) or [])
        ],
        "media": [media_map[key] for key in media_keys if key in media_map],
    }


def fetch_tweets(
    bearer_token: str,
    username: str,
    query: str,
    search_scope: str,
    start_time: Optional[datetime],
    end_time: Optional[datetime],
    limit: int,
) -> list[dict[str, Any]]:
    try:
        import tweepy
    except ImportError:
        print("[ERROR] Please install tweepy first: pip install tweepy", file=sys.stderr)
        sys.exit(1)

    client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)

    user_resp = client.get_user(username=username)
    if not user_resp.data:
        print(f"[ERROR] User not found: @{username}", file=sys.stderr)
        sys.exit(1)

    page_size = min(limit, 500 if search_scope == "all" else 100)
    request_kwargs: dict[str, Any] = {
        "query": query,
        "max_results": page_size,
        "tweet_fields": [
            "id",
            "text",
            "created_at",
            "attachments",
            "entities",
            "public_metrics",
            "conversation_id",
            "in_reply_to_user_id",
            "lang",
            "possibly_sensitive",
            "referenced_tweets",
            "source",
            "author_id",
        ],
        "expansions": ["attachments.media_keys", "author_id"],
        "media_fields": [
            "media_key",
            "type",
            "url",
            "preview_image_url",
            "width",
            "height",
            "public_metrics",
            "alt_text",
        ],
        "user_fields": ["id", "name", "username"],
    }
    if start_time is not None:
        request_kwargs["start_time"] = start_time
    if end_time is not None:
        request_kwargs["end_time"] = end_time

    search_method = client.search_all_tweets if search_scope == "all" else client.search_recent_tweets
    rows: list[dict[str, Any]] = []
    paginator = tweepy.Paginator(search_method, **request_kwargs)

    for response in paginator:
        includes = getattr(response, "includes", None) or {}
        media_map = {
            item.media_key: media_to_dict(item)
            for item in includes.get("media", [])
            if getattr(item, "media_key", None)
        }
        users = [user_to_dict(item) for item in includes.get("users", [])]

        for tweet in response.data or []:
            row = tweet_to_dict(tweet, username, media_map)
            row["matched_query"] = query
            row["matched_users"] = users
            rows.append(row)
            if len(rows) >= limit:
                return rows

    return rows


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def normalize_date_str(value: str) -> str:
    raw = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw

    cn_match = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw)
    if cn_match:
        year, month, day = cn_match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    raise ValueError(f"Unsupported date format: {value!r}")


def read_token(token_arg: Optional[str], project_root: Path) -> Optional[str]:
    if token_arg:
        return token_arg

    env_token = os.environ.get("TWITTER_TOKEN")
    if env_token:
        return env_token

    token_path = project_root / "token" / "TWITTER_TOKEN.json"
    if not token_path.exists():
        return None

    payload = load_json(token_path)
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, dict):
        for key in ("token", "bearer_token", "TWITTER_TOKEN"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def iter_candidate_cache_paths(project_root: Path, date_str: str) -> Iterable[Path]:
    candidates = [
        project_root / "data" / f"tweets_{DEFAULT_USER}_{date_str}.json",
        project_root / "data" / "tweets" / f"tweets_{DEFAULT_USER}_{date_str}.json",
    ]

    ymd = datetime.strptime(date_str, "%Y-%m-%d").date()
    candidates.append(
        project_root
        / "data"
        / f"tweets_{DEFAULT_USER}_{ymd - timedelta(days=1)}_{ymd + timedelta(days=1)}.json"
    )
    return candidates


def filter_tweets_by_created_at(rows: list[dict[str, Any]], date_str: str) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for row in rows:
        created_at = str(row.get("created_at") or "")
        if created_at.startswith(date_str):
            filtered.append(row)
    return filtered


def normalize_results_payload(payload: Any, date_str: str) -> Optional[list[dict[str, Any]]]:
    if isinstance(payload, dict):
        if "results" in payload and isinstance(payload["results"], list):
            for item in payload["results"]:
                if str(item.get("date")) == date_str and isinstance(item.get("tweets"), list):
                    return item["tweets"]
        if str(payload.get("date")) == date_str and isinstance(payload.get("tweets"), list):
            return payload["tweets"]
        if isinstance(payload.get("tweets"), list):
            filtered = filter_tweets_by_created_at(payload["tweets"], date_str)
            if filtered:
                return filtered

    if isinstance(payload, list):
        filtered = filter_tweets_by_created_at(payload, date_str)
        if filtered:
            return filtered
    return None


def load_cached_tweets_for_date(project_root: Path, date_str: str) -> Optional[list[dict[str, Any]]]:
    for path in iter_candidate_cache_paths(project_root, date_str):
        if not path.exists():
            continue
        try:
            tweets = normalize_results_payload(load_json(path), date_str)
        except Exception:
            continue
        if tweets is not None:
            return tweets

    selected_files = [
        project_root / "data" / "tweets_ASU_virtual_selected_dates.json",
        project_root / "data" / "tweets_ASU_virtual_selected_dates_2023-10_to_2024-02.json",
        project_root / "data" / "tweets_ASU_virtual_from_covered_by_note_check.json",
    ]
    for path in selected_files:
        if not path.exists():
            continue
        payload = load_json(path)
        tweets = normalize_results_payload(payload, date_str)
        if tweets is not None:
            return tweets

    return None


def unique_sort_tweets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        tweet_id = str(row.get("id") or "")
        if tweet_id and tweet_id not in merged:
            merged[tweet_id] = row

    return sorted(merged.values(), key=lambda item: str(item.get("created_at") or ""))


def is_tco_only_line(line: str) -> bool:
    return bool(re.fullmatch(r"https://t\.co/\S+", line.strip()))


def line_has_trailing_tco(line: str) -> bool:
    return bool(re.search(r"https://t\.co/\S+\s*$", line.strip()))


def has_photo_shortlink(tweet: dict[str, Any]) -> bool:
    entities = tweet.get("entities")
    if not isinstance(entities, dict):
        return False

    for url_item in entities.get("urls", []):
        if not isinstance(url_item, dict):
            continue
        expanded_url = str(url_item.get("expanded_url") or "")
        media_key = str(url_item.get("media_key") or "")
        if "/photo/" in expanded_url or media_key:
            return True
    return False


def is_strict_hit_tweet(tweet: dict[str, Any]) -> bool:
    text = tweet.get("text")
    if not isinstance(text, str):
        return False

    stripped = text.strip()
    if "https://t.co/" not in stripped:
        return False

    lines = [line.strip() for line in stripped.splitlines()]
    non_empty_lines = [line for line in lines if line]
    if len(non_empty_lines) < 4:
        return False

    if not is_tco_only_line(non_empty_lines[0]):
        return False

    if not line_has_trailing_tco(non_empty_lines[-1]):
        return False

    if not has_photo_shortlink(tweet):
        return False

    body_lines = non_empty_lines[1:-1]
    if len(body_lines) < 2:
        return False

    body_text = "\n".join(lines[1:-1]).strip()
    body_segments = [segment.strip() for segment in re.split(r"\n\s*\n", body_text) if segment.strip()]
    return len(body_segments) >= 2


def is_loose_hit_tweet(tweet: dict[str, Any]) -> bool:
    text = tweet.get("text")
    if not isinstance(text, str):
        return False

    stripped = text.strip()
    if "https://t.co/" not in stripped:
        return False

    body = re.sub(r"https://t\.co/\S+", " ", stripped)
    body = re.sub(r"\s+", " ", body).strip()
    return len(body) >= 10


def find_hit_index(tweets: list[dict[str, Any]], date_str: str) -> Optional[int]:
    use_strict_rule = STRICT_HIT_DATE_START <= date_str <= STRICT_HIT_DATE_END
    for idx, tweet in enumerate(tweets):
        matched = is_strict_hit_tweet(tweet) if use_strict_rule else is_loose_hit_tweet(tweet)
        if matched:
            return idx
    return None


def fetch_day_tweets(
    *,
    token: str,
    date_str: str,
    query: str,
    limit: int,
    delay: float,
) -> list[dict[str, Any]]:
    start_time = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_time = start_time + timedelta(days=1)
    rows = fetch_tweets(
        bearer_token=token,
        username=DEFAULT_USER,
        query=query,
        search_scope="all",
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    if delay > 0:
        time.sleep(delay)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate tweets_ASU_virtual_from_covered_by.json from covered_by rows.\n\n"
            "Input priority: --dates > --source-json > --source (file).\n"
            "If none is given, falls back to the default source file."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        default=None,
        help=(
            f"Source covered_by JSON path (default: {DEFAULT_SOURCE}). "
            "Ignored when --dates or --source-json is provided."
        ),
    )
    parser.add_argument(
        "--source-json",
        default=None,
        metavar="JSON",
        help=(
            "Inline JSON string to use as the data source instead of a file. "
            'Accepts: (1) the same object structure as the source file with a "rows" array, '
            '(2) a JSON array of row objects with a "date" field, '
            'or (3) a JSON array of date strings e.g. \'["2022-01-01","2022-03-08"]\'.'
        ),
    )
    parser.add_argument(
        "--dates",
        nargs="+",
        default=None,
        metavar="DATE",
        help=(
            "One or more dates to process directly, in YYYY-MM-DD format. "
            "Example: --dates 2022-01-01 2022-03-08 2023-06-15"
        ),
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output JSON path.")
    parser.add_argument("--token", default=None, help="Bearer token. Falls back to env or token file.")
    parser.add_argument(
        "--cache-dir",
        default="data/tweets",
        help="Directory to store fetched per-day cache files.",
    )
    parser.add_argument(
        "--limit-per-day",
        type=int,
        default=100,
        help="Maximum tweets fetched per date.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.1,
        help="Delay in seconds after each fetch.",
    )
    parser.add_argument(
        "--refresh",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Ignore local caches and refetch every date.",
    )
    return parser.parse_args()


def resolve_rows(args: argparse.Namespace, project_root: Path) -> tuple[list[dict[str, Any]], str]:
    """Return (rows, source_label) from whichever input mode is active."""
    if args.dates:
        rows: list[dict[str, Any]] = [{"date": d} for d in args.dates]
        return rows, "--dates"

    if args.source_json:
        try:
            payload = json.loads(args.source_json)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"[ERROR] --source-json is not valid JSON: {exc}") from exc

        if isinstance(payload, list):
            if payload and isinstance(payload[0], str):
                rows = [{"date": d} for d in payload]
            else:
                rows = [item for item in payload if isinstance(item, dict)]
        elif isinstance(payload, dict):
            rows = payload.get("rows", [])
            if not isinstance(rows, list):
                raise SystemExit("[ERROR] --source-json object does not contain a valid 'rows' array.")
        else:
            raise SystemExit("[ERROR] --source-json must be a JSON object or array.")

        return rows, "--source-json"

    source = args.source or DEFAULT_SOURCE
    source_path = (project_root / source).resolve()
    source_payload = load_json(source_path)
    rows = source_payload.get("rows", [])
    if not isinstance(rows, list):
        raise SystemExit("[ERROR] Source file does not contain a rows array.")
    return rows, source.replace("\\", "/")


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    args = parse_args()
    project_root = Path(__file__).resolve().parent.parent
    output_path = (project_root / args.output).resolve()
    cache_dir = (project_root / args.cache_dir).resolve()

    rows, source_label = resolve_rows(args, project_root)

    query = build_query(
        username=DEFAULT_USER,
        keywords=[],
        phrases=[],
        include_retweets=False,
        include_replies=False,
        extra_query=None,
    )

    token = read_token(args.token, project_root)
    results: list[dict[str, Any]] = []
    total_count = 0

    for covered_by in rows:
        raw_date = str(covered_by.get("date") or "")
        if not raw_date:
            continue
        date_str = normalize_date_str(raw_date)

        tweets: Optional[list[dict[str, Any]]] = None
        if not args.refresh:
            tweets = load_cached_tweets_for_date(project_root, date_str)

        cache_path = cache_dir / f"tweets_{DEFAULT_USER}_{date_str}.json"
        if tweets is None and cache_path.exists() and not args.refresh:
            tweets = normalize_results_payload(load_json(cache_path), date_str)

        if tweets is None:
            if not token:
                raise SystemExit(
                    f"[ERROR] Missing token and no cache available for {date_str}. "
                    "Provide --token, set TWITTER_TOKEN, or add token/TWITTER_TOKEN.json."
                )
            print(f"[INFO] Fetching tweets for {date_str}", file=sys.stderr)
            tweets = fetch_day_tweets(
                token=token,
                date_str=date_str,
                query=query,
                limit=args.limit_per_day,
                delay=args.delay,
            )
            cache_payload = {
                "user": DEFAULT_USER,
                "query": query,
                "search_scope": "all",
                "start_time": f"{date_str}T00:00:00+00:00",
                "end_time": (
                    datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    + timedelta(days=1)
                ).isoformat(),
                "count": len(tweets),
                "tweets": tweets,
            }
            save_json(cache_path, cache_payload)

        day_tweets = unique_sort_tweets(list(tweets or []))
        entry: dict[str, Any] = {
            "date": date_str,
            "covered_by": covered_by,
            "count": len(day_tweets),
            "tweets": day_tweets,
        }
        hit_idx = find_hit_index(day_tweets, date_str)
        if hit_idx is not None:
            entry["status"] = "hit"
            entry["idx"] = hit_idx

        results.append(entry)
        total_count += len(day_tweets)

    payload = {
        "user": DEFAULT_USER,
        "query": query,
        "source_file": source_label,
        "filter": DEFAULT_FILTER,
        "days": len(results),
        "total_count": total_count,
        "results": results,
    }

    save_json(output_path, payload)
    print(f"[OK] Saved {len(results)} dates to {output_path}", file=sys.stderr)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
