"""下書き（単発・ツリー）を投稿前に検査する。ネットワークに出ません。

使い方
  python3 scripts/thread_check.py drafts/2026-11-01-tree.md
  python3 scripts/thread_check.py drafts/*.md

見るもの
  - 1投稿ごとの文字数（X の数え方で 280 以内）
  - 1本目の長さ（ツリーの1本目は短いほうが読まれやすい → 140 を超えたら注意）
  - 1本目の終わりに続きの合図（↓ など）があるか（ツリーのとき）
  - 最後の投稿に「次にしてほしいこと」があるか
  - URL の数（URL 入りは API の料金が約13倍・本文に入れるなら最後の1本だけ）
  - 禁止の言い回し（config/ng-words.txt）
"""
from __future__ import annotations

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401


import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).absolute().parent))
from textutil import MAX_WEIGHT, ROOT, has_url, read_draft, weighted_len  # noqa: E402

CTA_HINTS = ["プロフ", "固定", "保存", "いいね", "フォロー", "リプ", "DM", "コメント", "↓", "ここから", "受け取"]
NEXT_HINTS = ["↓", "👇", "続き", "スレッド", "ツリー", "解説します", "まとめました"]


def ng_words() -> list[str]:
    p = ROOT / "config" / "ng-words.txt"
    if not p.exists():
        return []
    return [w.strip() for w in p.read_text(encoding="utf-8").splitlines() if w.strip() and not w.startswith("#")]


def check(path: Path) -> int:
    meta, posts = read_draft(path)
    kind = meta.get("type", "tree" if len(posts) > 1 else "single")
    errors, warns = [], []
    if not posts:
        errors.append("投稿が1本もありません")
    ng = ng_words()
    for i, p in enumerate(posts, 1):
        w = weighted_len(p)
        if w > MAX_WEIGHT:
            errors.append(f"{i}本目が {w}/{MAX_WEIGHT}（日本語は1字2と数える）。{(w - MAX_WEIGHT + 1) // 2}字ほど削る")
        for word in ng:
            if word in p:
                errors.append(f"{i}本目に禁止の言い回し「{word}」")
        if has_url(p) and i != len(posts):
            warns.append(f"{i}本目に URL。URL は最後の1本かプロフへ（表示が落ちやすい・API 料金が約13倍）")
    if posts and kind == "tree":
        first = posts[0]
        if weighted_len(first) > 140:
            warns.append(f"1本目が {weighted_len(first)}。ツリーの1本目は 140 以内（全角70字）が目安")
        if not any(h in first for h in NEXT_HINTS):
            warns.append("1本目に続きの合図（↓ など）がありません")
        if not any(h in posts[-1] for h in CTA_HINTS):
            warns.append("最後の投稿に「次にしてほしいこと」（保存・プロフ・固定ポストなど）がありません")
    print(f"■ {path}（{kind}・{len(posts)}本）")
    for i, p in enumerate(posts, 1):
        print(f"  {i}本目 {weighted_len(p):>3}/{MAX_WEIGHT}  {p.splitlines()[0][:30]}")
    for e in errors:
        print(f"  🔴 {e}")
    for w in warns:
        print(f"  🟡 {w}")
    if not errors and not warns:
        print("  ✅ 問題なし")
    return 1 if errors else 0


def main() -> None:
    ap = argparse.ArgumentParser(description="下書きの検査（投稿はしません）")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    rc = 0
    for f in a.files:
        rc |= check(Path(f))
    sys.exit(rc)


if __name__ == "__main__":
    main()
