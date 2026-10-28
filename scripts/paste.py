"""検査が通った下書きを、X の画面に貼りやすい形で出す。ネットワークに出ません。

使い方
  python3 scripts/paste.py drafts/2026-11-01-tree.md
  python3 scripts/paste.py drafts/2026-11-01-tree.md --one 2     # 2本目だけ（コピーしやすい）

貼り方（ツリー）
  1本目を投稿 → その投稿の「返信」に2本目 → 2本目の「返信」に3本目 … の順。
  X の投稿画面の「＋」で、1回でまとめてツリーにして投稿・予約することもできます。
"""
from __future__ import annotations

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401


import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).absolute().parent))
from textutil import ROOT, read_draft, weighted_len  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="貼る用に出す")
    ap.add_argument("draft")
    ap.add_argument("--one", type=int, help="この番号の投稿だけ出す")
    a = ap.parse_args()
    path = Path(a.draft)
    chk = subprocess.run([sys.executable, str(ROOT / "scripts" / "thread_check.py"), str(path)],
                         capture_output=True, text=True)
    if chk.returncode != 0:
        print(chk.stdout)
        sys.exit("[止まりました] 検査で 🔴 が出ています。直してから貼ってください。")
    meta, posts = read_draft(path)
    for k in ("quote_url", "reply_url", "at"):
        if meta.get(k):
            print(f"【{ {'quote_url': '引用する投稿', 'reply_url': '返信する投稿', 'at': '予約する時刻'}[k] }】{meta[k]}")
    for i, p in enumerate(posts, 1):
        if a.one and i != a.one:
            continue
        print(f"\n===== {i}/{len(posts)}本目（{weighted_len(p)}/280）=====")
        print(p)
    print()


if __name__ == "__main__":
    main()
