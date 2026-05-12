#!/usr/bin/env python3
"""
fetch_tweets_timeline.py  —  推特推文 → timeline.json events 格式转换工具

三类输出条目（对齐 codes/src/data/timeline.json）：

[Cover]        有 YouTube URL 且推文含 "THE COVER" / "covered by" 关键词
  media.url    = YouTube 视频链接
  media.caption= <a href="yt_url">THE COVER xx</a>  （若无则用 oEmbed title）
  text.headline= {曲名} - {原唱} covered by 明透
  text.text    = 歌唱感想（来自推文本身或时间上相邻的推文）

[MV / Origin]  有 YouTube URL 且含 "THE ORIGIN" / "オリジナルMV" / "Op." / "new single" 关键词
  media.url    = YouTube 视频链接
  media.caption= <a href="yt_url">THE ORIGIN xx</a>（或 oEmbed title）
  text.headline= 明透 Op.N - 曲名  /  曲名【オリジナルMV】  /  oEmbed title
  text.text    = 发布感想或空 <p></p>

[Celebratory]  有 pbs.twimg 图片 + 无 YouTube，含里程碑关键词
  media.url    = pbs.twimg.com/...?format=jpg&name=orig
  media.caption= <a href="tweet_url" target="_blank">Twitter address</a>
  text.headline= 庆祝标题（推文首行）
  text.text    = 全文 HTML 段落

用法:
  python fetch_tweets_timeline.py --user ASU_virtual --start 2022-06-01 --end 2022-06-30

  # 同时生成与 timeline.json 的比对报告
  python fetch_tweets_timeline.py \\
    --user ASU_virtual --start 2022-06-01 --end 2022-06-30 \\
    --compare codes/src/data/timeline.json

  # 含 Bearer Token 与断点续传
  python fetch_tweets_timeline.py \\
    --user ASU_virtual --start 2022-01-01 --end 2022-12-31 \\
    --token YOUR_BEARER_TOKEN \\
    --checkpoint-dir ./checkpoints_tl
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any, Optional


# ─── 分类关键词正则 ───────────────────────────────────────────────────────────

# Cover/MV 判定使用的 YouTube 域名（不含 live——直播流不作为歌みた/MV）
YT_COVER_DOMAINS = (
    "youtube.com/watch",
    "youtu.be/",
    "youtube.com/shorts",
)
# 完整 YouTube 域名列表（用于 URL 展开等其他用途）
YT_DOMAINS = YT_COVER_DOMAINS + ("youtube.com/live",)

RE_COVER_LABEL  = re.compile(
    r"THE\s*COVER\s*\d*"           # 旧式标签  THE COVER 27
    r"|歌ってみた|歌いました"         # 日语唱曲惯用表达
    r"|cover\s+song"               # 英文 cover song
    r"|カバー(?:曲|ソング)?",        # 片假名 カバー / カバー曲
    re.IGNORECASE,
)
RE_ORIGIN_LABEL = re.compile(r"THE\s*ORIGIN\s*\d*", re.IGNORECASE)
RE_NEW_SINGLE   = re.compile(r"new\s+single", re.IGNORECASE)
RE_COVERED_BY   = re.compile(r"covered\s+by", re.IGNORECASE)
RE_ORIGINAL_MV  = re.compile(r"オリジナルMV")
RE_OP_NUMBER    = re.compile(r"\bOp\.\s*\d+")
RE_MILESTONE    = re.compile(
    r"万再生|万人突破|万フォロワー|周年|チャンネル登録|フォロワー数が.{0,10}突破|"
    r"登録者数.{0,10}突破|再生.{0,10}突破|ミリオン"
)
RE_TWIMG_EXT    = re.compile(r"\.(jpg|jpeg|png|gif|webp)(\?.*)?$", re.IGNORECASE)
RE_TCO          = re.compile(r"https://t\.co/\S+")


# ─── URL 工具 ────────────────────────────────────────────────────────────────

def normalize_twimg_url(url: str) -> str:
    """pbs.twimg.com/media/KEY.jpg → pbs.twimg.com/media/KEY?format=jpg&name=orig"""
    if "pbs.twimg.com" not in url:
        return url
    base = url.split("?")[0]
    base = RE_TWIMG_EXT.sub("", base)
    return base + "?format=jpg&name=orig"


def extract_yt_url(entities: Any) -> Optional[str]:
    """
    entities から Cover/MV 判定用の YouTube URL を抽取する。
    youtube.com/live は直播流のため除外（歌みた/MV の判定には使わない）。
    """
    urls_list: Any = None
    if isinstance(entities, dict):
        urls_list = entities.get("urls")
    else:
        urls_list = getattr(entities, "urls", None)
    if not urls_list:
        return None
    for u in urls_list:
        expanded: str = (
            u.get("expanded_url") if isinstance(u, dict)
            else getattr(u, "expanded_url", None)
        ) or ""
        if any(d in expanded for d in YT_COVER_DOMAINS):
            return expanded
    return None


def extract_image_url(entities: Any, image_url: str) -> Optional[str]:
    """返回第一个 pbs.twimg 图片 URL（已规范化为 orig 形式）。"""
    if image_url and "pbs.twimg.com" in image_url:
        return normalize_twimg_url(image_url)
    return None


def oembed_title(yt_url: str, timeout: int = 6) -> Optional[str]:
    """通过 YouTube oEmbed API 获取视频标题（无需 API Key）。"""
    api_url = f"https://www.youtube.com/oembed?format=json&url={yt_url}"
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("title")
    except Exception:
        return None


# ─── HTML 工具 ───────────────────────────────────────────────────────────────

def apply_entity_urls_to_text(full_text: str, entities: Any = None) -> str:
    """将推文中的 t.co 短链展开为 HTML 超链接，清除残余 t.co。"""
    text = full_text
    urls_list: Any = None
    if entities:
        if isinstance(entities, dict):
            urls_list = entities.get("urls")
        else:
            urls_list = getattr(entities, "urls", None)
    if urls_list:
        for u in urls_list:
            if isinstance(u, dict):
                short    = u.get("url") or ""
                expanded = u.get("expanded_url") or short
                display  = u.get("display_url") or expanded
            else:
                short    = getattr(u, "url",          None) or ""
                expanded = getattr(u, "expanded_url", None) or short
                display  = getattr(u, "display_url",  None) or expanded
            if not short:
                continue
            href   = escape(str(expanded), quote=True)
            label  = escape(str(display))
            anchor = (
                f'<a href="{href}" target="_blank"'
                f' rel="noopener noreferrer">{label}</a>'
            )
            if short in text:
                text = text.replace(short, anchor, 1)
    text = RE_TCO.sub("", text)
    return text.strip()


def text_to_html_paragraphs(rich_text: str) -> str:
    """将富文本按换行切段，每段包入 <p>。空内容返回 <p></p>。"""
    lines = [ln.strip() for ln in rich_text.strip().split("\n") if ln.strip()]
    if not lines:
        return "<p></p>"
    return "".join(f"<p>{ln}</p>" for ln in lines)


def strip_plain(text: str) -> str:
    """去除 HTML 标签与 t.co URL，返回纯文本（用于长度判断）。"""
    cleaned = re.sub(r"<[^>]+>", "", text)
    cleaned = RE_TCO.sub("", cleaned)
    return cleaned.strip()


# ─── 分类逻辑 ────────────────────────────────────────────────────────────────

def classify(tweet_text: str, yt_url: Optional[str], img_url: Optional[str]) -> str:
    """
    返回 'cover' | 'mv' | 'celebratory' | 'other'

    注意顺序：先看是否有 YouTube（Cover/MV 优先），再看图文里程碑。
    """
    if yt_url:
        if RE_COVER_LABEL.search(tweet_text) or RE_COVERED_BY.search(tweet_text):
            return "cover"
        if (RE_ORIGIN_LABEL.search(tweet_text)
                or RE_ORIGINAL_MV.search(tweet_text)
                or RE_OP_NUMBER.search(tweet_text)
                or RE_NEW_SINGLE.search(tweet_text)):
            return "mv"
        # 有 YouTube 但无明确 Cover/MV 标记 → other（直播/协作等）
        return "other"

    if img_url:
        if RE_MILESTONE.search(tweet_text):
            return "celebratory"

    return "other"


# ─── 标题与锚文字提取 ────────────────────────────────────────────────────────

def extract_cover_label(text: str) -> Optional[str]:
    m = RE_COVER_LABEL.search(text)
    return m.group(0).strip() if m else None


def extract_mv_label(text: str) -> Optional[str]:
    """MV 推文的 caption 锚文字：优先 THE ORIGIN xx，否则命中 new single 时用固定文案。"""
    m = RE_ORIGIN_LABEL.search(text)
    if m:
        return m.group(0).strip()
    if RE_NEW_SINGLE.search(text):
        return "New Single"
    return None


def build_cover_headline(tweet_text: str, oembed: Optional[str]) -> str:
    """
    优先从 oEmbed title 提取 `xxx covered by xxx` 格式；
    退而匹配推文正文；最终 fallback 到 oEmbed title 原文。
    """
    for src in ([oembed] if oembed else []) + [tweet_text]:
        if not src:
            continue
        m = re.search(r"(.+covered\s+by.+)", src, re.IGNORECASE)
        if m:
            line = m.group(1).strip()
            line = re.sub(r"【[^】]*】", "", line).strip()
            line = re.sub(r"#\S+", "", line).strip()
            return line
    if oembed:
        return oembed
    return tweet_text.strip().split("\n")[0][:60]


def build_mv_headline(tweet_text: str, oembed: Optional[str]) -> str:
    """
    按优先级匹配：推文/oEmbed 里的 Op.N 表述 → 【オリジナルMV】 → oEmbed title。
    """
    for src in [tweet_text, oembed or ""]:
        if not src:
            continue
        # 明透 Op.N - 曲名
        m = re.search(r"明透\s+Op\.\s*\d+\s*[-－]\s*\S+", src)
        if m:
            return m.group(0).strip()
        # 曲名【オリジナルMV】
        m = re.search(r"(.+?【オリジナルMV】)", src)
        if m:
            return m.group(1).strip()
        # 【オリジナルMV】曲名
        m = re.search(r"【オリジナルMV】(.+)", src)
        if m:
            return ("【オリジナルMV】" + m.group(1).strip()).split("\n")[0][:60]

    if oembed:
        return oembed
    return tweet_text.strip().split("\n")[0][:60]


_RE_DECORATION   = re.compile(r"^[━─=＝╭╮╰╯|｜\-\s\u25a0-\u25ff]+$")
_RE_SHORT_EXCLAIM = re.compile(r"^[！!？?…ー〜～わあえっきゃおうん]{1,6}$")
_RE_MILESTONE_LINE = re.compile(
    r"万再生|万人|突破|🎉|㊗|おめでとう|記念|周年|達成|ミリオン|デビュー"
)


def build_celebratory_headline(tweet_text: str) -> str:
    """
    庆祝推文标题：优先取含里程碑关键词的行，次取第一个非空/非装饰/非感叹行。
    ASU_virtual 庆祝推文常以 「なんとー！」「ええっ」 等短感叹开头，真正的里程碑
    描述行在其后，这里需要跳过这类开头。
    """
    lines = [ln.strip() for ln in tweet_text.strip().split("\n") if ln.strip()]
    lines = [ln for ln in lines if not _RE_DECORATION.match(ln)]

    # 1) 含里程碑词汇的行优先
    for ln in lines:
        if _RE_MILESTONE_LINE.search(ln):
            return ln[:60]

    # 2) 跳过纯感叹短行
    for ln in lines:
        if _RE_SHORT_EXCLAIM.match(ln):
            continue
        return ln[:60]

    return lines[0][:60] if lines else tweet_text[:60]


# ─── 邻近推文感想合并 ─────────────────────────────────────────────────────────

def is_substantive(text: str, min_chars: int = 20) -> bool:
    """判断文本（去掉 t.co / 哈希标签后）是否足够实质。"""
    cleaned = RE_TCO.sub("", text)
    cleaned = re.sub(r"#\S+", "", cleaned).strip()
    return len(cleaned) >= min_chars


def get_neighbor_text(idx: int, raw_tweets: list[dict],
                      window_hours: float = 12.0) -> str:
    """
    对 raw_tweets[idx] 对应的主推文，若其正文太短，
    则在时间窗内寻找前后各 1 条同作者、非 RT 推文的富文本。
    返回可用作 text.text 来源的富文本字符串。

    说明：抓取策略默认保留回复（不 exclude replies），
    因为明透常在 YouTube 推文下方以自回复形式发布感想长文。
    """
    curr      = raw_tweets[idx]
    curr_text = curr["text"]
    curr_dt   = curr["created_at"]
    curr_rich = apply_entity_urls_to_text(curr_text, curr.get("entities"))

    if is_substantive(curr_rich):
        return curr_rich

    window = timedelta(hours=window_hours)
    candidates: list[tuple[timedelta, str]] = []

    for offset in [-1, +1]:
        j = idx + offset
        if j < 0 or j >= len(raw_tweets):
            continue
        nbr = raw_tweets[j]
        # 排除转推与明显不相关的推文
        if nbr["text"].startswith("RT @"):
            continue
        ndt: datetime = nbr["created_at"]
        if abs(ndt - curr_dt) > window:
            continue
        nbr_rich = apply_entity_urls_to_text(nbr["text"], nbr.get("entities"))
        # 跳过另一个媒体帖（本身就是 YouTube/图片推文）
        if extract_yt_url(nbr.get("entities") or {}):
            continue
        if is_substantive(nbr_rich, min_chars=25):
            candidates.append((abs(ndt - curr_dt), nbr_rich))

    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    return curr_rich


_RE_SERIES_LABEL = re.compile(
    r"^(?:THE\s+(?:COVER|ORIGIN)\s*\d*"
    r"|歌ってみました"    # 歌ってみました単独行
    r")\s*$",
    re.IGNORECASE,
)


def clean_media_refs(rich_text: str) -> str:
    """
    去掉 rich_text 中的：
    - YouTube/图片链接（anchor 或裸 URL）
    - 纯系列标签行（THE COVER27 / THE ORIGIN 03 等，内容已在 caption 中）
    """
    # 去掉仅含 YouTube/图片域名的 anchor
    cleaned = re.sub(
        r'<a [^>]+>(?:youtube\.com|youtu\.be|pic\.x\.com|pic\.twitter\.com)[^<]*</a>',
        "", rich_text,
    )
    # 去掉裸 YouTube URL
    cleaned = re.sub(
        r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S*",
        "", cleaned,
    )
    # 去掉纯系列标签行
    lines = [ln.strip() for ln in cleaned.split("\n")]
    lines = [ln for ln in lines if not _RE_SERIES_LABEL.match(ln)]
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{2,}", "\n", cleaned).strip()
    return cleaned


# ─── 单条事件构建 ─────────────────────────────────────────────────────────────

def build_cover_event(username: str, tweet_id: str, created_at: datetime,
                      tweet_text: str, yt_url: str, entities: Any,
                      idx: int, raw_tweets: list[dict],
                      oembed_delay: float = 0.3) -> dict:
    label  = extract_cover_label(tweet_text)
    oembed = oembed_title(yt_url)
    if oembed_delay > 0:
        time.sleep(oembed_delay)

    caption_anchor = label or (oembed[:40] if oembed else None) or "YouTube"
    headline = build_cover_headline(tweet_text, oembed)

    neighbor_rich = get_neighbor_text(idx, raw_tweets)
    text_clean    = clean_media_refs(neighbor_rich)

    return {
        "media": {
            "url": yt_url,
            "caption": (
                f'<a href="{escape(yt_url, quote=True)}" target="_blank">'
                f'{escape(caption_anchor)}</a>'
            ),
        },
        "start_date": {
            "year":  str(created_at.year),
            "month": str(created_at.month),
            "day":   str(created_at.day),
        },
        "text": {
            "headline": headline,
            "text": (text_to_html_paragraphs(text_clean)
                     if text_clean else f"<p>{escape(caption_anchor)}</p>"),
        },
    }


def build_mv_event(username: str, tweet_id: str, created_at: datetime,
                   tweet_text: str, yt_url: str, entities: Any,
                   idx: int, raw_tweets: list[dict],
                   oembed_delay: float = 0.3) -> dict:
    label  = extract_mv_label(tweet_text)
    oembed = oembed_title(yt_url)
    if oembed_delay > 0:
        time.sleep(oembed_delay)

    caption_anchor = label or (oembed[:50] if oembed else None) or "YouTube"
    headline = build_mv_headline(tweet_text, oembed)

    neighbor_rich = get_neighbor_text(idx, raw_tweets)
    text_clean    = clean_media_refs(neighbor_rich)

    return {
        "media": {
            "url": yt_url,
            "caption": (
                f'<a href="{escape(yt_url, quote=True)}" target="_blank">'
                f'{escape(caption_anchor)}</a>'
            ),
        },
        "start_date": {
            "year":  str(created_at.year),
            "month": str(created_at.month),
            "day":   str(created_at.day),
        },
        "text": {
            "headline": headline,
            "text": (text_to_html_paragraphs(text_clean)
                     if text_clean else "<p></p>"),
        },
    }


def build_celebratory_event(username: str, tweet_id: str, created_at: datetime,
                             tweet_text: str, image_url: str,
                             entities: Any) -> dict:
    tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"
    rich_text = apply_entity_urls_to_text(tweet_text, entities)
    norm_img  = normalize_twimg_url(image_url)

    return {
        "media": {
            "url": norm_img,
            "caption": f'<a href="{tweet_url}" target="_blank">Twitter address</a>',
        },
        "start_date": {
            "year":  str(created_at.year),
            "month": str(created_at.month),
            "day":   str(created_at.day),
        },
        "text": {
            "headline": build_celebratory_headline(tweet_text),
            "text": text_to_html_paragraphs(rich_text),
        },
    }


# ─── API 抓取（原始 tweet 存储，不提前 build_event）─────────────────────────

def split_date_range(start: date, end: date,
                     chunk_days: int) -> list[tuple[date, date]]:
    if start >= end:
        raise ValueError(f"--start ({start}) 必须早于 --end ({end})")
    chunks: list[tuple[date, date]] = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=chunk_days), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end
    return chunks


def fetch_raw_chunk(client, user_id: int, username: str,
                    chunk_start: date, chunk_end: date,
                    exclude: Optional[list[str]] = None) -> dict[str, dict]:
    """
    抓取 [chunk_start, chunk_end) 内的推文，返回 {tweet_id: raw_dict}。
    raw_dict 保留完整字段，供后续分类与邻近合并使用。

    entities 被规范化为 dict（便于 JSON 序列化断点存储）。
    """
    import tweepy

    start_dt = datetime(chunk_start.year, chunk_start.month,
                        chunk_start.day, tzinfo=timezone.utc)
    end_dt   = datetime(chunk_end.year, chunk_end.month,
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
    if exclude:
        kwargs["exclude"] = exclude

    result: dict[str, dict] = {}

    for response in tweepy.Paginator(client.get_users_tweets, **kwargs):
        if not response.data:
            break

        media_map: dict[str, str] = {}
        if response.includes and "media" in response.includes:
            for m in response.includes["media"]:
                url = getattr(m, "url", None) or getattr(m, "preview_image_url", None)
                if url:
                    media_map[m.media_key] = url

        for tweet in response.data:
            image_url: Optional[str] = None
            if tweet.attachments and tweet.attachments.get("media_keys"):
                first_key = tweet.attachments["media_keys"][0]
                image_url = media_map.get(first_key)

            dt: datetime = tweet.created_at  # type: ignore
            raw_entities = tweet.entities
            # 规范化为可序列化的 dict
            if raw_entities is not None and not isinstance(raw_entities, dict):
                raw_entities = getattr(raw_entities, "data", None) or {}
            if raw_entities is None:
                raw_entities = {}

            result[str(tweet.id)] = {
                "id":         str(tweet.id),
                "text":       tweet.text,
                "created_at": dt.isoformat(),
                "image_url":  image_url or "",
                "entities":   raw_entities,
                "username":   username,
            }

    return result


def _parse_created_at(raw: dict) -> None:
    """将 created_at 字符串原地解析为 datetime 对象（支持从断点文件加载后调用）。"""
    val = raw["created_at"]
    if isinstance(val, str):
        try:
            raw["created_at"] = datetime.fromisoformat(val)
        except ValueError:
            raw["created_at"] = datetime.now(tz=timezone.utc)


def checkpoint_path(checkpoint_dir: Path, idx: int, cs: date, ce: date) -> Path:
    return checkpoint_dir / f"tl_chunk_{idx:04d}_{cs}_{ce}.json"


# ─── 转换主流程 ──────────────────────────────────────────────────────────────

def convert_to_events(
    all_raw: dict[str, dict],
    username: str,
    oembed_delay: float = 0.3,
    verbose: bool = True,
) -> tuple[list[dict], list[dict]]:
    """
    将原始推文 map 转换为 timeline events 列表。
    返回 (classified_events, unclassified_raw_list)。

    raw_tweets 按 created_at 升序排列，以支持邻近推文文本合并。
    """
    raw_tweets: list[dict] = sorted(all_raw.values(), key=lambda t: t["created_at"])
    for t in raw_tweets:
        _parse_created_at(t)

    events: list[dict]     = []
    unclassified: list[dict] = []

    for idx, raw in enumerate(raw_tweets):
        tweet_id   = raw["id"]
        tweet_text = raw["text"]
        created_at: datetime = raw["created_at"]
        image_url  = raw.get("image_url") or ""
        entities   = raw.get("entities") or {}

        yt_url  = extract_yt_url(entities)
        img_url = extract_image_url(entities, image_url)

        category = classify(tweet_text, yt_url, img_url)

        if verbose:
            snippet = tweet_text[:45].replace("\n", " ")
            print(
                f"  [{category:13s}] {created_at.date()}  {snippet!r}",
                file=sys.stderr,
            )

        if category == "cover":
            ev = build_cover_event(
                username, tweet_id, created_at,
                tweet_text, yt_url, entities,
                idx, raw_tweets, oembed_delay,
            )
            events.append(ev)

        elif category == "mv":
            ev = build_mv_event(
                username, tweet_id, created_at,
                tweet_text, yt_url, entities,
                idx, raw_tweets, oembed_delay,
            )
            events.append(ev)

        elif category == "celebratory":
            ev = build_celebratory_event(
                username, tweet_id, created_at,
                tweet_text, image_url, entities,
            )
            events.append(ev)

        else:
            # created_at を文字列に戻して JSON シリアライズ可能にする
            raw_copy = dict(raw)
            if isinstance(raw_copy.get("created_at"), datetime):
                raw_copy["created_at"] = raw_copy["created_at"].isoformat()
            unclassified.append(raw_copy)

    return events, unclassified


# ─── Golden 比对报告 ─────────────────────────────────────────────────────────

def compare_with_golden(
    events: list[dict],
    golden_path: str,
    start_date: Optional[date] = None,
    end_date: Optional[date]   = None,
) -> str:
    """与 timeline.json 比对，返回 Markdown 报告字符串。"""
    try:
        with open(golden_path, "r", encoding="utf-8") as f:
            golden_raw = json.load(f)
        golden_events: list[dict] = (
            golden_raw.get("events", golden_raw)
            if isinstance(golden_raw, dict)
            else golden_raw
        )
    except Exception as e:
        return f"## 无法读取 golden 文件：{e}\n"

    def in_window(ev: dict) -> bool:
        sd = ev.get("start_date", {})
        try:
            y, m, d = int(sd["year"]), int(sd["month"]), int(sd["day"])
            dt = date(y, m, d)
            if start_date and dt < start_date:
                return False
            if end_date and dt > end_date:
                return False
        except Exception:
            return False
        return True

    golden_filtered = [e for e in golden_events if in_window(e)]
    events_filtered = [e for e in events      if in_window(e)]

    lines = [
        f"# Timeline 比对报告（{start_date} ~ {end_date}）\n",
        f"- Golden 条目数（窗口内）：**{len(golden_filtered)}**",
        f"- 新脚本生成条目数：**{len(events_filtered)}**\n",
        "## 生成条目\n",
        "| 日期 | headline | media 类型 |",
        "|------|----------|------------|",
    ]
    for ev in events_filtered:
        sd     = ev["start_date"]
        dt_str = f"{sd['year']}-{sd['month']:>2s}-{sd['day']:>2s}"
        hl     = ev["text"]["headline"][:48]
        mu     = ev["media"]["url"]
        mtype  = "YouTube" if ("youtube" in mu or "youtu.be" in mu) else "Image"
        lines.append(f"| {dt_str} | {hl} | {mtype} |")

    lines += [
        "\n## Golden 条目\n",
        "| 日期 | headline | media 类型 |",
        "|------|----------|------------|",
    ]
    for ev in golden_filtered:
        sd     = ev["start_date"]
        dt_str = f"{sd['year']}-{sd['month']:>2s}-{sd['day']:>2s}"
        hl     = ev["text"]["headline"][:48]
        mu     = ev["media"]["url"]
        mtype  = "YouTube" if ("youtube" in mu or "youtu.be" in mu) else "Image"
        lines.append(f"| {dt_str} | {hl} | {mtype} |")

    lines.append("\n## Headline 差异（按日期对比）\n")
    g_by_date: dict[str, str] = {}
    for ev in golden_filtered:
        sd  = ev["start_date"]
        key = f"{sd['year']}-{sd['month']}-{sd['day']}"
        g_by_date.setdefault(key, ev["text"]["headline"])

    e_by_date: dict[str, str] = {}
    for ev in events_filtered:
        sd  = ev["start_date"]
        key = f"{sd['year']}-{sd['month']}-{sd['day']}"
        e_by_date.setdefault(key, ev["text"]["headline"])

    all_dates = sorted(set(list(g_by_date) + list(e_by_date)))
    lines.append("| 日期 | Golden headline | 生成 headline | 匹配 |")
    lines.append("|------|-----------------|---------------|------|")
    for dt_key in all_dates:
        g_hl = g_by_date.get(dt_key, "—")[:40]
        e_hl = e_by_date.get(dt_key, "—")[:40]
        match = "✓" if g_hl == e_hl else ("△" if g_hl != "—" and e_hl != "—" else "✗")
        lines.append(f"| {dt_key} | {g_hl} | {e_hl} | {match} |")

    return "\n".join(lines) + "\n"


# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "推特推文 → timeline.json events 格式转换工具\n"
            "自动分类 Cover / MV / 庆祝推文，对齐 timeline.json 字段规范"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例（2022-06 比对窗口）:\n"
            "  python fetch_tweets_timeline.py "
            "--user ASU_virtual --start 2022-06-01 --end 2022-06-30\n\n"
            "  # 含 golden diff\n"
            "  python fetch_tweets_timeline.py "
            "--user ASU_virtual --start 2022-06-01 --end 2022-06-30 "
            "--compare codes/src/data/timeline.json"
        ),
    )
    parser.add_argument("--user",  required=True, help="Twitter 用户名（不含 @）")
    parser.add_argument("--token", default=None,
                        help="Bearer Token（也可通过 TWITTER_TOKEN 环境变量传入）")
    parser.add_argument("--start", required=True, help="起始日期 YYYY-MM-DD（含）")
    parser.add_argument("--end",   default=None,  help="结束日期 YYYY-MM-DD（含，默认今天）")
    parser.add_argument("--chunk-days",   type=int,   default=30,
                        help="时间窗口天数（默认 30）")
    parser.add_argument("--delay",        type=float, default=2.0,
                        help="窗口间等待秒数（默认 2.0）")
    parser.add_argument("--oembed-delay", type=float, default=0.3,
                        help="每次 oEmbed 请求后等待秒数（默认 0.3）")
    parser.add_argument("--checkpoint-dir", default=None,
                        help="断点续传目录")
    parser.add_argument("--output",  default=None,
                        help="输出 JSON 路径（默认自动命名至仓库根目录）")
    parser.add_argument("--compare", default=None,
                        help="指定 golden timeline.json 路径，生成比对报告 _comparison.md")
    parser.add_argument("--include-unclassified", action="store_true",
                        help="在输出 JSON 中附加 unclassified 字段（调试用）")
    parser.add_argument(
        "--exclude-replies", action=argparse.BooleanOptionalAction, default=False,
        help=(
            "排除回复（默认关闭）。明透常在 YouTube 推文下以自回复发感想，"
            "建议保持默认开启回复抓取。"
        ),
    )
    parser.add_argument("--verbose", action="store_true",  default=True)
    parser.add_argument("--quiet",   dest="verbose", action="store_false")
    return parser.parse_args()


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    args  = parse_args()
    token = args.token or os.environ.get("TWITTER_TOKEN")
    if not token:
        print(
            "[ERROR] 请通过 --token 或 TWITTER_TOKEN 环境变量提供 Bearer Token",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
    except ValueError:
        print(f"[ERROR] --start 格式错误：{args.start}", file=sys.stderr)
        sys.exit(1)

    end_str = args.end or date.today().strftime("%Y-%m-%d")
    try:
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    except ValueError:
        print(f"[ERROR] --end 格式错误：{end_str}", file=sys.stderr)
        sys.exit(1)

    # Twitter API end_time 不含当天，+1 day 让 end_date 当天的推文也包含在内
    end_date_inclusive = end_date + timedelta(days=1)

    try:
        chunks = split_date_range(start_date, end_date_inclusive, args.chunk_days)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    print(
        f"[INFO] 时间范围：{start_date} ~ {end_date}，"
        f"共 {len(chunks)} 个窗口（每窗口 {args.chunk_days} 天）",
        file=sys.stderr,
    )

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

    exclude_list: list[str] = ["retweets"]
    if args.exclude_replies:
        exclude_list.append("replies")
    print(f"[INFO] exclude={','.join(exclude_list)}", file=sys.stderr)

    checkpoint_dir: Optional[Path] = None
    if args.checkpoint_dir:
        checkpoint_dir = Path(args.checkpoint_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

    # ── 逐窗口抓取原始推文 ──
    all_raw: dict[str, dict] = {}

    for idx, (cs, ce) in enumerate(chunks):
        cp = checkpoint_path(checkpoint_dir, idx, cs, ce) if checkpoint_dir else None

        if cp and cp.exists():
            with open(cp, "r", encoding="utf-8") as f:
                cached = json.load(f)
            all_raw.update(cached)
            print(
                f"[INFO] [{idx+1}/{len(chunks)}] {cs}~{ce}  "
                f"从断点加载 {len(cached)} 条",
                file=sys.stderr,
            )
            continue

        print(f"[INFO] [{idx+1}/{len(chunks)}] 抓取窗口 {cs} ~ {ce} ...",
              file=sys.stderr)
        try:
            chunk_data = fetch_raw_chunk(
                client, user_id, args.user, cs, ce,
                exclude=exclude_list,
            )
        except Exception as e:
            print(f"[WARN] [{idx+1}/{len(chunks)}] 窗口 {cs}~{ce} 失败：{e}",
                  file=sys.stderr)
            continue

        print(f"[INFO] [{idx+1}/{len(chunks)}] 获取 {len(chunk_data)} 条",
              file=sys.stderr)
        all_raw.update(chunk_data)

        if cp:
            with open(cp, "w", encoding="utf-8") as f:
                json.dump(chunk_data, f, ensure_ascii=False, indent=2)

        if idx < len(chunks) - 1 and args.delay > 0:
            time.sleep(args.delay)

    print(f"[INFO] 共 {len(all_raw)} 条原始推文，开始分类转换...", file=sys.stderr)

    # ── 分类转换 ──
    events, unclassified = convert_to_events(
        all_raw, args.user,
        oembed_delay=args.oembed_delay,
        verbose=args.verbose,
    )

    print(
        f"[INFO] 转换完成：{len(events)} 条已分类，{len(unclassified)} 条未分类",
        file=sys.stderr,
    )

    # 按日期升序排列（与 timeline.json events 顺序一致）
    def sort_key(ev: dict) -> tuple[int, int, int]:
        sd = ev["start_date"]
        return (int(sd["year"]), int(sd["month"]), int(sd["day"]))

    events.sort(key=sort_key)

    # ── 组装输出 ──
    if args.output:
        output_path = args.output
    else:
        ts           = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname        = f"tweets_timeline_{args.user}_{start_date}_{end_date}_{ts}.json"
        project_root = Path(__file__).resolve().parent.parent
        output_path  = str(project_root / fname)

    output_payload: Any = events
    if args.include_unclassified:
        output_payload = {"events": events, "unclassified": unclassified}

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)
    print(f"[OK] 已保存至：{output_path}", file=sys.stderr)

    # ── Golden 比对 ──
    if args.compare:
        report = compare_with_golden(
            events, args.compare,
            start_date=start_date,
            end_date=end_date,
        )
        report_path = str(Path(output_path).with_suffix("")) + "_comparison.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"[OK] 比对报告已保存至：{report_path}", file=sys.stderr)
        print(report, file=sys.stderr)

    print(json.dumps(output_payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
