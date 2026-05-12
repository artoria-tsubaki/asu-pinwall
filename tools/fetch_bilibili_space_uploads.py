#!/usr/bin/env python3
"""Fetch all uploads from a Bilibili user space and emit timeline-style JSON."""

from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": "https://space.bilibili.com/",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def _video_url(bvid: str) -> str:
    return f"https://www.bilibili.com/video/{bvid}"


def _caption_anchor(url: str, title: str) -> str:
    esc_title = html.escape(title, quote=True)
    esc_url = html.escape(url, quote=True)
    return f'<a href="{esc_url}" target="_blank" rel="noopener noreferrer">{esc_title}</a>'


def _item_from_arc(v: dict) -> dict:
    bvid = v.get("bvid") or ""
    title = (v.get("title") or "").strip()
    url = _video_url(bvid)
    pub = int(v.get("pubdate") or 0)
    cst = timezone(timedelta(hours=8))
    dt = datetime.fromtimestamp(pub, tz=cst)
    y, m, d = dt.year, dt.month, dt.day
    return {
        "media": {
            "url": url,
            "caption": _caption_anchor(url, title),
        },
        "start_date": {
            "year": str(y),
            "month": str(m),
            "day": str(d),
        },
        "text": {
            "headline": title,
            "text": "",
        },
    }


def fetch_all(mid: int, order: str = "pubdate", page_size: int = 30) -> list[dict]:
    out: list[dict] = []
    pn = 1
    total = None

    while True:
        q = urllib.parse.urlencode(
            {"mid": mid, "ps": page_size, "pn": pn, "order": order}
        )
        api = f"https://api.bilibili.com/x/space/arc/list?{q}"
        data = _http_get_json(api)
        if data.get("code") != 0:
            raise RuntimeError(f"arc/list failed: {data}")

        body = data.get("data") or {}
        archives = body.get("archives") or []
        page = body.get("page") or {}
        if total is None:
            total = int(page.get("count") or 0)

        if not archives:
            break

        for v in archives:
            out.append(_item_from_arc(v))

        if total and len(out) >= total:
            break
        if len(archives) < page_size:
            break
        pn += 1
        time.sleep(0.35)

    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mid", type=int, default=1634470651)
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()
    mid = args.mid
    items = fetch_all(mid)
    path = args.out or re.sub(r"[^\w\-]+", "_", f"bilibili_uploads_mid{mid}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"wrote {len(items)} items -> {path}")


if __name__ == "__main__":
    main()
