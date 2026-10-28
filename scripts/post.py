"""下書き（単発・ツリー・自分宛てへの返事）を投稿する。

使い方
  python3 scripts/post.py drafts/2026-11-01-tree.md          # 何が出るかと費用の目安だけ（既定）
  python3 scripts/post.py drafts/2026-11-01-tree.md --go     # 本当に投稿する

下書きの書き方は templates/ を見てください。
  type: single / tree … 1本目を投稿し、ツリーなら2本目以降を1本前への返信としてつなぐ
  type: reply        … 各投稿の先頭行に reply_to: <投稿ID> を書く（自分を @ で呼んだ投稿にだけ返せる）
  type: quote        … API では作れないので止まる（手で貼る）

ツリーの2本目で断られたら（返信の制限）、残りを drafts/manual/ に書き出して止まります。
投稿したものは data/posted.jsonl に1行ずつ残ります（振り返りで使う）。
"""
from __future__ import annotations

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401


import argparse
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).absolute().parent))
from textutil import MAX_WEIGHT, ROOT, append_jsonl, has_url, read_draft, weighted_len  # noqa: E402

PRICE_POST = 0.015
PRICE_POST_URL = 0.200


def cost(posts: list[str]) -> float:
    return sum(PRICE_POST_URL if has_url(p) else PRICE_POST for p in posts)


def split_reply_to(p: str) -> tuple[str | None, str]:
    m = re.match(r"reply_to:\s*(\d+)\s*\n", p)
    if m:
        return m.group(1), p[m.end():].strip()
    return None, p


def write_manual(path: Path, posts: list[str], parent_id: str | None, why: str) -> Path:
    out = ROOT / "drafts" / "manual" / (path.stem + "-manual.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    head = [f"# 手で貼る分（{why}）", ""]
    if parent_id:
        head += [f"返信先：https://x.com/i/web/status/{parent_id} にこの順で返信してください", ""]
    out.write_text("\n".join(head) + "\n\n---\n\n".join(posts) + "\n", encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="下書きを投稿する（--go が無ければ投稿しない）")
    ap.add_argument("draft")
    ap.add_argument("--go", action="store_true", help="本当に投稿する")
    ap.add_argument("--gap", type=float, default=3.0, help="ツリーの1本ごとの間（秒）")
    a = ap.parse_args()
    path = Path(a.draft)
    meta, posts = read_draft(path)
    kind = meta.get("type", "tree" if len(posts) > 1 else "single")
    if kind == "quote":
        sys.exit("[止まりました] 引用投稿は API では Enterprise 契約だけです。人が X の画面で引用して貼ってください（playbooks/03）。")
    if not posts:
        sys.exit("[止まりました] 投稿が0本です。")
    bodies = [split_reply_to(p)[1] for p in posts]
    over = [i + 1 for i, b in enumerate(bodies) if weighted_len(b) > MAX_WEIGHT]
    if over:
        sys.exit(f"[止まりました] {over} 本目が 280 を超えています。thread_check.py で直してください。")

    print(f"■ {path}（{kind}・{len(posts)}本）")
    for i, b in enumerate(bodies, 1):
        print(f"  {i}本目 {weighted_len(b):>3}/{MAX_WEIGHT}{' URLあり' if has_url(b) else ''}  {b.splitlines()[0][:30]}")
    print(f"  費用の目安 約 {cost(bodies):.3f} ドル（正しい額は開発者コンソールで）")
    if not a.go:
        print("  （見るだけ。投稿するには --go を付けてください）")
        return

    from xlib import request  # 投稿するときだけ読み込む

    prev_id = None
    for i, p in enumerate(posts, 1):
        reply_to, body = split_reply_to(p)
        payload: dict = {"text": body}
        if kind == "reply":
            if not reply_to:
                sys.exit(f"[止まりました] {i}本目に reply_to: がありません。")
            payload["reply"] = {"in_reply_to_tweet_id": reply_to}
        elif kind == "tree" and prev_id:
            payload["reply"] = {"in_reply_to_tweet_id": prev_id}
        try:
            res = request("POST", "/2/tweets", body=payload, auth="user", exit_on_error=False)
        except RuntimeError as e:
            if kind == "tree" and i > 1:
                out = write_manual(path, posts[i - 1:], prev_id, f"{i}本目で断られた")
                sys.exit(f"[止まりました] {i}本目で断られました：{e}\n残りを手で貼る分にしました → {out}")
            sys.exit(f"[止まりました] {e}")
        new_id = res.get("data", {}).get("id")
        print(f"  ✅ {i}本目 https://x.com/i/web/status/{new_id}")
        append_jsonl(ROOT / "data" / "posted.jsonl", {
            "id": new_id, "at": datetime.now(timezone.utc).isoformat(), "draft": str(path),
            "n": i, "of": len(posts), "type": kind, "hook": meta.get("hook", ""), "theme": meta.get("theme", ""),
            "reply_to": payload.get("reply", {}).get("in_reply_to_tweet_id"),
        })
        prev_id = new_id
        if i < len(posts):
            time.sleep(a.gap)


if __name__ == "__main__":
    main()
