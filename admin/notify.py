# Email / SMS notifications (verification + later order alerts)
from __future__ import annotations

import hashlib
import hmac
import json
import os
import smtplib
import time
import urllib.error
import urllib.parse
import urllib.request
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

OTP_TTL = 10 * 60
OTP_COOLDOWN = 55
_otp: dict[str, dict] = {}
_otp_log: list[dict] = []


def login_kind(login: str) -> str | None:
    s = (login or "").strip().lower()
    if len(s) == 11 and s.isdigit() and s.startswith("1"):
        return "sms"
    if "@" in s and "." in s.split("@")[-1] and 6 <= len(s) <= 80:
        return "email"
    return None


def _hash_code(login: str, code: str) -> str:
    return hashlib.sha256((login + ":" + code).encode("utf-8")).hexdigest()


def issue_otp(login: str) -> tuple[str | None, str | None]:
    login = (login or "").strip().lower()
    kind = login_kind(login)
    if not kind:
        return None, "请填写中国大陆手机号或邮箱"
    now = time.time()
    prev = _otp.get(login)
    if prev and now - prev.get("sent", 0) < OTP_COOLDOWN:
        return None, "验证码刚发过，请稍等一分钟"
    code = f"{int.from_bytes(os.urandom(3), 'big') % 1000000:06d}"
    _otp[login] = {
        "hash": _hash_code(login, code),
        "exp": now + OTP_TTL,
        "sent": now,
        "tries": 0,
        "kind": kind,
    }
    _otp_log.insert(0, {"login": login, "kind": kind, "code": code, "at": int(now)})
    del _otp_log[30:]
    return code, None


def consume_otp(login: str, code: str) -> str | None:
    login = (login or "").strip().lower()
    rec = _otp.get(login)
    if not rec or rec["exp"] < time.time():
        _otp.pop(login, None)
        return "验证码无效或已过期"
    rec["tries"] = rec.get("tries", 0) + 1
    if rec["tries"] > 8:
        _otp.pop(login, None)
        return "验证码错误次数过多，请重新获取"
    if not hmac.compare_digest(rec["hash"], _hash_code(login, (code or "").strip())):
        return "验证码不对"
    _otp.pop(login, None)
    return None


def recent_otp_log() -> list[dict]:
    now = time.time()
    return [x for x in _otp_log if now - x["at"] < OTP_TTL]


def channel_status() -> dict:
    return {
        "email": bool(os.environ.get("NOTIFY_SMTP_HOST") and os.environ.get("NOTIFY_SMTP_USER")),
        "sms": bool(os.environ.get("ALIYUN_SMS_ACCESS_KEY_ID") and os.environ.get("ALIYUN_SMS_SIGN_NAME")),
    }


def send_verification(login: str, code: str) -> tuple[bool, str]:
    kind = login_kind(login)
    text = f"【永恒守护 Aeterna Save】验证码 {code}，10 分钟内有效。如非本人操作请忽略。"
    if kind == "email":
        ok, err = send_email(login, "Aeterna Save 验证码", text)
        return ok, err
    if kind == "sms":
        ok, err = send_sms(login, code)
        return ok, err
    return False, "账号格式不对"


def notify_user(login: str, title: str, text: str) -> tuple[bool, str]:
    """Later: buyer interest / order updates."""
    kind = login_kind(login)
    if kind == "email":
        return send_email(login, title, text)
    if kind == "sms":
        return send_sms_text(login, text[:60])
    return False, "无法投递"


def send_email(to: str, subject: str, text: str) -> tuple[bool, str]:
    host = os.environ.get("NOTIFY_SMTP_HOST", "").strip()
    port = int(os.environ.get("NOTIFY_SMTP_PORT", "465") or 465)
    user = os.environ.get("NOTIFY_SMTP_USER", "").strip()
    password = os.environ.get("NOTIFY_SMTP_PASS", "").strip()
    from_addr = os.environ.get("NOTIFY_SMTP_FROM", user).strip()
    if not host or not user or not password:
        return False, "邮件通道未开通（缺少 SMTP）"
    msg = MIMEText(text, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr(("Aeterna Save", from_addr))
    msg["To"] = to
    try:
        if port == 465:
            smtp = smtplib.SMTP_SSL(host, port, timeout=12)
        else:
            smtp = smtplib.SMTP(host, port, timeout=12)
            smtp.starttls()
        smtp.login(user, password)
        smtp.sendmail(from_addr, [to], msg.as_string())
        smtp.quit()
        return True, ""
    except Exception as e:
        return False, "邮件发送失败：" + str(e)[:120]


def send_sms(phone: str, code: str) -> tuple[bool, str]:
    template = os.environ.get("ALIYUN_SMS_TEMPLATE_CODE", "").strip()
    if not template:
        return send_sms_text(phone, f"验证码{code}，10分钟内有效")
    params = json.dumps({"code": code}, ensure_ascii=False)
    return _aliyun_sms(phone, template, params)


def send_sms_text(phone: str, text: str) -> tuple[bool, str]:
    template = os.environ.get("ALIYUN_SMS_NOTICE_TEMPLATE", "").strip()
    if not template:
        return False, "短信通道未开通（缺少阿里云短信签名/模板）"
    params = json.dumps({"txt": text[:20]}, ensure_ascii=False)
    return _aliyun_sms(phone, template, params)


def _aliyun_sms(phone: str, template_code: str, template_param: str) -> tuple[bool, str]:
    access = os.environ.get("ALIYUN_SMS_ACCESS_KEY_ID", "").strip()
    secret = os.environ.get("ALIYUN_SMS_ACCESS_KEY_SECRET", "").strip()
    sign = os.environ.get("ALIYUN_SMS_SIGN_NAME", "").strip()
    if not access or not secret or not sign:
        return False, "短信通道未开通（缺少阿里云 AccessKey）"
    from datetime import datetime, timezone

    params = {
        "AccessKeyId": access,
        "Action": "SendSms",
        "Format": "JSON",
        "PhoneNumbers": phone,
        "RegionId": "cn-hangzhou",
        "SignName": sign,
        "SignatureMethod": "HMAC-SHA1",
        "SignatureNonce": hashlib.sha1(os.urandom(16)).hexdigest(),
        "SignatureVersion": "1.0",
        "TemplateCode": template_code,
        "TemplateParam": template_param,
        "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "Version": "2017-05-25",
    }
    sorted_q = sorted(params.items())
    encoded = urllib.parse.urlencode(sorted_q, quote_via=urllib.parse.quote)
    string_to_sign = "GET&%2F&" + urllib.parse.quote(encoded, safe="")
    key = (secret + "&").encode("utf-8")
    sig = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha1).digest()
    import base64

    params["Signature"] = base64.b64encode(sig).decode("utf-8")
    url = "https://dysmsapi.aliyuncs.com/?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=12) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return False, "短信接口错误：" + e.read()[:120].decode("utf-8", "ignore")
    except Exception as e:
        return False, "短信发送失败：" + str(e)[:120]
    if body.get("Code") == "OK":
        return True, ""
    return False, "短信发送失败：" + str(body.get("Message") or body.get("Code") or body)
