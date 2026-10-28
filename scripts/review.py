"""自分の投稿の数字を振り返り、次の企画に使う表を作る。ネットワークに出ません。

使い方
  python3 scripts/review.py                          # data/metrics/ の一番新しいファイル
  python3 scripts/review.py data/metrics/2026-11-08.json
  python3 scripts/review.py samples/sample_metrics.json   # 見本で試す

入力  metrics.py が保存した JSON（自分の投稿と数字）
      data/posted.jsonl（post.py が投稿のたびに残す・下書きの type / hook / theme が入る）
出力  data/reviews/<日付>.md

見る数字（どれも「表示」で割る）
  保存率        … 保存 ÷ 表示       役に立つ・後で見返したい中身か
  プロフ率      … プロフへのアクセス ÷ 表示   あなたに興味を持ったか（フォローの手前）
  いいね率      … いいね ÷ 表示
  ※ プロフへのアクセスは投稿から30日以内・自分の投稿だけ取れます（X の決まり）。
"""
from __future__ import annotations

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401


import argparse
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).absolute().parent))
from textutil import ROOT, load_json, read_jsonl  # noqa: E402


def rate(a, b):
    return (a / b) if b else None


def pct(x):
    return "-" if x is None else f"{x:.2%}"


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def main() -> None:
    ap = argparse.ArgumentParser(description="数字の振り返り（投稿はしません）")
    ap.add_argument("file", nargs="?")
    a = ap.parse_args()
    if a.file:
        src = Path(a.file)
    else:
        files = sorted((ROOT / "data" / "metrics").glob("*.json"))
        if not files:
            sys.exit("[止まりました] data/metrics/ が空です。先に metrics.py --go を動かすか、samples/sample_metrics.json で試してください。")
        src = files[-1]
    posts = load_json(src).get("data", [])
    meta = {r.get("id"): r for r in read_jsonl(ROOT / "data" / "posted.jsonl")}
    rows = []
    for t in posts:
        pm = t.get("public_metrics", {})
        npm = t.get("non_public_metrics", {})
        imp = pm.get("impression_count", 0)
        m = meta.get(t["id"], {}) or t.get("kit", {})
        if int(m.get("n", 1) or 1) > 1:
            continue  # ツリーの2本目以降は1本目の数字で見る（数えると本数が水増しになる）
        rows.append({
            "id": t["id"], "text": t.get("text", ""), "created_at": t.get("created_at", ""),
            "imp": imp, "like": pm.get("like_count", 0), "save": pm.get("bookmark_count", 0),
            "profile": npm.get("user_profile_clicks"), "link": npm.get("url_link_clicks"),
            "save_r": rate(pm.get("bookmark_count", 0), imp),
            "prof_r": rate(npm.get("user_profile_clicks", 0), imp) if "user_profile_clicks" in npm else None,
            "like_r": rate(pm.get("like_count", 0), imp),
            "type": m.get("type", "?"), "hook": m.get("hook", "?"), "theme": m.get("theme", "?"),
        })
    if not rows:
        sys.exit("[止まりました] 投稿が0件です。")
    rows.sort(key=lambda r: -r["imp"])
    L = [f"# 振り返り（{src.name}・{len(rows)}本・作成 {date.today()}）", "",
         "| | 表示 | 保存率 | プロフ率 | いいね率 | 型 | 1行目 |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        first = r["text"].splitlines()[0][:24] if r["text"] else ""
        L.append(f"| {r['id'][-6:]} | {r['imp']:,} | {pct(r['save_r'])} | {pct(r['prof_r'])} | {pct(r['like_r'])} | {r['type']}/{r['hook']} | {first} |")
    L.append("")
    for key, title in [("type", "投稿の種類ごと"), ("hook", "1行目の型ごと"), ("theme", "テーマごと")]:
        g = defaultdict(list)
        for r in rows:
            g[r[key]].append(r)
        L += [f"## {title}", "", "| | 本数 | 表示（中央値） | 保存率 | プロフ率 |", "|---|---|---|---|---|"]
        for k, rs in sorted(g.items(), key=lambda kv: -(med([r["imp"] for r in kv[1]]) or 0)):
            L.append(f"| {k} | {len(rs)} | {med([r['imp'] for r in rs]) or 0:,.0f} | {pct(med([r['save_r'] for r in rs]))} | {pct(med([r['prof_r'] for r in rs]))} |")
        L.append("")
    # 次の企画への手がかり（機械が出す仮説。決めるのは人とエージェント）
    best_save = max(rows, key=lambda r: r["save_r"] or 0)
    best_prof = max(rows, key=lambda r: r["prof_r"] or 0)
    m_imp = med([r["imp"] for r in rows]) or 0
    L += ["## 次の企画への仮説（機械が出したもの・本文を読んで確かめる）", "",
          f"- 保存率が一番高い投稿（{pct(best_save['save_r'])}）の中身の型を、次の1週間でもう2本試す",
          f"- プロフ率が一番高い投稿（{pct(best_prof['prof_r'])}）の最後の一文（誘導）を、他の投稿の締めにも使う",
          f"- 表示が中央値（{m_imp:,.0f}）の半分未満だった投稿は、1行目だけ書き直して別の日に出し直す候補",
          "- 本数が3本未満の型は、まだ判断しない（たまたまの差が大きい）", ""]
    out = ROOT / "data" / "reviews" / f"{date.today()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"✅ {len(rows)}本を振り返りました → {out}")


if __name__ == "__main__":
    main()
