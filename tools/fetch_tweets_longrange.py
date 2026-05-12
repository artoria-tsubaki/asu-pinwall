#!/usr/bin/env python3
"""
Twitter/X 长时段推文批量抓取脚本（官方 API v2）

将指定用户在较长时间跨度内的推文全量抓取，
通过时间窗口分割 + 逐段分页 + 去重合并的方式保证数据完整性。
输出格式与 fetch_tweets.py 完全一致（data.json events 条目格式）。

用法:
  python fetch_tweets_longrange.py \\
      --user ASU_virtual \\
      --start 2025-01-01 \\
      --end   2025-12-31 \\
      --chunk-days 30 \\
      --delay 3.0 \\
      --checkpoint-dir ./checkpoints \\
      --output tweets_full.json

  # 也可通过环境变量传入 Token
  $env:TWITTER_TOKEN = "你的BearerToken"
  python fetch_tweets_longrange.py --user ASU_virtual --start 2025-01-01
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from html import escape
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional


# ─── 数据转换（与 fetch_tweets.py 保持一致）────────────────────────────────────

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


# ─── 时间窗口分割 ────────────────────────────────────────────────────────────

def split_date_range(start: date, end: date,
                     chunk_days: int) -> list[tuple[date, date]]:
    """
    将 [start, end] 拆分为若干个不超过 chunk_days 天的子区间。
    返回 [(chunk_start, chunk_end), ...] 列表，按时间升序排列。
    每个区间左闭右开：[chunk_start, chunk_end)，与 Twitter API 语义一致。
    """
    if start >= end:
        raise ValueError(f"--start ({start}) 必须早于 --end ({end})")
    if chunk_days < 1:
        raise ValueError("--chunk-days 必须 >= 1")

    chunks: list[tuple[date, date]] = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=chunk_days), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end
    return chunks


# ─── 单窗口抓取（返回 tweet_id -> event 映射）────────────────────────────────

def fetch_chunk(client,  # tweepy.Client
                user_id: int,
                username: str,
                chunk_start: date,
                chunk_end: date,
                exclude: Optional[list[str]] = None) -> dict[str, dict]:
    """
    抓取 [chunk_start, chunk_end) 内的所有推文（排除转推和回复），
    返回 {tweet_id: event_dict} 字典，便于后续去重合并。
    """
    import tweepy  # 延迟导入，错误提示在外层处理

    start_dt = datetime(chunk_start.year, chunk_start.month,
                        chunk_start.day, tzinfo=timezone.utc)
    end_dt = datetime(chunk_end.year, chunk_end.month,
                      chunk_end.day, tzinfo=timezone.utc)

    kwargs: dict = dict(
        id=user_id,
        max_results=100,
        tweet_fields=["created_at", "attachments", "entities"],
        expansions=["attachments.media_keys"],
        media_fields=["url", "preview_image_url", "type"],
        start_time=start_dt,
        end_time=end_dt,
    )
    # 注意：X API v2 在同时使用 start_time + end_time 时，若 exclude 含 replies，
    # 实测若干账号会稳定返回 0 条；长时段抓取默认只排除转推。
    if exclude:
        kwargs["exclude"] = exclude

    result: dict[str, dict] = {}

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
            tid = str(tweet.id)
            result[tid] = build_event(
                username, tid, dt, tweet.text, image_url, tweet.entities
            )

    return result


# ─── 断点保存与读取 ──────────────────────────────────────────────────────────

def checkpoint_filename(checkpoint_dir: Path, idx: int,
                        chunk_start: date, chunk_end: date) -> Path:
    return checkpoint_dir / f"chunk_{idx:04d}_{chunk_start}_{chunk_end}.json"


def save_checkpoint(data: dict[str, dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_checkpoint(path: Path) -> dict[str, dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_completed_checkpoints(checkpoint_dir: Path,
                                chunks: list[tuple[date, date]]
                                ) -> set[int]:
    """返回已完成的 chunk 索引集合。"""
    completed: set[int] = set()
    if not checkpoint_dir.exists():
        return completed
    for idx, (cs, ce) in enumerate(chunks):
        cp = checkpoint_filename(checkpoint_dir, idx, cs, ce)
        if cp.exists():
            completed.add(idx)
    return completed


# ─── 合并去重排序 ────────────────────────────────────────────────────────────

def merge_and_deduplicate(
    all_chunks: list[dict[str, dict]]
) -> list[dict]:
    """
    合并多个 {tweet_id: event} 字典，按 tweet_id 去重，
    再按 start_date 降序（最新推文在前）排列，返回 event 列表。
    """
    merged: dict[str, dict] = {}
    for chunk in all_chunks:
        for tid, event in chunk.items():
            if tid not in merged:
                merged[tid] = event

    def sort_key(item: tuple[str, dict]) -> tuple[int, int, int]:
        sd = item[1]["start_date"]
        return (int(sd["year"]), int(sd["month"]), int(sd["day"]))

    sorted_items = sorted(merged.items(), key=sort_key, reverse=True)
    return [event for _, event in sorted_items]


# ─── 主流程 ──────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "长时段 Twitter/X 推文批量抓取工具\n"
            "通过时间窗口分割保证大时间跨度数据的完整性"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  # 获取过去半年数据，每 30 天为一窗口\n"
            "  python fetch_tweets_longrange.py "
            "--user ASU_virtual --start 2024-11-01 --end 2025-04-30\n\n"
            "  # 获取一年数据并保存断点（断网续传）\n"
            "  python fetch_tweets_longrange.py "
            "--user ASU_virtual --start 2024-01-01 --checkpoint-dir ./ckpt"
        )
    )

    parser.add_argument("--user", required=True,
                        help="Twitter 用户名（不含 @）")
    parser.add_argument("--token", default=None,
                        help="Bearer Token（也可通过环境变量 TWITTER_TOKEN 传入）")
    parser.add_argument("--start", required=True,
                        help="抓取起始日期，格式 YYYY-MM-DD（含）")
    parser.add_argument("--end", default=None,
                        help="抓取结束日期，格式 YYYY-MM-DD（含，默认今天）")
    parser.add_argument("--chunk-days", type=int, default=30,
                        help="每个时间窗口的天数，默认 30（建议 7~30）")
    parser.add_argument("--delay", type=float, default=3.0,
                        help="每个时间窗口之间的等待秒数，默认 3.0（防止触发频率限制）")
    parser.add_argument("--checkpoint-dir", default=None,
                        help="断点保存目录，指定后每窗口独立存档，支持中断续传")
    parser.add_argument("--output", default=None,
                        help="输出文件路径（默认自动生成带时间戳的文件名）")
    parser.add_argument(
        "--exclude-retweets", action=argparse.BooleanOptionalAction,
        default=True,
        help="排除转推（默认开启，对应 --no-exclude-retweets 保留转推）"
    )
    parser.add_argument(
        "--exclude-replies", action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "排除回复（默认关闭）。若与时间窗口同时启用，X API 可能返回空结果，请先试默认。"
        )
    )

    return parser.parse_args()


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    args = parse_args()

    # ── Token 验证 ──
    token = args.token or os.environ.get("TWITTER_TOKEN")
    if not token:
        print(
            "[ERROR] 请通过 --token 参数或 TWITTER_TOKEN 环境变量提供 Bearer Token",
            file=sys.stderr
        )
        sys.exit(1)

    # ── 日期解析 ──
    try:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
    except ValueError:
        print(f"[ERROR] --start 日期格式错误：{args.start}，应为 YYYY-MM-DD",
              file=sys.stderr)
        sys.exit(1)

    end_str = args.end or date.today().strftime("%Y-%m-%d")
    try:
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    except ValueError:
        print(f"[ERROR] --end 日期格式错误：{end_str}，应为 YYYY-MM-DD",
              file=sys.stderr)
        sys.exit(1)

    # Twitter API end_time 是不包含当天的，+1 day 让 end_date 当天的推文也被纳入
    end_date_inclusive = end_date + timedelta(days=1)

    try:
        chunks = split_date_range(start_date, end_date_inclusive, args.chunk_days)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    total_chunks = len(chunks)
    print(
        f"[INFO] 时间范围：{start_date} ~ {end_date}，"
        f"共拆分为 {total_chunks} 个窗口（每窗口 {args.chunk_days} 天）",
        file=sys.stderr
    )

    # ── 初始化 tweepy ──
    try:
        import tweepy
    except ImportError:
        print("[ERROR] 请先安装 tweepy: pip install tweepy", file=sys.stderr)
        sys.exit(1)

    client = tweepy.Client(bearer_token=token, wait_on_rate_limit=True)

    user_resp = client.get_user(username=args.user)
    if not user_resp.data:
        print(f"[ERROR] 找不到用户 @{args.user}", file=sys.stderr)
        sys.exit(1)
    user_id = user_resp.data.id
    print(f"[INFO] 已找到用户 @{args.user}（id={user_id}）", file=sys.stderr)

    exclude_list: list[str] = []
    if args.exclude_retweets:
        exclude_list.append("retweets")
    if args.exclude_replies:
        exclude_list.append("replies")
    excl_note = ",".join(exclude_list) if exclude_list else "无"
    print(f"[INFO] exclude={excl_note}", file=sys.stderr)

    # ── 断点目录 ──
    checkpoint_dir: Optional[Path] = None
    if args.checkpoint_dir:
        checkpoint_dir = Path(args.checkpoint_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

    completed_indices = (
        find_completed_checkpoints(checkpoint_dir, chunks)
        if checkpoint_dir else set()
    )
    if completed_indices:
        print(
            f"[INFO] 发现 {len(completed_indices)} 个已完成的断点窗口，将跳过重新抓取",
            file=sys.stderr
        )

    # ── 逐窗口抓取 ──
    all_chunks: list[dict[str, dict]] = []
    total_fetched = 0

    for idx, (cs, ce) in enumerate(chunks):
        cp_path = checkpoint_filename(checkpoint_dir, idx, cs, ce) if checkpoint_dir else None

        # 断点续传：已存在则直接加载
        if idx in completed_indices and cp_path:
            cached = load_checkpoint(cp_path)
            all_chunks.append(cached)
            print(
                f"[INFO] [{idx+1}/{total_chunks}] {cs} ~ {ce}  "
                f"从断点加载 {len(cached)} 条",
                file=sys.stderr
            )
            continue

        print(
            f"[INFO] [{idx+1}/{total_chunks}] 抓取窗口 {cs} ~ {ce} ...",
            file=sys.stderr
        )
        try:
            chunk_data = fetch_chunk(
                client, user_id, args.user, cs, ce,
                exclude=exclude_list if exclude_list else None,
            )
        except Exception as e:
            print(
                f"[WARN] [{idx+1}/{total_chunks}] 窗口 {cs}~{ce} 抓取失败，已跳过：{e}",
                file=sys.stderr
            )
            all_chunks.append({})
            continue

        print(
            f"[INFO] [{idx+1}/{total_chunks}] {cs} ~ {ce}  获取 {len(chunk_data)} 条",
            file=sys.stderr
        )
        total_fetched += len(chunk_data)
        all_chunks.append(chunk_data)

        # 保存断点
        if cp_path:
            save_checkpoint(chunk_data, cp_path)

        # 窗口间延迟（最后一个窗口不等待）
        if idx < total_chunks - 1 and args.delay > 0:
            time.sleep(args.delay)

    # ── 合并去重 ──
    events = merge_and_deduplicate(all_chunks)
    raw_total = sum(len(c) for c in all_chunks)
    dedup_removed = raw_total - len(events)

    print(
        f"[INFO] 合并完成：原始 {raw_total} 条，去重删除 {dedup_removed} 条，"
        f"最终保留 {len(events)} 条",
        file=sys.stderr
    )

    if not events:
        print("[WARN] 未获取到任何推文", file=sys.stderr)
        sys.exit(0)

    # ── 输出 ──
    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tweets_{args.user}_{start_date}_{end_date}_{timestamp}.json"
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(script_dir, ".."))
        output_path = os.path.join(project_root, filename)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

    print(f"[OK] 已保存 {len(events)} 条推文至：{output_path}", file=sys.stderr)
    print(json.dumps(events, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
