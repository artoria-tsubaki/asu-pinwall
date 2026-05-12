#!/usr/bin/env python3
"""
Twitter/X 推文抓取脚本（官方 API v2）
将指定用户的推文转换为 data.json 的 events 条目格式，并保存到项目根目录

用法:
  $env:TWITTER_TOKEN = "你的BearerToken"
  python fetch_tweets.py --token $env:TWITTER_TOKEN --user ASU_virtual --limit 20 --since 2024-01-01
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from html import escape
from datetime import datetime, timezone
from typing import Any, Optional


# ─── 数据转换 ────────────────────────────────────────────────────────────────

def text_to_headline(text: str, max_len: int = 50) -> str:
    plain = re.sub(r"<[^>]+>", "", text)
    first_line = plain.strip().split("\n")[0]
    if len(first_line) > max_len:
        return first_line[:max_len] + "…"
    return first_line


def text_to_html_paragraphs(text: str) -> str:
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    return "".join(f"<p>{line}</p>" for line in lines)


def _entity_url_parts(u) -> Optional[tuple[str, str, str]]:
    if isinstance(u, dict):
        short = u.get("url") or ""
        expanded = u.get("expanded_url") or short
        display = u.get("display_url") or expanded
    else:
        short = getattr(u, "url", None) or ""
        expanded = getattr(u, "expanded_url", None) or short
        display = getattr(u, "display_url", None) or expanded
    if not short:
        return None
    return str(short), str(expanded), str(display)


def apply_entity_urls_to_text(full_text: str, entities: Any = None) -> str:
    text = full_text
    urls_list = None
    if entities:
        if isinstance(entities, dict):
            urls_list = entities.get("urls")
        else:
            urls_list = getattr(entities, "urls", None)
    if urls_list:
        for u in urls_list:
            parts = _entity_url_parts(u)
            if not parts:
                continue
            short, expanded, display = parts
            href = escape(expanded, quote=True)
            label = escape(display)
            anchor = (
                f'<a href="{href}" target="_blank" '
                f'rel="noopener noreferrer">{label}</a>'
            )
            if short in text:
                text = text.replace(short, anchor, 1)
    text = re.sub(r"https://t\.co/\S+", "", text)
    return text.strip()


def build_event(username: str, tweet_id: str, created_at: datetime,
                full_text: str, image_url: Optional[str],
                entities: Any = None) -> dict:
    tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"
    rich_text = apply_entity_urls_to_text(full_text, entities)

    return {
        "media": {
            "url": image_url or "",
            "caption": f'<a href="{tweet_url}" target="_blank">Twitter</a>'
        },
        "start_date": {
            "year": str(created_at.year),
            "month": str(created_at.month),
            "day": str(created_at.day)
        },
        "text": {
            "headline": text_to_headline(rich_text),
            "text": text_to_html_paragraphs(rich_text)
        }
    }


# ─── 官方 API v2 (tweepy) ────────────────────────────────────────────────────

def fetch_via_api(username: str, bearer_token: str,
                  limit: int, since: Optional[str]) -> list[dict]:
    try:
        import tweepy
    except ImportError:
        print("[ERROR] 请先安装 tweepy: pip install tweepy", file=sys.stderr)
        sys.exit(1)

    client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)

    user_resp = client.get_user(username=username)
    if not user_resp.data:
        print(f"[ERROR] 找不到用户 @{username}", file=sys.stderr)
        sys.exit(1)
    user_id = user_resp.data.id

    start_time = None
    if since:
        start_time = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    kwargs = dict(
        id=user_id,
        max_results=min(limit, 100),
        tweet_fields=["created_at", "attachments", "entities"],
        expansions=["attachments.media_keys"],
        media_fields=["url", "preview_image_url", "type"],
        exclude=["retweets", "replies"],
    )
    if start_time:
        kwargs["start_time"] = start_time

    events = []
    collected = 0

    paginator = tweepy.Paginator(client.get_users_tweets, **kwargs)
    for response in paginator:
        if not response.data:
            break

        media_map: dict[str, str] = {}
        if response.includes and "media" in response.includes:
            for m in response.includes["media"]:
                url = getattr(m, "url", None) or getattr(m, "preview_image_url", None)
                if url:
                    media_map[m.media_key] = url

        for tweet in response.data:
            image_url = None
            if tweet.attachments and tweet.attachments.get("media_keys"):
                first_key = tweet.attachments["media_keys"][0]
                image_url = media_map.get(first_key)

            dt: datetime = tweet.created_at  # type: ignore
            entry = build_event(
                username, str(tweet.id), dt, tweet.text, image_url, tweet.entities
            )
            events.append(entry)
            collected += 1
            if collected >= limit:
                break

        if collected >= limit:
            break

    return events


# ─── 主入口 ──────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="抓取 Twitter/X 用户推文并转换为 data.json events 格式"
    )
    parser.add_argument("--user", required=True, help="Twitter 用户名（不含 @）")
    parser.add_argument("--token", default=None,
                        help="Bearer Token（也可通过环境变量 TWITTER_TOKEN 传入）")
    parser.add_argument("--limit", type=int, default=20, help="最多获取条数（默认 20）")
    parser.add_argument("--since", default=None, help="仅获取该日期之后的推文，格式 YYYY-MM-DD")
    return parser.parse_args()


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    args = parse_args()

    # Token 优先从参数读取，其次从环境变量读取
    token = args.token or os.environ.get("TWITTER_TOKEN")
    if not token:
        print("[ERROR] 请通过 --token 参数或 TWITTER_TOKEN 环境变量提供 Bearer Token", file=sys.stderr)
        sys.exit(1)

    events = fetch_via_api(args.user, token, args.limit, args.since)

    if not events:
        print("[WARN] 未获取到任何推文", file=sys.stderr)
        sys.exit(0)

    # 以执行时间命名，保存到项目根目录（脚本向上三级即为根目录）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"tweets_{args.user}_{timestamp}.json"

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", "..", "..", ".."))
    output_path = os.path.join(project_root, filename)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

    print(f"[OK] 已获取 {len(events)} 条推文，保存至: {output_path}", file=sys.stderr)
    print(json.dumps(events, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
