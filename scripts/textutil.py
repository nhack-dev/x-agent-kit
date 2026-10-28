"""文字数・下書きファイル・保存の共通部品（ネットワークに出ない）。"""
from __future__ import annotations

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401


import json
import re
from pathlib import Path

ROOT = Path(__file__).absolute().parent.parent
MAX_WEIGHT = 280

URL_RE = re.compile(r"https?://\S+")
# X の数え方（twitter-text v3）：この範囲は1、それ以外（日本語・絵文字など）は2。URL は長さに関係なく23。
_ONE = [(0, 4351), (8192, 8205), (8208, 8223), (8242, 8247)]


def weighted_len(text: str) -> int:
    n = 23 * len(URL_RE.findall(text))
    for ch in URL_RE.sub("", text):
        c = ord(ch)
        n += 1 if any(a <= c <= b for a, b in _ONE) else 2
    return n


def has_url(text: str) -> bool:
    return bool(URL_RE.search(text))


def read_draft(path: Path) -> tuple[dict, list[str]]:
    """下書きを読む。先頭の --- で囲んだ所が設定、そのあとを '---' だけの行で区切って投稿の一覧にする。"""
    raw = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    meta: dict = {}
    if raw.startswith("---\n"):
        head, _, raw = raw[4:].partition("\n---\n")
        for line in head.splitlines():
            if ":" in line:
                a, b = line.split(":", 1)
                meta[a.strip()] = b.strip()
    posts = []
    for p in re.split(r"\n-{3,}\n", "\n" + raw + "\n"):
        p = re.sub(r"<!--.*?-->", "", p, flags=re.S).strip()
        if p:
            posts.append(p)
    return meta, posts


def save_json(path: Path, obj) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def append_jsonl(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
