# Seller accounts (not published to GitHub)
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import threading
import time
from pathlib import Path

from notify import login_kind, normalize_login

LOCK = threading.Lock()
TOKEN_TTL = 12 * 3600
MAX_LISTINGS = 50
PBKDF2_ROUNDS = 120_000

_sessions: dict[str, dict] = {}
_register_hits: dict[str, list[float]] = {}

NAME_RE = re.compile(r"^[\w\u4e00-\u9fff ·\-_]{2,24}$")


def accounts_path(root: Path) -> Path:
    return root / "data" / "accounts.json"


def load_accounts(root: Path) -> dict:
    path = accounts_path(root)
    if not path.exists():
        return {"users": []}
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def save_accounts(root: Path, data: dict) -> None:
    import json

    path = accounts_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS
    ).hex()


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "login": user["login"],
        "name": user["name"],
    }


def mask_login(login: str) -> str:
    s = str(login or "").strip()
    if "@" in s:
        name, _, host = s.partition("@")
        shown = name[0] + "***" if name else "*"
        return shown + "@" + host
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) >= 7:
        prefix = "+" if s.startswith("+") else ""
        head = digits[:2] if prefix else digits[:3]
        return prefix + head + "****" + digits[-4:]
    return "***" if s else ""


def admin_users(root: Path) -> list:
    data = load_accounts(root)
    rows = []
    for u in data.get("users") or []:
        rows.append(
            {
                "id": u.get("id"),
                "name": u.get("name") or "",
                "login": mask_login(u.get("login") or ""),
                "channel": u.get("channel") or login_kind(u.get("login") or "") or "",
                "created": int(u.get("created") or 0),
            }
        )
    rows.sort(key=lambda x: x.get("created") or 0, reverse=True)
    return rows


def find_user(data: dict, login: str):
    key = normalize_login(login)
    for u in data.get("users") or []:
        if normalize_login(str(u.get("login") or "")) == key:
            return u
    return None


def too_many_registers(ip: str) -> bool:
    now = time.time()
    window = _register_hits.setdefault(ip, [])
    _register_hits[ip] = [t for t in window if now - t < 3600]
    if len(_register_hits[ip]) >= 8:
        return True
    _register_hits[ip].append(now)
    return False


def register(root: Path, login: str, password: str, name: str):
    login = normalize_login(login)
    name = (name or "").strip()
    password = password or ""
    kind = login_kind(login)
    if not kind:
        return None, "请填写邮箱，或选择区号后填写手机号"
    if not NAME_RE.match(name):
        return None, "店铺名 2–24 个字"
    if len(password) < 8:
        return None, "密码至少 8 位"
    with LOCK:
        data = load_accounts(root)
        if find_user(data, login):
            return None, "这个账号已注册，请直接登录"
        salt = secrets.token_hex(16)
        user = {
            "id": "u" + secrets.token_hex(8),
            "login": login,
            "name": name,
            "salt": salt,
            "password_hash": hash_password(password, salt),
            "created": int(time.time()),
            "channel": kind,
        }
        data.setdefault("users", []).append(user)
        save_accounts(root, data)
    return user, None


def verify_login(root: Path, login: str, password: str):
    with LOCK:
        data = load_accounts(root)
        user = find_user(data, login or "")
    if not user:
        return None
    expected = user.get("password_hash") or ""
    got = hash_password(password or "", user.get("salt") or "")
    if not hmac.compare_digest(expected, got):
        return None
    return user


def new_token(user_id: str) -> str:
    raw = secrets.token_urlsafe(32)
    _sessions[raw] = {"uid": user_id, "exp": time.time() + TOKEN_TTL}
    return raw


def session_user_id(token: str | None) -> str | None:
    if not token:
        return None
    rec = _sessions.get(token)
    if not rec or rec["exp"] < time.time():
        _sessions.pop(token, None)
        return None
    return rec["uid"]


def drop_token(token: str | None) -> None:
    if token:
        _sessions.pop(token, None)


def user_by_id(root: Path, uid: str):
    with LOCK:
        data = load_accounts(root)
        for u in data.get("users") or []:
            if u.get("id") == uid:
                return u
    return None
