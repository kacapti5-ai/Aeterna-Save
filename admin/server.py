# 永恒守护 · 管理后台（本机运行）
# 用法：python3 admin/server.py
# 打开：http://127.0.0.1:8787/admin/

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
ADMIN_DIR = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "market.json"
SITE_PATH = ROOT / "data" / "site.json"
PASSWORD_FILE = ADMIN_DIR / "password.txt"

HOST = os.environ.get("ADMIN_HOST", "127.0.0.1")
PORT = int(os.environ.get("ADMIN_PORT", "8787"))
TOKEN_TTL = 12 * 3600

_sessions: dict[str, float] = {}


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

    def _token_from_request(self) -> str | None:
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

    def _send(self, code: int, body: bytes, content_type: str, extra_headers: list[tuple[str, str]] | None = None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj, extra=None):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", extra)

    def _read_body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", "*"))
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path in ("/admin", "/admin/"):
            html = (ADMIN_DIR / "index.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")
            return
        if path.startswith("/admin/"):
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
            ok = _valid_token(self._token_from_request())
            self._json(200, {"ok": ok})
            return

        if path == "/api/market":
            if not _valid_token(self._token_from_request()):
                self._json(401, {"error": "未登录"})
                return
            self._json(200, _read_json(DATA_PATH, {"games": [], "products": []}))
            return

        if path == "/api/site":
            if not _valid_token(self._token_from_request()):
                self._json(401, {"error": "未登录"})
                return
            self._json(200, _read_json(SITE_PATH, {}))
            return

        # public static (optional: preview site while admin runs)
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
            try:
                payload = json.loads(self._read_body() or b"{}")
            except json.JSONDecodeError:
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
            tok = self._token_from_request()
            if tok:
                _sessions.pop(tok, None)
            self._json(200, {"ok": True}, [("Set-Cookie", "admin_token=; Path=/; Max-Age=0")])
            return

        self._json(404, {"error": "not found"})

    def do_PUT(self):
        if not _valid_token(self._token_from_request()):
            self._json(401, {"error": "未登录"})
            return
        parsed = urlparse(self.path)
        try:
            payload = json.loads(self._read_body() or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "无效 JSON"})
            return
        if parsed.path == "/api/market":
            games = payload.get("games")
            products = payload.get("products")
            if not isinstance(games, list) or not isinstance(products, list):
                self._json(400, {"error": "games / products 必须是数组"})
                return
            _write_json(DATA_PATH, {"games": games, "products": products})
            self._json(200, {"ok": True})
            return
        if parsed.path == "/api/site":
            if not isinstance(payload, dict):
                self._json(400, {"error": "无效数据"})
                return
            _write_json(SITE_PATH, payload)
            self._json(200, {"ok": True})
            return
        self._json(404, {"error": "not found"})


def main():
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"管理后台：http://{HOST}:{PORT}/admin/", flush=True)
    print("前台预览：http://%s:%s/" % (HOST, PORT), flush=True)
    if not os.environ.get("ADMIN_PASSWORD"):
        print("默认登录密码见 admin/password.txt （请尽快修改环境变量 ADMIN_PASSWORD）", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
