#!/usr/bin/env python3
"""
Fetch archived X/Twitter image tweets for a user from the Wayback Machine.

Workflow:
1. Query the Wayback CDX API for archived status URLs.
2. Fetch each archived tweet page.
3. Extract direct `pbs.twimg.com/media/` image URLs and the tweet timestamp.
4. Normalize each image URL to `name=orig`.
5. Download images and incrementally merge a flat manifest:

[
  {
    "filename": "1770758604271899027_1.jpg",
    "tweet_time": "2024-03-21T10:25:25Z"
  }
]

Example:
  C:\Users\Artor\AppData\Local\Programs\Python\Python314\python.exe ^
    tools/fetch_x_images_wayback.py ^
    --user ASU_virtual ^
    --since 2023-12-19 ^
    --until 2024-03-21
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_OUT_DIR = Path("x_images") / "ASU_virtual"
DEFAULT_JSON_OUT = Path("data") / "asu_virtual_x_images.json"
WAYBACK_CDX_URL = "https://web.archive.org/cdx/search/cdx"
WAYBACK_WEB_PREFIX = "https://web.archive.org/web"
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
CREATED_AT_PATTERNS = (
    re.compile(r'"created_at"\s*:\s*"([^"]+)"'),
    re.compile(r"&quot;created_at&quot;\s*:\s*&quot;([^&]+)&quot;"),
    re.compile(r'"dateCreated"\s*:\s*"([^"]+)"'),
    re.compile(r'article:published_time"\s+content="([^"]+)"'),
    re.compile(r'name="twitter:label1"\s+content="Time"[^>]*name="twitter:data1"\s+content="([^"]+)"'),
)
MEDIA_URL_PATTERNS = (
    re.compile(r'https://pbs\.twimg\.com/media/[A-Za-z0-9_\-\.]+(?:\?[^\s"\'<>&\\]+)?'),
    re.compile(r'https:\\/\\/pbs\.twimg\.com\\/media\\/[A-Za-z0-9_\-\.]+(?:\\?[^\s"\'<>&\\]+)?'),
)
STATUS_ID_PATTERN = re.compile(r"/status/(\d+)")


@dataclass(frozen=True)
class ImageRecord:
    filename: str
    tweet_time: str


@dataclass(frozen=True)
class CdxRecord:
    archived_timestamp: str
    original_url: str
    tweet_id: str


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch archived image tweets for an X/Twitter user through the "
            "Wayback Machine and save direct media files locally."
        )
    )
    parser.add_argument("--user", required=True, help="X username without @.")
    parser.add_argument(
        "--since",
        required=True,
        help="Keep tweets on/after this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--until",
        required=True,
        help="Keep tweets on/before this date (YYYY-MM-DD).",
    )
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
        "--cdx-limit",
        type=int,
        default=150000,
        help="Maximum number of CDX rows to request. Default: 150000",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Network timeout in seconds. Default: 30",
    )
    parser.add_argument(
        "--download-delay",
        type=float,
        default=0.0,
        help="Optional delay between image downloads in seconds. Default: 0",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report records without downloading or writing files.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed exception information for debugging.",
    )
    return parser.parse_args()


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_user_date(value: str, *, is_until: bool) -> datetime:
    parsed_date = datetime.strptime(value.strip(), "%Y-%m-%d").date()
    if is_until:
        return datetime(
            parsed_date.year,
            parsed_date.month,
            parsed_date.day,
            23,
            59,
            59,
            999999,
            tzinfo=timezone.utc,
        )
    return datetime(
        parsed_date.year,
        parsed_date.month,
        parsed_date.day,
        tzinfo=timezone.utc,
    )


def format_tweet_time(value: datetime) -> str:
    return ensure_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def write_manifest(path: Path, records: Iterable[ImageRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {"filename": record.filename, "tweet_time": record.tweet_time}
        for record in records
    ]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def merge_records(existing: list[ImageRecord], new_records: list[ImageRecord]) -> list[ImageRecord]:
    merged: dict[str, ImageRecord] = {record.filename: record for record in existing}
    for record in new_records:
        merged[record.filename] = record
    return sorted(merged.values(), key=lambda item: (item.tweet_time, item.filename))


def record_stem(filename: str) -> str:
    return Path(filename).stem


def normalize_username(username: str) -> str:
    return username.lstrip("@").strip()


def fetch_text(url: str, timeout: int) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def fetch_bytes(url: str, timeout: int) -> tuple[bytes, Optional[str]]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://x.com/",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        return response.read(), content_type or None


def build_cdx_url(username: str, since: str, until: str, limit: int) -> str:
    params = {
        "url": f"https://twitter.com/{username}/status/*",
        "limit": str(limit),
        "from": since.replace("-", ""),
        "to": until.replace("-", ""),
        "output": "json",
        "collapse": "urlkey",
    }
    return f"{WAYBACK_CDX_URL}?{urllib.parse.urlencode(params)}"


def parse_cdx_payload(payload: str) -> list[CdxRecord]:
    data = json.loads(payload)
    if not isinstance(data, list) or not data:
        return []

    header = data[0]
    if not isinstance(header, list):
        raise ValueError("Unexpected CDX payload: missing header row.")

    index_by_name = {str(name): idx for idx, name in enumerate(header)}
    required_fields = ("timestamp", "original")
    missing_fields = [field for field in required_fields if field not in index_by_name]
    if missing_fields:
        raise ValueError(f"CDX payload missing required columns: {', '.join(missing_fields)}")

    records: list[CdxRecord] = []
    seen_tweet_ids: set[str] = set()

    for row in data[1:]:
        if not isinstance(row, list):
            continue
        try:
            archived_timestamp = str(row[index_by_name["timestamp"]]).strip()
            original_url = str(row[index_by_name["original"]]).strip()
        except (IndexError, TypeError):
            continue
        match = STATUS_ID_PATTERN.search(original_url)
        if not match:
            continue
        tweet_id = match.group(1)
        if tweet_id in seen_tweet_ids:
            continue
        seen_tweet_ids.add(tweet_id)
        records.append(
            CdxRecord(
                archived_timestamp=archived_timestamp,
                original_url=original_url,
                tweet_id=tweet_id,
            )
        )
    return records


def build_wayback_page_urls(record: CdxRecord) -> list[str]:
    encoded_original = urllib.parse.quote(record.original_url, safe=":/?&=%")
    return [
        f"{WAYBACK_WEB_PREFIX}/{record.archived_timestamp}id_/{encoded_original}",
        f"{WAYBACK_WEB_PREFIX}/{record.archived_timestamp}/{encoded_original}",
    ]


def fetch_archived_tweet_html(record: CdxRecord, timeout: int) -> str:
    last_error: Optional[Exception] = None
    for url in build_wayback_page_urls(record):
        try:
            return fetch_text(url, timeout)
        except Exception as exc:
            last_error = exc
    if last_error is None:
        raise RuntimeError(f"Failed to fetch archived tweet page for {record.original_url}")
    raise last_error


def normalize_media_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

    query["name"] = ["orig"]

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


def infer_extension_from_content_type(content_type: Optional[str]) -> Optional[str]:
    if not content_type:
        return None
    return CONTENT_TYPE_TO_EXT.get(content_type)


def resolve_filename(tweet_id: str, index: int, url: str, content_type: Optional[str]) -> str:
    ext = infer_extension_from_url(url) or infer_extension_from_content_type(content_type) or "jpg"
    ext = "jpg" if ext == "jpeg" else ext
    return f"{tweet_id}_{index}.{ext}"


def decode_created_at_candidate(value: str) -> str:
    candidate = html.unescape(value).strip()
    candidate = candidate.replace("\\/", "/")
    try:
        candidate = json.loads(f'"{candidate}"')
    except json.JSONDecodeError:
        pass
    return candidate.strip()


def parse_datetime_candidate(value: str) -> Optional[datetime]:
    candidate = decode_created_at_candidate(value)
    if not candidate:
        return None

    normalized = candidate.replace("Z", "+00:00")
    iso_candidate = normalized
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2})", iso_candidate):
        return ensure_utc(datetime.fromisoformat(iso_candidate))

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
        return ensure_utc(datetime.fromisoformat(candidate))

    for pattern in (
        "%a %b %d %H:%M:%S %z %Y",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            parsed = datetime.strptime(candidate, pattern)
            return ensure_utc(parsed)
        except ValueError:
            continue
    return None


def extract_tweet_time_from_html(document: str) -> Optional[datetime]:
    for pattern in CREATED_AT_PATTERNS:
        for match in pattern.finditer(document):
            parsed = parse_datetime_candidate(match.group(1))
            if parsed is not None:
                return parsed
    return None


def normalize_media_match(raw_url: str) -> Optional[str]:
    url = html.unescape(raw_url.strip())
    url = url.replace("\\/", "/")
    url = url.rstrip("\\")
    if not url.startswith("https://pbs.twimg.com/media/"):
        return None

    parsed = urllib.parse.urlparse(url)
    if "/media/" not in parsed.path:
        return None

    if not infer_extension_from_url(url):
        return None

    return normalize_media_url(url)


def extract_media_urls(document: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    for pattern in MEDIA_URL_PATTERNS:
        for match in pattern.finditer(document):
            normalized = normalize_media_match(match.group(0))
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            candidates.append(normalized)
    return candidates


def parse_wayback_timestamp(value: str) -> datetime:
    parsed = datetime.strptime(value, "%Y%m%d%H%M%S")
    return parsed.replace(tzinfo=timezone.utc)


def download_media(url: str, out_dir: Path, tweet_id: str, index: int, timeout: int) -> str:
    payload, content_type = fetch_bytes(url, timeout)
    filename = resolve_filename(tweet_id, index, url, content_type)
    destination = out_dir / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "wb") as handle:
        handle.write(payload)
    return filename


def run(args: argparse.Namespace) -> int:
    username = normalize_username(args.user)
    since = parse_user_date(args.since, is_until=False)
    until = parse_user_date(args.until, is_until=True)
    if until < since:
        raise RuntimeError("--until must be on or after --since.")
    if args.cdx_limit < 1:
        raise RuntimeError("--cdx-limit must be >= 1.")
    if args.timeout < 1:
        raise RuntimeError("--timeout must be >= 1.")
    if args.download_delay < 0:
        raise RuntimeError("--download-delay must be >= 0.")

    out_dir = Path(args.out_dir)
    json_out = Path(args.json_out)
    existing_records = load_existing_manifest(json_out)
    existing_by_stem = {record_stem(record.filename) for record in existing_records}

    cdx_url = build_cdx_url(username, args.since, args.until, args.cdx_limit)
    eprint(f"[INFO] CDX query: {cdx_url}")
    cdx_records = parse_cdx_payload(fetch_text(cdx_url, args.timeout))
    eprint(f"[INFO] CDX tweet candidates: {len(cdx_records)}")

    new_records: list[ImageRecord] = []
    scanned_pages = 0
    tweets_with_images = 0
    skipped_existing = 0
    downloaded = 0
    repaired_manifest_only = 0
    skipped_out_of_range = 0
    page_failures = 0

    for record in cdx_records:
        scanned_pages += 1
        try:
            document = fetch_archived_tweet_html(record, args.timeout)
        except Exception as exc:
            page_failures += 1
            eprint(f"[WARN] Failed to fetch archived tweet {record.tweet_id}: {exc}")
            continue

        media_urls = extract_media_urls(document)
        if not media_urls:
            continue

        tweets_with_images += 1
        tweet_time = extract_tweet_time_from_html(document) or parse_wayback_timestamp(record.archived_timestamp)
        if not within_range(tweet_time, since=since, until=until):
            skipped_out_of_range += 1
            continue
        tweet_time_text = format_tweet_time(tweet_time)

        for photo_index, media_url in enumerate(media_urls, start=1):
            stable_stem = f"{record.tweet_id}_{photo_index}"
            matching_local_files = list(out_dir.glob(f"{stable_stem}.*"))

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

            if args.dry_run:
                filename = resolve_filename(record.tweet_id, photo_index, media_url, None)
            else:
                filename = download_media(
                    media_url,
                    out_dir,
                    record.tweet_id,
                    photo_index,
                    args.timeout,
                )
                downloaded += 1
                if args.download_delay > 0:
                    time.sleep(args.download_delay)

            existing_by_stem.add(stable_stem)
            new_records.append(ImageRecord(filename=filename, tweet_time=tweet_time_text))

    merged_records = merge_records(existing_records, new_records)

    if not args.dry_run:
        write_manifest(json_out, merged_records)

    eprint(f"[INFO] Archived pages scanned: {scanned_pages}")
    eprint(f"[INFO] Archived pages with images: {tweets_with_images}")
    eprint(f"[INFO] Downloaded new images: {downloaded}")
    eprint(f"[INFO] Repaired manifest-only records: {repaired_manifest_only}")
    eprint(f"[INFO] Skipped existing images: {skipped_existing}")
    eprint(f"[INFO] Skipped out-of-range tweets: {skipped_out_of_range}")
    eprint(f"[INFO] Page fetch failures: {page_failures}")
    if args.dry_run:
        eprint("[OK] Dry run complete. No files were written.")
    else:
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
        raise SystemExit(run(args))
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
