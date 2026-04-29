#!/usr/bin/env python3
"""
从萌娘百科「明透」页面解析「原创曲」wikitable，写入 data/asu_music_data.json（保留已有 discography）。

说明：mzh.moegirl.org.cn 对常见爬虫返回 403，且 parse API 可能受限。
用法：
  1) 浏览器打开条目，另存为 HTML（UTF-8），然后：
     python tools/scrape_moegirl_asu_original.py --html path/to/明透.html
  2) 若直连可用（视网络环境）：
     python tools/scrape_moegirl_asu_original.py

列映射：投稿时间、歌曲名称、链接（取表格中 Bilibili 列首个 http(s) 链接；
若无则填 —，需人工对照条目补全）。
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

PAGE_URL = "https://mzh.moegirl.org.cn/%E6%98%8E%E9%80%8F"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "asu_music_data.json"


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://mzh.moegirl.org.cn/",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def cell_text(td) -> str:
    return td.get_text(" ", strip=True)


def first_link(td) -> str | None:
    a = td.find("a", href=True)
    if not a:
        return None
    href = a["href"].strip()
    if href.startswith("//"):
        href = "https:" + href
    if href.startswith(("http://", "https://")):
        return href
    return None


def find_original_song_table(soup: BeautifulSoup):
    for h in soup.find_all(["h2", "h3", "h4"]):
        if "原创曲" not in h.get_text():
            continue
        node = h.find_next_sibling()
        while node and node.name not in ("table", "h2", "h3", "h4"):
            node = node.find_next_sibling()
        if node and node.name == "table":
            return node
    return None


def parse_table(table) -> list[dict]:
    rows_el = table.find_all("tr")
    if not rows_el:
        return []
    header_cells = rows_el[0].find_all(["th", "td"])
    headers = [cell_text(c) for c in header_cells]
    try:
        i_date = headers.index("投稿时间")
        i_title = headers.index("歌曲名称")
        i_bili = headers.index("Bilibili")
    except ValueError as e:
        raise SystemExit(f"表头不符合预期: {headers}") from e

    out: list[dict] = []
    for tr in rows_el[1:]:
        tds = tr.find_all(["td", "th"])
        if len(tds) <= max(i_date, i_title, i_bili):
            continue
        date = cell_text(tds[i_date])
        title = cell_text(tds[i_title])
        href = first_link(tds[i_bili])
        if not date and not title:
            continue
        if href:
            m = re.search(r"(BV[\w]+)", href)
            label = m.group(1) if m and "bilibili.com" in href else (
                "网易云音乐" if "music.163.com" in href else href
            )
            watch = {"url": href, "label": label}
        else:
            watch = None
        out.append({"date": date, "title": title, "watch": watch})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", type=Path, help="本地保存的条目 HTML")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    if args.html:
        html = args.html.read_text(encoding="utf-8", errors="replace")
    else:
        html = fetch(PAGE_URL)

    soup = BeautifulSoup(html, "html.parser")
    table = find_original_song_table(soup)
    if not table:
        raise SystemExit("未找到「原创曲」下的表格")

    rows = parse_table(table)
    existing: dict = {}
    if args.out.exists():
        try:
            existing = json.loads(args.out.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    payload = {
        "source": PAGE_URL,
        "section": "作品概览 · 原创曲",
        "note": "由 tools/scrape_moegirl_asu_original.py 从页面解析。",
        "columns": ["投稿时间", "歌曲名称", "链接"],
        "rows": rows,
    }
    if "discography" in existing:
        payload["discography"] = existing["discography"]
    if "updated" in existing:
        payload["updated"] = existing["updated"]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} rows -> {args.out}")


if __name__ == "__main__":
    main()
