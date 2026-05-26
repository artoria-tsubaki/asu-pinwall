#!/usr/bin/env python3
"""Fetch a Bilibili season collection and write its videos to a JSON table."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen


TZ = timezone(timedelta(hours=8))
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
ROOT = Path(__file__).resolve().parents[1]


def parse_season_url(value: str) -> tuple[int, int]:
    match = re.search(r"space\.bilibili\.com/(\d+)/lists/(\d+)", value)
    if not match:
        raise argparse.ArgumentTypeError(
            "Expected a URL like https://space.bilibili.com/1741301/lists/49333?type=season"
        )
    mid, season_id = match.groups()
    return int(mid), int(season_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch a Bilibili season collection and write data/bilibili_season_1741301_49333.json."
    )
    parser.add_argument(
        "--url",
        default="https://space.bilibili.com/1741301/lists/49333?type=season",
        help="Bilibili season collection URL.",
    )
    parser.add_argument("--mid", type=int, default=None, help="Bilibili uploader mid.")
    parser.add_argument("--season-id", type=int, default=None, help="Bilibili season collection id.")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "bilibili_season_1741301_49333.json",
        help="Output JSON path.",
    )
    parser.add_argument(
        "--section",
        default="Bilibili 投稿合集（season）",
        help="Section title stored in the output JSON.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=30,
        help="Collection page size. Bilibili season collections usually paginate at 30.",
    )
    return parser.parse_args()


def fetch_json(url: str, referer: str) -> dict:
    req = Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": referer,
        },
    )
    with urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def fetch_season_archives(mid: int, season_id: int, page_size: int) -> list[dict]:
    referer = f"https://space.bilibili.com/{mid}/lists/{season_id}?type=season"
    archives: list[dict] = []
    page_num = 1
    total = None

    while True:
        query = urllib.parse.urlencode(
            {
                "mid": mid,
                "season_id": season_id,
                "page_num": page_num,
                "page_size": page_size,
                "sort_reverse": "false",
            }
        )
        url = f"https://api.bilibili.com/x/polymer/web-space/seasons_archives_list?{query}"
        raw = fetch_json(url, referer)
        if raw.get("code") != 0:
            raise SystemExit(raw)

        data = raw.get("data") or {}
        page_archives = data.get("archives") or []
        page = data.get("page") or {}

        if total is None:
            total = int(page.get("total") or 0)

        if not page_archives:
            break

        archives.extend(page_archives)

        if total and len(archives) >= total:
            break
        if len(page_archives) < page_size:
            break

        page_num += 1
        time.sleep(0.35)

    return archives


def to_rows(archives: list[dict]) -> list[dict]:
    rows = []
    for archive in archives:
        pub = datetime.fromtimestamp(int(archive["pubdate"]), tz=TZ)
        bvid = archive["bvid"]
        rows.append(
            {
                "date": f"{pub.year}年{pub.month}月{pub.day}日",
                "title": archive["title"],
                "watch": {
                    "url": f"https://www.bilibili.com/video/{bvid}",
                    "label": bvid,
                },
            }
        )
    return rows


def load_existing(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def main() -> None:
    args = parse_args()
    url_mid, url_season_id = parse_season_url(args.url)
    mid = args.mid or url_mid
    season_id = args.season_id or url_season_id
    source = f"https://space.bilibili.com/{mid}/lists/{season_id}?type=season"

    archives = fetch_season_archives(mid, season_id, args.page_size)
    rows = to_rows(archives)

    existing = load_existing(args.out)
    payload = {
        "source": source,
        "section": args.section,
        "note": f"对照 B 站投稿合集 season_id={season_id} 自动抓取，投稿时间为稿件 pubdate（UTC+8）。",
        "updated": datetime.now(TZ).date().isoformat(),
        "columns": ["投稿时间", "歌曲名称", "链接"],
        "rows": rows,
    }
    if "discography" in existing:
        payload["discography"] = existing["discography"]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"{len(rows)} rows -> {args.out}")


if __name__ == "__main__":
    main()
