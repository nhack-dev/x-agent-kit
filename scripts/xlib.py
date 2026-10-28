"""X API v2 を呼ぶ共通部品（標準ライブラリだけ）。

- .env を読む
- Bearer（読むだけ）と OAuth 1.0a（自分として読む・投稿する）で呼ぶ
- 料金の目安を持つ（X の料金は変わります。正しい額は開発者コンソールで）

ネットワークに出るのは request() だけです。どの道具も --go を付けないと request() を呼びません。
"""
from __future__ import annotations

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401


import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).absolute().parent.parent
DEFAULT_BASE = "https://api.x.com"   # 公式ドキュメント https://docs.x.com/x-api/introduction の接続先

# 料金の目安（USD）。2026-10-27 に https://docs.x.com/x-api/getting-started/pricing で確認。
PRICE = {
    "post": 0.015,         # 投稿1件
    "post_url": 0.200,     # URL を含む投稿1件
    "read": 0.005,         # 他の人の投稿を1件読む
    "own": 0.001,          # 自分の投稿・自分宛てを1件読む
}


def load_env(path: Path | None = None) -> None:
    """.env を読んで os.environ に足す（すでにある値は上書きしない）。"""
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def need(*names: str) -> dict:
    load_env()
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit(f"[止まりました] .env に {', '.join(missing)} がありません。README の「キーの取り方」を見てください。")
    return {n: os.environ[n] for n in names}


def base() -> str:
    load_env()
    return (os.environ.get("X_API_BASE") or DEFAULT_BASE).rstrip("/")


# ---------- OAuth 1.0a（HMAC-SHA1） ----------

def _pct(s) -> str:
    return urllib.parse.quote(str(s), safe="~-._")


def oauth1_header(method: str, url: str, params: dict | None, keys: dict,
                  nonce: str | None = None, timestamp: str | None = None) -> str:
    """署名つきの Authorization を作る。JSON の本文は署名に入れない（決まり）。クエリは入れる。"""
    oauth = {
        "oauth_consumer_key": keys["X_API_KEY"],
        "oauth_nonce": nonce or secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": timestamp or str(int(time.time())),
        "oauth_token": keys["X_ACCESS_TOKEN"],
        "oauth_version": "1.0",
    }
    allp = {**(params or {}), **oauth}
    pstr = "&".join(f"{_pct(a)}={_pct(b)}" for a, b in sorted((_pct(k), _pct(v)) for k, v in allp.items()))
    base_str = "&".join([method.upper(), _pct(url), _pct(pstr)])
    key = f"{_pct(keys['X_API_SECRET'])}&{_pct(keys['X_ACCESS_TOKEN_SECRET'])}"
    oauth["oauth_signature"] = base64.b64encode(
        hmac.new(key.encode(), base_str.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join(f'{_pct(a)}="{_pct(b)}"' for a, b in sorted(oauth.items()))


class XError(RuntimeError):
    def __init__(self, code: int, text: str):
        hint = {
            401: "鍵が違うか期限切れです。.env を見直してください（権限を変えたあとは Access Token を作り直す）。",
            402: "クレジットが足りません。開発者コンソールで残高を見てください。",
            403: "この操作は今の契約・決まりで許されていません（返信・引用の制限など）。docs/x-api-facts.md を見てください。",
            429: "回数の上限です。15分ほど待ってからやり直してください。",
        }.get(code, "")
        super().__init__(f"HTTP {code} {hint}\n{text[:800]}")
        self.code = code


def request(method: str, path: str, query: dict | None = None, body: dict | None = None,
            auth: str = "bearer", exit_on_error: bool = True) -> dict:
    """X API を1回呼ぶ。auth は 'bearer'（読むだけ）か 'user'（自分として）。"""
    url = base() + path
    query = {k: str(v) for k, v in (query or {}).items() if v not in (None, "")}
    full = url + ("?" + urllib.parse.urlencode(query) if query else "")
    headers = {"User-Agent": "x-agent-kit/1.0"}
    if auth == "bearer":
        headers["Authorization"] = "Bearer " + need("X_BEARER_TOKEN")["X_BEARER_TOKEN"]
    else:
        keys = need("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
        headers["Authorization"] = oauth1_header(method, url, query, keys)
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(full, data=data, method=method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        err = XError(e.code, e.read().decode(errors="replace"))
        if exit_on_error:
            sys.exit(f"[止まりました] {err}")
        raise err


def my_user_id(auth: str = "user") -> str:
    load_env()
    name = os.environ.get("X_USERNAME", "")
    if not name:
        sys.exit("[止まりました] .env に X_USERNAME（自分のユーザー名・@ なし）がありません。")
    res = request("GET", f"/2/users/by/username/{name}", auth=auth)
    uid = res.get("data", {}).get("id")
    if not uid:
        sys.exit(f"[止まりました] @{name} が見つかりません。")
    return uid
