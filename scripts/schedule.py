"""手元の予約表（queue/）。X API には予約の項目が無いので、時刻が来たら post.py で出します。

使い方
  python3 scripts/schedule.py add drafts/2026-11-01-tree.md   # 予約表に入れる（下書きに at: が要る）
  python3 scripts/schedule.py list                            # 予約表を見る
  python3 scripts/schedule.py run                             # 時刻が来た分を見るだけ
  python3 scripts/schedule.py run --go                        # 時刻が来た分を投稿する（5分おきに動かす）
  python3 scripts/schedule.py remove 2026-11-01-tree.md       # 予約を外す

at: の書き方 … 2026-11-01T19:00+09:00（タイムゾーンまで書く）
遅れの上限 … 予定から60分を過ぎた分は投稿せず queue/late/ に移します（時刻がずれた投稿を出さないため）。
"""
from __future__ import annotations

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401


import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).absolute().parent))
from textutil import ROOT, read_draft  # noqa: E402

Q = ROOT / "queue"
LATE_LIMIT = timedelta(minutes=60)


def when(path: Path) -> datetime | None:
    meta, _ = read_draft(path)
    at = meta.get("at", "")
    try:
        d = datetime.fromisoformat(at)
    except ValueError:
        return None
    return d if d.tzinfo else None


def items() -> list[tuple[datetime, Path]]:
    out = []
    for p in sorted(Q.glob("*.md")):
        d = when(p)
        if d:
            out.append((d, p))
    return sorted(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="手元の予約表")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add"); s.add_argument("draft")
    sub.add_parser("list")
    s = sub.add_parser("run"); s.add_argument("--go", action="store_true")
    s = sub.add_parser("remove"); s.add_argument("name")
    a = ap.parse_args()
    Q.mkdir(exist_ok=True)

    if a.cmd == "add":
        src = Path(a.draft)
        d = when(src)
        if not d:
            sys.exit("[止まりました] 下書きの先頭に at: 2026-11-01T19:00+09:00 の形で時刻を書いてください（タイムゾーンまで）。")
        if d < datetime.now(timezone.utc):
            sys.exit(f"[止まりました] 時刻 {d.isoformat()} はもう過ぎています。")
        chk = subprocess.run([sys.executable, str(ROOT / "scripts" / "thread_check.py"), str(src)])
        if chk.returncode != 0:
            sys.exit("[止まりました] 検査で 🔴 が出ました。直してから入れてください。")
        dst = Q / src.name
        if dst.exists():
            sys.exit(f"[止まりました] 同じ名前の予約があります：{dst.name}")
        shutil.copy2(src, dst)
        print(f"✅ 予約表に入れました：{dst.name}（{d.astimezone().strftime('%m/%d %H:%M')}）")
    elif a.cmd == "list":
        it = items()
        if not it:
            print("予約表は空です。")
        for d, p in it:
            print(f"  {d.astimezone().strftime('%m/%d(%a) %H:%M')}  {p.name}")
    elif a.cmd == "remove":
        p = Q / a.name
        if not p.exists():
            sys.exit(f"[止まりました] {a.name} は予約表にありません。")
        (Q / "removed").mkdir(exist_ok=True)
        shutil.move(str(p), Q / "removed" / p.name)
        print(f"✅ 外しました：{a.name}（queue/removed/ に残しています）")
    elif a.cmd == "run":
        now = datetime.now(timezone.utc)
        due = [(d, p) for d, p in items() if d <= now]
        if not due:
            print("時刻が来た予約はありません。")
            return
        for d, p in due:
            if now - d > LATE_LIMIT:
                (Q / "late").mkdir(exist_ok=True)
                if a.go:
                    shutil.move(str(p), Q / "late" / p.name)
                print(f"  ⏭ {p.name} は予定から60分以上過ぎたので出しません → queue/late/")
                continue
            cmd = [sys.executable, str(ROOT / "scripts" / "post.py"), str(p)] + (["--go"] if a.go else [])
            r = subprocess.run(cmd)
            if a.go and r.returncode == 0:
                (Q / "done").mkdir(exist_ok=True)
                shutil.move(str(p), Q / "done" / p.name)
            elif a.go:
                # 途中まで出ている可能性があるので、次の回で同じものを出し直さないよう外す
                (Q / "failed").mkdir(exist_ok=True)
                shutil.move(str(p), Q / "failed" / p.name)
                print(f"  🔴 {p.name} は投稿できませんでした → queue/failed/（data/posted.jsonl で出た所まで確かめてから手で直す）")


if __name__ == "__main__":
    main()
