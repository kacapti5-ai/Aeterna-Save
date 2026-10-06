# 永恒守护 · 管理后台 + 卖家注册上架
# 用法：python3 admin/server.py
# 管理：http://127.0.0.1:8787/admin/
# 卖家接口：http://0.0.0.0:8788/api/seller/...

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import subprocess
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from seller import (
    MAX_LISTINGS,
    drop_token,
    new_token,
    public_user,
    register,
    session_user_id,
    too_many_registers,
    user_by_id,
    verify_login,
)

ROOT = Path(__file__).resolve().parent.parent
ADMIN_DIR = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "market.json"
SITE_PATH = ROOT / "data" / "site.json"
PASSWORD_FILE = ADMIN_DIR / "password.txt"

HOST = os.environ.get("ADMIN_HOST", "127.0.0.1")
PORT = int(os.environ.get("ADMIN_PORT", "8787"))
PUBLIC_HOST = os.environ.get("PUBLIC_HOST", "0.0.0.0")
PUBLIC_PORT = int(os.environ.get("PUBLIC_PORT", "8788"))
TOKEN_TTL = 12 * 3600

_sessions: dict[str, float] = {}
_write_lock = threading.Lock()

TYPE_LABEL = {
    "cards": "卡牌",
    "toys": "玩具",
    "account": "账号",
    "items": "道具/素材",
    "materials": "游戏素材 / MOD",
}

ALLOWED_ORIGINS = {
    "http://aeternasave.com",
    "http://www.aeternasave.com",
    "https://aeternasave.com",
    "https://www.aeternasave.com",
    "http://127.0.0.1:8787",
    "http://127.0.0.1:8788",
    "http://localhost:8787",
    "http://localhost:8788",
    "http://121.41.104.180:8788",
}


def _load_password() -> str:
    env = os.environ.get("ADMIN_PASSWORD", "").strip()
    if env:
        return env
    if PASSWORD_FILE.exists():
        return PASSWORD_FILE.read_text(encoding="utf-8").strip()
    pwd = "AeternaSave#admin"
    PASSWORD_FILE.write_text(pwd + "\n", encoding="utf-8")
    return pwd


def _secret() -> bytes:
    key = os.environ.get("ADMIN_SECRET", "").strip()
    if not key:
        key_file = ADMIN_DIR / ".signing_key"
        if key_file.exists():
            key = key_file.read_text(encoding="utf-8").strip()
        else:
            key = secrets.token_hex(32)
            key_file.write_text(key, encoding="utf-8")
    return key.encode("utf-8")


