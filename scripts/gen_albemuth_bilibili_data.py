"""从 B 站 x/series/archives 拉取合集 3337044，更新 data/albemuth_music_data.json 中的投稿表（保留已有 discography）。"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

TZ = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "albemuth_music_data.json"
API = (
    "https://api.bilibili.com/x/series/archives"
    "?mid=1634470651&series_id=3337044&only_normal=true&sort=pubtime&pn=1&ps=100"
)

req = Request(
    API,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://space.bilibili.com/1634470651/lists/3337044",
    },
)
with urlopen(req, timeout=60) as resp:
    raw = json.loads(resp.read().decode("utf-8"))

if raw.get("code") != 0:
    raise SystemExit(raw)

archives = raw["data"]["archives"]
rows = []

for a in archives:
    pub = datetime.fromtimestamp(a["pubdate"], tz=TZ)
    date_cn = f"{pub.year}年{pub.month}月{pub.day}日"
    bvid = a["bvid"]
    rows.append(
        {
            "date": date_cn,
            "title": a["title"],
            "watch": {
                "url": f"https://www.bilibili.com/video/{bvid}",
                "label": bvid,
            },
        }
    )

existing: dict = {}
if OUT.exists():
    try:
        existing = json.loads(OUT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        existing = {}

payload = {
    "source": "https://space.bilibili.com/1634470651/lists/3337044?type=series",
    "section": "作品概览 · Albemuth 投稿视频（B站合集）",
    "note": "对照 B 站空间合集 id=3337044 自动拉取，投稿时间为稿件 pubdate（UTC+8）。",
    "updated": datetime.now(TZ).date().isoformat(),
    "columns": ["投稿时间", "歌曲名称", "链接"],
    "rows": rows,
}
if "discography" in existing:
    payload["discography"] = existing["discography"]

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(len(rows), "rows ->", OUT)
