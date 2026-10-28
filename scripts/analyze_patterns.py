"""集めた投稿から「伸びている型」を数える。ネットワークに出ません。

使い方
  python3 scripts/analyze_patterns.py data/research/2026-11-01-ai副業.json
  python3 scripts/analyze_patterns.py samples/sample_search.json      # 見本で試す

入力は research.py が保存した JSON（X API の検索結果そのまま）。
出力は data/research/<元の名前>-patterns.md（エージェントがこれを読んで企画を立てる）。

数え方
  - 伸び   … 表示（impression_count）。無いときは いいね＋リポスト×2＋保存×2
  - 保存率 … 保存 ÷ 表示（後から読み返したい中身か）
  - 型     … 1行目の作り（数字・問い・断言・体験・一覧）、行数、長さ、画像の有無、続きの合図
  ※ 型の判定は言葉の手がかりで機械的に付けています。最後は人とエージェントが本文を読んで確かめてください。
"""
from __future__ import annotations

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401


import argparse
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).absolute().parent))
from textutil import load_json, weighted_len  # noqa: E402

HOOKS = [
    ("数字", re.compile(r"^\D{0,6}\d|[0-9０-９]+(選|個|つ|本|倍|万|円|%|％|日|時間|分)")),
    ("問いかけ", re.compile(r"[?？]|なぜ|どうして|知ってる|ですか")),
    ("体験", re.compile(r"てみた|てみて|した結果|続けた結果|やってみ|試した|使ってみ")),
    ("断言", re.compile(r"(だけ|しかない|べき|一択|9割|正解|結論|絶対)")),
    ("一覧", re.compile(r"^\s*([・\-•①-⑳]|\d+[.)．])", re.M)),
]


def hook_type(text: str) -> str:
    first = text.strip().splitlines()[0] if text.strip() else ""
    for name, rx in HOOKS:
        if name == "一覧":
            if len(rx.findall(text)) >= 3:
                return name
        elif rx.search(first):
            return name
    return "その他"


def score(m: dict) -> float:
    imp = m.get("impression_count") or 0
    if imp:
        return float(imp)
    return float(m.get("like_count", 0) + 2 * m.get("retweet_count", 0) + 2 * m.get("bookmark_count", 0))


def features(t: dict) -> dict:
    text = t.get("text", "")
    m = t.get("public_metrics", {})
    imp = m.get("impression_count") or 0
    return {
        "id": t.get("id"),
        "author_id": t.get("author_id"),
        "text": text,
        "hook": hook_type(text),
        "lines": len([l for l in text.splitlines() if l.strip()]),
        "weight": weighted_len(text),
        "media": bool(t.get("attachments", {}).get("media_keys")),
        "next_sign": any(s in text for s in ["↓", "👇", "スレッド", "続き"]),
        "score": score(m),
        "save_rate": (m.get("bookmark_count", 0) / imp) if imp else None,
        "metrics": m,
    }


def summarize(rows: list[dict], key: str) -> list[tuple]:
    g = defaultdict(list)
    for r in rows:
        g[r[key]].append(r)
    out = []
    for k, rs in g.items():
        sc = [r["score"] for r in rs]
        sv = [r["save_rate"] for r in rs if r["save_rate"] is not None]
        out.append((k, len(rs), statistics.median(sc), statistics.median(sv) if sv else None))
    return sorted(out, key=lambda x: -x[2])


def main() -> None:
    ap = argparse.ArgumentParser(description="伸びている型を数える（投稿はしません）")
    ap.add_argument("file")
    ap.add_argument("--top", type=int, default=10, help="本文を載せる上位の数")
    a = ap.parse_args()
    src = Path(a.file)
    d = load_json(src)
    users = {u["id"]: u for u in d.get("includes", {}).get("users", [])}
    rows = [features(t) for t in d.get("data", [])]
    if not rows:
        sys.exit("[止まりました] 投稿が0件です。research.py の条件を広げてください。")
    rows.sort(key=lambda r: -r["score"])

    lines = [f"# 伸びている型（{src.name}・{len(rows)}件）", "",
             "数字は中央値。件数が5件未満の型は、たまたまの可能性が高いので決め手にしない。", ""]
    for title, key in [("1行目の作り", "hook"), ("画像あり", "media"), ("続きの合図あり", "next_sign")]:
        lines += [f"## {title}", "", "| 型 | 件数 | 伸び（中央値） | 保存率（中央値） |", "|---|---|---|---|"]
        for k, n, sc, sv in summarize(rows, key):
            lines.append(f"| {k} | {n} | {sc:,.0f} | {'' if sv is None else f'{sv:.2%}'} |")
        lines.append("")
    w = [r["weight"] for r in rows[: max(3, len(rows) // 3)]]
    ln = [r["lines"] for r in rows[: max(3, len(rows) // 3)]]
    lines += ["## 上位3分の1の長さ", "",
              f"- 文字の重さ（280が上限）中央値 {statistics.median(w):.0f}",
              f"- 行数 中央値 {statistics.median(ln):.0f}", ""]
    lines += [f"## 上位{min(a.top, len(rows))}件の本文（型をまねる材料・文言はまねない）", ""]
    for r in rows[: a.top]:
        u = users.get(r["author_id"], {})
        name = u.get("username", "?")
        lines += [f"### {r['score']:,.0f}（{r['hook']}・{r['lines']}行・@{name}）", "",
                  "> " + r["text"].replace("\n", "\n> "), ""]
    out = src.with_name(src.stem + "-patterns.md")
    if src.parent.name == "samples":
        out = Path(__file__).absolute().parent.parent / "data" / "research" / out.name
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ {len(rows)}件を数えました → {out}")
    for k, n, sc, sv in summarize(rows, "hook")[:3]:
        print(f"   {k}: {n}件・伸び中央値 {sc:,.0f}")


if __name__ == "__main__":
    main()
