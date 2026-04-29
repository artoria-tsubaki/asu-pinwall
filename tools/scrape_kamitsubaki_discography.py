#!/usr/bin/env python3
"""
从 KAMITSUBAKI discography 页面抓取 .disco-main__detail__img__thumbnail 内的图片，
并沿分页导航继续抓取。

说明：该站点的 HTML 使用 li.prev / li.next，没有 class=\"pre\"。
默认跟随 li.prev > a（rel=prev，指向较旧的作品），直到 li.prev 内无链接。
若需从新到旧以外的方向，可使用 --nav next。

每站写入一条记录：Date（dl.ttl 内 span）、Title（dt 下 h1）、Desc（div.desc 内 p）、
src（本地下载的相对 JSON 旁路径；单张为字符串，多张为字符串数组，失败为 null）。
运行结束后写入 --json 指定的 discography.json（默认同目录）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

DEFAULT_START = "https://kamitsubaki.jp/discography/asu/9128/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as f:
        f.write(resp.read())


def post_id_from_url(url: str) -> str:
    m = re.search(r"/(\d+)/?$", url.rstrip())
    return m.group(1) if m else re.sub(r"\W+", "_", urlparse(url).path.strip("/"))


def extract_date_title_desc(soup: BeautifulSoup) -> tuple[str | None, str | None, str | None]:
    """dl.ttl 下 dd>span 为 Date；dt 下 h1 为 Title；div.desc 下 p 为 Desc。"""
    date: str | None = None
    title: str | None = None
    dl = soup.select_one("dl.ttl")
    if dl:
        sp = dl.select_one("dd span")
        if sp:
            date = sp.get_text(strip=True)
        h1 = dl.select_one("dt h1")
        if h1:
            title = h1.get_text(strip=True)
    desc: str | None = None
    box = soup.select_one("div.desc")
    if box:
        ps = box.find_all("p")
        if ps:
            parts = [p.get_text(" ", strip=True) for p in ps if p.get_text(strip=True)]
            desc = "\n".join(parts) if parts else None
        else:
            t = box.get_text(" ", strip=True)
            desc = t if t else None
    return date, title, desc


def find_thumbnail_imgs(soup: BeautifulSoup) -> list[str]:
    div = soup.select_one(".disco-main__detail__img__thumbnail")
    if not div:
        return []
    out: list[str] = []
    for img in div.find_all("img", src=True):
        src = (img.get("src") or "").strip()
        if src:
            out.append(src)
    return out


def find_next_href(soup: BeautifulSoup, nav_class: str) -> str | None:
    """
    仅在封面图旁的分块 .disco-main__detail__img__nav 内取 li.prev / li.next，
    避免匹配到页面上其他列表里的 li.prev（曾导致误把「下一首」当「上一首」、出现假循环）。
    """
    block = soup.select_one(".disco-main__detail__img__nav")
    if not block:
        return None
    a = block.select_one(f"li.{nav_class} a[href]")
    if not a:
        return None
    return a.get("href")


def local_path_for_json(dest: Path, json_path: Path) -> str:
    """JSON 与图片的相对路径（POSIX 形式，便于跨机使用）。"""
    return os.path.relpath(dest, json_path.parent).replace("\\", "/")


def run(
    start_url: str,
    out_dir: Path,
    json_path: Path,
    nav: str,
    delay: float,
    max_pages: int | None = None,
) -> None:
    nav = nav.lower()
    if nav not in ("prev", "next"):
        raise SystemExit('nav 必须是 "prev" 或 "next"')
    current = start_url
    seen_urls: set[str] = set()
    page_idx = 0
    records: list[dict] = []
    out_dir = out_dir.resolve()
    json_path = json_path.resolve()
    json_path.parent.mkdir(parents=True, exist_ok=True)

    while current:
        if current in seen_urls:
            print(f"检测到循环，停止: {current}")
            break
        seen_urls.add(current)
        page_idx += 1
        print(f"[{page_idx}] 获取: {current}")
        try:
            html = fetch(current)
        except urllib.error.HTTPError as e:
            print(f"HTTP 错误 {e.code}: {current}")
            break
        except OSError as e:
            print(f"请求失败: {e}")
            break

        soup = BeautifulSoup(html, "html.parser")
        date, title, desc_text = extract_date_title_desc(soup)
        imgs = find_thumbnail_imgs(soup)
        pid = post_id_from_url(current)
        local_srcs: list[str] = []
        for i, src in enumerate(imgs):
            name = unquote(urlparse(src).path.rsplit("/", 1)[-1] or f"image_{i}.bin")
            safe = re.sub(r'[<>:"/\\|?*]', "_", name)
            if len(imgs) > 1:
                dest = out_dir / f"{pid}_{i:02d}_{safe}"
            else:
                dest = out_dir / f"{pid}_{safe}"
            if not dest.suffix and "." in safe:
                pass
            print(f"  保存: {dest.name}")
            try:
                download_file(src, dest)
            except OSError as e:
                print(f"  下载失败: {e}")
            else:
                # JSON 中记录相对 json 文件所在目录的路径
                rel = local_path_for_json(dest, json_path)
                local_srcs.append(rel)

        if local_srcs:
            src_value: str | list[str] | None = local_srcs[0] if len(local_srcs) == 1 else local_srcs
        else:
            src_value = None
        row = {
            "Date": date,
            "Title": title,
            "Desc": desc_text,
            "src": src_value,
        }
        records.append(row)

        next_href = find_next_href(soup, nav)
        if not next_href:
            print(f"li.{nav} 下无链接，结束。")
            break
        current = next_href
        if max_pages is not None and page_idx >= max_pages:
            print(f"已达 --max-pages={max_pages}，停止。")
            break
        if delay > 0:
            time.sleep(delay)

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"已写入 JSON: {json_path}（{len(records)} 条）")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--start",
        default=DEFAULT_START,
        help="起始 discography 页面 URL",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "kamitsubaki_discography_imgs",
        help="图片保存目录",
    )
    p.add_argument(
        "--json",
        type=Path,
        default=None,
        help="导出的 JSON 路径；默认为图片目录下 discography.json",
    )
    p.add_argument(
        "--nav",
        choices=("prev", "next"),
        default="prev",
        help='分页方向：prev=跟随 li.prev（较旧作品，站点无 class"pre" 时即此项）；next=较新',
    )
    p.add_argument("--delay", type=float, default=0.5, help="每页之间延迟（秒）")
    p.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="最多抓取页数（默认不限制；调试用可设为 3）",
    )
    args = p.parse_args()
    json_path = args.json
    if json_path is None:
        json_path = args.out / "discography.json"
    run(args.start, args.out, json_path, args.nav, args.delay, args.max_pages)
    print(f"完成。文件目录: {args.out}")


if __name__ == "__main__":
    main()
