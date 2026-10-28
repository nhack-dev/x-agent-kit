"""手で集めたもの（画面で見た投稿・数字）を、道具が読める形にする。ネットワークに出ません。

API を使わずに運用するための入口です。

使い方
  ① 自分の投稿の数字（振り返り用）
     python3 scripts/import_manual.py metrics data/metrics-manual.csv
     → data/metrics/<日付>-manual.json（そのあと python3 scripts/review.py）
     書き方は templates/metrics-manual.csv（投稿の「アナリティクス」画面を見て1投稿1行）

  ② 伸びている投稿（リサーチ用）
     python3 scripts/import_manual.py research data/research/manual-2026-11-01.md
     → data/research/manual-2026-11-01.json（そのあと python3 scripts/analyze_patterns.py）
     書き方は templates/research-manual.md（X の画面で見た投稿を1つずつ貼る）
"""
from __future__ import annotations

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401


import argparse
import csv
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).absolute().parent))
from textutil import ROOT, read_draft, save_json  # noqa: E402

NAMES = {"表示": "impression_count", "いいね": "like_count", "リポスト": "retweet_count",
         "返信": "reply_count", "保存": "bookmark_count", "引用": "quote_count"}


def num(v) -> int:
    v = str(v or "").replace(",", "").strip()
    try:
        return int(float(v)) if v else 0
    except ValueError:
        return 0


def do_metrics(path: Path) -> None:
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    data = []
    for i, r in enumerate(rows, 2):
        m = re.search(r"status/(\d+)", r.get("url", ""))
        t = {
            "id": m.group(1) if m else f"manual-{i}", "created_at": r.get("date", ""), "text": r.get("first_line", ""),
            "public_metrics": {"impression_count": num(r.get("impressions")), "like_count": num(r.get("likes")),
                               "retweet_count": num(r.get("reposts")), "reply_count": num(r.get("replies")),
                               "bookmark_count": num(r.get("bookmarks")), "quote_count": 0},
            "kit": {"type": r.get("type") or "?", "hook": r.get("hook") or "?", "theme": r.get("theme") or "?"},
        }
        if (r.get("profile_visits") or "").strip():
            t["non_public_metrics"] = {"user_profile_clicks": num(r.get("profile_visits")),
                                       "url_link_clicks": num(r.get("link_clicks"))}
        data.append(t)
    if not data:
        sys.exit("[止まりました] 行が0です。")
    out = save_json(ROOT / "data" / "metrics" / f"{date.today()}-manual.json", {"data": data})
    print(f"✅ {len(data)}行を取り込みました → {out}\n   次に python3 scripts/review.py {out}")


def do_research(path: Path) -> None:
    _, blocks = read_draft(path)
    data, users = [], {}
    for i, b in enumerate(blocks, 1):
        head, _, body = b.partition("\n")
        pm = {v: 0 for v in NAMES.values()}
        for k, v in re.findall(r"(\S+?)=(\S+)", head):
            if k in NAMES:
                pm[NAMES[k]] = num(v)
        if not body.strip():
            print(f"  🟡 {i}件目は本文がないので外しました")
            continue
        u = re.search(r"@(\w+)", head)
        if u and u.group(1) not in users:
            users[u.group(1)] = str(1000 + len(users))
        t = {"id": f"manual-{i}", "author_id": users.get(u.group(1)) if u else "", "text": body.strip(),
             "public_metrics": pm}
        if re.search(r"画像=(あり|有|yes)", head):
            t["attachments"] = {"media_keys": [f"m{i}"]}
        data.append(t)
    if not data:
        sys.exit("[止まりました] 投稿が0件です。templates/research-manual.md の形で貼ってください。")
    inc = [{"id": v, "username": k} for k, v in users.items()]
    out = save_json(path.with_suffix(".json"), {"data": data, "includes": {"users": inc}})
    print(f"✅ {len(data)}件を取り込みました → {out}\n   次に python3 scripts/analyze_patterns.py {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description="手で集めたものを取り込む")
    ap.add_argument("kind", choices=["metrics", "research"])
    ap.add_argument("file")
    a = ap.parse_args()
    (do_metrics if a.kind == "metrics" else do_research)(Path(a.file))


if __name__ == "__main__":
    main()