ADMIN_PASSWORD = _load_password()
SIGN_KEY = _secret()


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _publish_to_github() -> dict:
    script = ROOT / "scripts" / "publish-data.sh"
    if not script.is_file():
        return {"published": False, "error": "缺少 publish-data.sh"}
    try:
        proc = subprocess.run(
            ["bash", str(script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ},
        )
    except subprocess.TimeoutExpired:
        return {"published": False, "error": "同步官网超时"}
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        return {"published": False, "error": out[-400:] or "git push 失败"}
    return {"published": True, "detail": out[-200:]}


def _hash_pw(password: str) -> str:
    return hashlib.sha256((password + ":" + SIGN_KEY.decode()).encode("utf-8")).hexdigest()


def _new_token() -> str:
    raw = secrets.token_urlsafe(32)
    _sessions[raw] = time.time() + TOKEN_TTL
    return raw


def _valid_token(token: str | None) -> bool:
    if not token:
        return False
    exp = _sessions.get(token)
    if not exp or exp < time.time():
        _sessions.pop(token, None)
        return False
    return True


def _clip(value, n: int) -> str:
    return str(value or "").strip()[:n]


MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "AeternaAdmin/1.0"

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def _is_local(self) -> bool:
        return self.client_address[0] in ("127.0.0.1", "::1", "localhost")

    def _cors_origin(self) -> str:
        origin = (self.headers.get("Origin") or "").rstrip("/")
        if origin in ALLOWED_ORIGINS:
            return origin
        if origin.startswith("http://127.0.0.1:") or origin.startswith("http://localhost:"):
            return origin
        return ""

    def _cors_headers(self) -> list[tuple[str, str]]:
        origin = self._cors_origin()
        if not origin:
            return []
        return [
            ("Access-Control-Allow-Origin", origin),
            ("Access-Control-Allow-Credentials", "true"),
            ("Access-Control-Allow-Headers", "Content-Type, Authorization"),
            ("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS"),
            ("Vary", "Origin"),
        ]

    def _admin_token(self) -> str | None:
        auth = self.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth.split(" ", 1)[1].strip()
        raw = self.headers.get("Cookie", "")
        if raw:
            c = SimpleCookie()
            c.load(raw)
            if "admin_token" in c:
                return c["admin_token"].value
        return None

    def _seller_token(self) -> str | None:
        auth = self.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth.split(" ", 1)[1].strip()
        raw = self.headers.get("Cookie", "")
        if raw:
            c = SimpleCookie()
            c.load(raw)
            if "seller_token" in c:
                return c["seller_token"].value
        return None

    def _send(self, code: int, body: bytes, content_type: str, extra_headers: list[tuple[str, str]] | None = None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in self._cors_headers():
            self.send_header(k, v)
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj, extra=None):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", extra)

    def _read_body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n > 200_000:
            return b""
        return self.rfile.read(n) if n else b""

    def _payload(self):
        try:
            return json.loads(self._read_body() or b"{}")
        except json.JSONDecodeError:
            return None

    def _current_seller(self):
        uid = session_user_id(self._seller_token())
        if not uid:
            return None
        return user_by_id(ROOT, uid)

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in self._cors_headers():
            self.send_header(k, v)
        self.send_header("Access-Control-Allow-Origin", self._cors_origin() or "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path in ("/admin", "/admin/") or path.startswith("/admin/"):
            if not self._is_local():
                self._send(403, b"admin is local only", "text/plain")
                return
            if path in ("/admin", "/admin/"):
                html = (ADMIN_DIR / "index.html").read_bytes()
                self._send(200, html, "text/html; charset=utf-8")
                return
            rel = path[len("/admin/") :]
            if ".." in rel:
                self._send(403, b"forbidden", "text/plain")
                return
            fp = (ADMIN_DIR / rel).resolve()
            if not str(fp).startswith(str(ADMIN_DIR.resolve())) or not fp.is_file():
                self._send(404, b"not found", "text/plain")
                return
            self._send(200, fp.read_bytes(), MIME.get(fp.suffix.lower(), "application/octet-stream"))
            return

        if path == "/api/me":
            if not self._is_local():
                self._json(403, {"error": "管理接口仅本机可用"})
                return
            ok = _valid_token(self._admin_token())
            self._json(200, {"ok": ok})
            return

        if path in ("/api/market", "/api/site"):
            if not self._is_local() or not _valid_token(self._admin_token()):
                self._json(401, {"error": "未登录"})
                return
            if path == "/api/market":
                self._json(200, _read_json(DATA_PATH, {"games": [], "products": []}))
            else:
                self._json(200, _read_json(SITE_PATH, {}))
            return

        if path == "/api/seller/me":
            user = self._current_seller()
            if not user:
                self._json(200, {"ok": False})
                return
            self._json(200, {"ok": True, "user": public_user(user)})
            return

        if path == "/api/seller/catalog":
            market = _read_json(DATA_PATH, {"games": [], "products": []})
            self._json(200, {"games": market.get("games") or []})
            return

        if path == "/api/seller/products":
            user = self._current_seller()
            if not user:
                self._json(401, {"error": "请先登录"})
                return
            market = _read_json(DATA_PATH, {"games": [], "products": []})
            mine = [p for p in (market.get("products") or []) if p.get("sellerId") == user["id"]]
            self._json(200, {"products": mine})
            return

        rel = path.lstrip("/")
        if rel == "":
            rel = "index.html"
        fp = (ROOT / rel).resolve()
        if not str(fp).startswith(str(ROOT.resolve())) or not fp.is_file():
            self._send(404, b"not found", "text/plain")
            return
        self._send(200, fp.read_bytes(), MIME.get(fp.suffix.lower(), "application/octet-stream"))

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/login":
            if not self._is_local():
                self._json(403, {"error": "管理登录仅本机可用"})
                return
            payload = self._payload()
            if payload is None:
                self._json(400, {"error": "无效请求"})
                return
            pwd = str(payload.get("password") or "")
            if hmac.compare_digest(_hash_pw(pwd), _hash_pw(ADMIN_PASSWORD)):
                token = _new_token()
                cookie = f"admin_token={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={TOKEN_TTL}"
                self._json(200, {"ok": True, "token": token}, [("Set-Cookie", cookie)])
            else:
                self._json(401, {"error": "密码错误"})
            return

        if path == "/api/logout":
            tok = self._admin_token()
            if tok:
                _sessions.pop(tok, None)
            self._json(200, {"ok": True}, [("Set-Cookie", "admin_token=; Path=/; Max-Age=0")])
            return

        if path == "/api/seller/register":
            if too_many_registers(self.client_address[0]):
                self._json(429, {"error": "注册太频繁，请稍后再试"})
                return
            payload = self._payload()
            if payload is None:
                self._json(400, {"error": "无效请求"})
                return
            user, err = register(
                ROOT,
                str(payload.get("login") or ""),
                str(payload.get("password") or ""),
                str(payload.get("name") or ""),
            )
            if err:
                self._json(400, {"error": err})
                return
            token = new_token(user["id"])
            self._json(200, {"ok": True, "token": token, "user": public_user(user)})
            return

        if path == "/api/seller/login":
            payload = self._payload()
            if payload is None:
                self._json(400, {"error": "无效请求"})
                return
            user = verify_login(ROOT, str(payload.get("login") or ""), str(payload.get("password") or ""))
            if not user:
                self._json(401, {"error": "账号或密码不对"})
                return
            token = new_token(user["id"])
            self._json(200, {"ok": True, "token": token, "user": public_user(user)})
            return

        if path == "/api/seller/logout":
            drop_token(self._seller_token())
            self._json(200, {"ok": True})
            return

        if path == "/api/seller/products":
            user = self._current_seller()
            if not user:
                self._json(401, {"error": "请先登录"})
                return
            payload = self._payload()
            if payload is None:
                self._json(400, {"error": "无效 JSON"})
                return
            product, err = _seller_product(user, payload, None)
            if err:
                self._json(400, {"error": err})
                return
            with _write_lock:
                market = _read_json(DATA_PATH, {"games": [], "products": []})
                products = market.get("products") or []
                mine = [p for p in products if p.get("sellerId") == user["id"]]
                if len(mine) >= MAX_LISTINGS:
                    self._json(400, {"error": "每个账号最多 %d 件商品" % MAX_LISTINGS})
                    return
                products.insert(0, product)
                market["products"] = products
                _write_json(DATA_PATH, market)
            pub = _publish_to_github()
            self._json(200, {"ok": True, "product": product, **pub})
            return

        self._json(404, {"error": "not found"})

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/seller/products/"):
            user = self._current_seller()
            if not user:
                self._json(401, {"error": "请先登录"})
                return
            pid = unquote(path[len("/api/seller/products/") :])
            payload = self._payload()
            if payload is None:
                self._json(400, {"error": "无效 JSON"})
                return
            with _write_lock:
                market = _read_json(DATA_PATH, {"games": [], "products": []})
                products = market.get("products") or []
                idx = next((i for i, p in enumerate(products) if p.get("id") == pid and p.get("sellerId") == user["id"]), -1)
                if idx < 0:
                    self._json(404, {"error": "找不到这件商品"})
                    return
                product, err = _seller_product(user, payload, products[idx])
                if err:
                    self._json(400, {"error": err})
                    return
                products[idx] = product
                market["products"] = products
                _write_json(DATA_PATH, market)
            pub = _publish_to_github()
            self._json(200, {"ok": True, "product": product, **pub})
            return

        if not self._is_local() or not _valid_token(self._admin_token()):
            self._json(401, {"error": "未登录"})
            return
        payload = self._payload()
        if payload is None:
            self._json(400, {"error": "无效 JSON"})
            return
        if path == "/api/market":
            games = payload.get("games")
            products = payload.get("products")
            if not isinstance(games, list) or not isinstance(products, list):
                self._json(400, {"error": "games / products 必须是数组"})
                return
            with _write_lock:
                _write_json(DATA_PATH, {"games": games, "products": products})
            pub = _publish_to_github()
            self._json(200, {"ok": True, **pub})
            return
        if path == "/api/site":
            if not isinstance(payload, dict):
                self._json(400, {"error": "无效数据"})
                return
            with _write_lock:
                _write_json(SITE_PATH, payload)
            pub = _publish_to_github()
            self._json(200, {"ok": True, **pub})
            return
        self._json(404, {"error": "not found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if not path.startswith("/api/seller/products/"):
            self._json(404, {"error": "not found"})
            return
        user = self._current_seller()
        if not user:
            self._json(401, {"error": "请先登录"})
            return
        pid = unquote(path[len("/api/seller/products/") :])
        with _write_lock:
            market = _read_json(DATA_PATH, {"games": [], "products": []})
            products = market.get("products") or []
            kept = [p for p in products if not (p.get("id") == pid and p.get("sellerId") == user["id"])]
            if len(kept) == len(products):
                self._json(404, {"error": "找不到这件商品"})
                return
            market["products"] = kept
            _write_json(DATA_PATH, market)
        pub = _publish_to_github()
        self._json(200, {"ok": True, **pub})


def _seller_product(user: dict, payload: dict, existing: dict | None) -> tuple[dict | None, str | None]:
    market = _read_json(DATA_PATH, {"games": [], "products": []})
    games = market.get("games") or []
    game_id = _clip(payload.get("game"), 40)
    game = next((g for g in games if g.get("id") == game_id), None)
    if not game:
        return None, "请选择游戏"
    title = _clip(payload.get("title"), 80)
    if len(title) < 2:
        return None, "请填写标题"
    try:
        price = int(payload.get("price") or 0)
    except (TypeError, ValueError):
        return None, "价格无效"
    if price < 1 or price > 10_000_000:
        return None, "价格需在 1–10000000 元"
    ptype = _clip(payload.get("type"), 20) or "account"
    if ptype not in TYPE_LABEL:
        ptype = "account"
    items_raw = payload.get("items")
    if isinstance(items_raw, list):
        items = [_clip(x, 80) for x in items_raw if str(x).strip()][:20]
    else:
        items = [ln.strip()[:80] for ln in str(payload.get("desc") or "").splitlines() if ln.strip()][:20]
    row = dict(existing or {})
    row.update(
        {
            "id": (existing or {}).get("id") or ("p" + secrets.token_hex(6)),
            "game": game_id,
            "gameName": game.get("name") or game_id,
            "type": ptype,
            "typeLabel": TYPE_LABEL.get(ptype, ptype),
            "title": title,
            "price": price,
            "server": _clip(payload.get("server"), 40),
            "level": _clip(payload.get("level"), 40),
            "seller": user["name"],
            "sellerId": user["id"],
            "sellerRating": float((existing or {}).get("sellerRating") or 5),
            "sellerOrders": int((existing or {}).get("sellerOrders") or 0),
            "delivery": _clip(payload.get("delivery"), 20) or "48小时内",
            "verified": False,
            "escrow": True,
            "compensation": bool(payload.get("compensation")),
            "legacy": bool(payload.get("legacy")),
            "legacyPlan": _clip(payload.get("legacyPlan"), 40),
            "tags": [_clip(t, 20) for t in (payload.get("tags") or []) if str(t).strip()][:8],
            "image": _clip(payload.get("image"), 8) or "🎴",
            "items": items,
            "linkedAssets": (existing or {}).get("linkedAssets") or [],
            "verifyNote": _clip(payload.get("verifyNote"), 200),
            "published": True,
            "source": "seller",
        }
    )
    return row, None


def _serve(host: str, port: int) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    print("listening %s:%s" % (host, port), flush=True)
    httpd.serve_forever()


def main():
    print("管理后台：http://127.0.0.1:%s/admin/" % PORT, flush=True)
    print("卖家接口：http://%s:%s/api/seller/" % (PUBLIC_HOST, PUBLIC_PORT), flush=True)
    threading.Thread(target=_serve, args=(HOST, PORT), daemon=True).start()
    _serve(PUBLIC_HOST, PUBLIC_PORT)


if __name__ == "__main__":
    main()
