"""伸びている投稿を集める（直近7日の検索・参考アカウントの最近の投稿・自分のプロフ）。

使い方
  python3 scripts/research.py "AI 副業 -is:retweet lang:ja" --max 50        # 見積もりだけ（既定・キー不要）
  python3 scripts/research.py "AI 副業 -is:retweet lang:ja" --max 50 --go   # 読む（クレジットが減る）
  python3 scripts/research.py --user example_account --max 30 --go         # そのアカウントの最近の投稿
  python3 scripts/research.py --me --go                                    # 自分のプロフと固定ポスト

保存先  data/research/<日付>-<語>.json（そのまま analyze_patterns.py に渡せる）
費用    他の人の投稿は1件約0.005ドル。--max の数だけかかると考える。
決まり  検索は直近7日・1回10〜100件（X の決まり）。自動でくり返して大量に集める使い方はしない。
"""
from __future__ import annotations

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401


import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).absolute().parent))
from textutil import ROOT, save_json  # noqa: E402

PRICE_READ = 0.005
PRICE_OWN = 0.001
FIELDS = {
    "tweet.fields": "created_at,public_metrics,author_id,conversation_id,attachments,lang",
    "expansions": "author_id,attachments.media_keys",
    "user.fields": "username,name,public_metrics,description",
    "media.fields": "type",
}


def slug(s: str) -> str:
    s = re.sub(r"-?\S+:\S+", "", s)
    s = re.sub(r"[^\w぀-ヿ一-鿿]+", "-", s).strip("-")
    return s[:30] or "search"


def main() -> None:
    ap = argparse.ArgumentParser(description="伸びている投稿を集める（--go が無ければ読まない）")
    ap.add_argument("query", nargs="?", help="検索の語（X の検索の書き方が使えます）")
    ap.add_argument("--user", help="このアカウントの最近の投稿を読む（@ なし）")
    ap.add_argument("--me", action="store_true", help="自分のプロフと固定ポストを読む")
    ap.add_argument("--max", type=int, default=50, help="読む件数（10〜100）")
    ap.add_argument("--sort", default="relevancy", choices=["relevancy", "recency"])
    ap.add_argument("--go", action="store_true", help="本当に読む（お金がかかる）")
    a = ap.parse_args()
    n = max(10, min(100, a.max))
    if not (a.query or a.user or a.me):
        ap.error("検索の語・--user・--me のどれかを指定してください")

    if a.me:
        print(f"■ 自分のプロフと固定ポストを読みます（約 {2 * PRICE_OWN:.3f} ドル）")
    elif a.user:
        print(f"■ @{a.user} の最近の投稿を {n} 件読みます（約 {n * PRICE_READ + PRICE_READ:.3f} ドル）")
    else:
        print(f"■ 「{a.query}」を直近7日から {n} 件読みます（約 {n * PRICE_READ:.3f} ドル）")
    if not a.go:
        print("  （見積もりだけ。読むには --go を付けてください。正しい額と残高は開発者コンソールで）")
        return

    import os
    from xlib import load_env, request  # 読むときだけ読み込む

    if a.me:
        load_env()
        name = os.environ.get("X_USERNAME", "")
        if not name:
            sys.exit("[止まりました] .env に X_USERNAME がありません。")
        res = request("GET", f"/2/users/by/username/{name}",
                      {"user.fields": "description,public_metrics,pinned_tweet_id,url",
                       "expansions": "pinned_tweet_id", "tweet.fields": "public_metrics,created_at"})
        out = ROOT / "data" / "research" / f"{date.today()}-me.json"
    elif a.user:
        u = request("GET", f"/2/users/by/username/{a.user}", {"user.fields": "username,public_metrics"})
        uid = u.get("data", {}).get("id")
        if not uid:
            sys.exit(f"[止まりました] @{a.user} が見つかりません。")
        q = dict(FIELDS, max_results=n, exclude="retweets,replies")
        res = request("GET", f"/2/users/{uid}/tweets", q)
        res.setdefault("includes", {}).setdefault("users", []).append(u["data"])
        out = ROOT / "data" / "research" / f"{date.today()}-user-{a.user}.json"
    else:
        q = dict(FIELDS, query=a.query, max_results=n, sort_order=a.sort)
        res = request("GET", "/2/tweets/search/recent", q)
        out = ROOT / "data" / "research" / f"{date.today()}-{slug(a.query)}.json"
    save_json(out, res)
    got = res.get("data", [])
    print(f"✅ {len(got) if isinstance(got, list) else 1}件 → {out}")


if __name__ == "__main__":
    main()
