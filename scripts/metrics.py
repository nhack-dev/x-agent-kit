"""自分の投稿の数字を取る（表示・いいね・リポスト・返信・引用・保存・プロフへのアクセス・リンクのクリック）。

使い方
  python3 scripts/metrics.py --days 7            # 見積もりだけ（既定・キー不要）
  python3 scripts/metrics.py --days 7 --go       # 取る → data/metrics/<日付>.json → review.py
  python3 scripts/metrics.py --mentions --go     # 自分宛ての @ を読む → data/mentions/<日付>.json

X の決まり（https://docs.x.com/x-api/fundamentals/metrics）
  - プロフへのアクセス（user_profile_clicks）・リンクのクリック（url_link_clicks）は
    自分の投稿だけ・投稿から30日以内だけ・自分としてのログイン（OAuth）で取れる。だから --days は30まで。
費用  自分の投稿・自分宛ては1件約0.001ドル。
"""
from __future__ import annotations

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401


import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).absolute().parent))
from textutil import ROOT, save_json  # noqa: E402

PRICE_OWN = 0.001


def main() -> None:
    ap = argparse.ArgumentParser(description="自分の投稿の数字を取る（--go が無ければ読まない）")
    ap.add_argument("--days", type=int, default=7, help="何日前の投稿まで（1〜30）")
    ap.add_argument("--max", type=int, default=100, help="最大何本（5〜100）")
    ap.add_argument("--mentions", action="store_true", help="自分宛ての @ を読む")
    ap.add_argument("--go", action="store_true", help="本当に読む")
    a = ap.parse_args()
    days = max(1, min(30, a.days))
    n = max(5, min(100, a.max))
    what = f"直近{days}日の自分宛ての @" if a.mentions else f"直近{days}日の自分の投稿"
    print(f"■ {what}を最大 {n} 件読みます（約 {(n + 1) * PRICE_OWN:.3f} ドル）")
    if not a.go:
        print("  （見積もりだけ。読むには --go を付けてください）")
        return

    from xlib import my_user_id, request

    uid = my_user_id()
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    if a.mentions:
        q = {"max_results": n, "start_time": start,
             "tweet.fields": "created_at,author_id,conversation_id,public_metrics",
             "expansions": "author_id", "user.fields": "username,name"}
        res = request("GET", f"/2/users/{uid}/mentions", q, auth="user")
        out = ROOT / "data" / "mentions" / f"{date.today()}.json"
    else:
        q = {"max_results": n, "start_time": start, "exclude": "retweets",
             "tweet.fields": "created_at,public_metrics,non_public_metrics,conversation_id,in_reply_to_user_id"}
        res = request("GET", f"/2/users/{uid}/tweets", q, auth="user")
        out = ROOT / "data" / "metrics" / f"{date.today()}.json"
    save_json(out, res)
    print(f"✅ {res.get('meta', {}).get('result_count', 0)}件 → {out}")
    if not a.mentions:
        print("   次に python3 scripts/review.py で表にしてください。")


if __name__ == "__main__":
    main()
