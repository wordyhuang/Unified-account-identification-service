"""邀请注册页接入服务：跳转签名、URL 校验、Webhook 投递。"""

import hashlib
import hmac
import ipaddress
import json
import socket
import threading
import time
import uuid
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from django.conf import settings
from django.utils import timezone

from apps.applications.models import WebhookDelivery

# 跳转签名有效期（秒），供接入方校验
JUMP_SIGN_TTL = 300
# Webhook 超时与重试间隔（首次 + 3 次重试）
WEBHOOK_TIMEOUT = 5
WEBHOOK_RETRY_DELAYS = (0, 1, 5, 30)


def sign_invite_jump(app_secret, payload, ts):
    """跳转签名：HMAC_SHA256(app_secret, "{payload}.{ts}") 取前 32 位。"""
    message = f"{payload}.{ts}".encode("utf-8")
    return hmac.new(app_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()[:32]


def _origin(url):
    parsed = urlparse(str(url or ""))
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def _is_blocked_host(hostname):
    """拒绝内网/回环/链路本地地址（SSRF 防护）；DEBUG 下放行便于本地联调。"""
    if settings.DEBUG:
        return False
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return True
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return True
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


def url_allowed_for_origins(allowed_origins, url):
    """校验目标地址：协议、同源白名单、SSRF（不依赖 Application 实例）。"""
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    allowed = {_origin(u) for u in (allowed_origins or [])}
    allowed.discard("")
    if _origin(url) not in allowed:
        return False
    return not _is_blocked_host(parsed.hostname)


def url_allowed_for_app(app, url):
    """校验目标地址：协议、同源白名单（cors_origins）、SSRF。"""
    return url_allowed_for_origins(app.cors_origins, url)


def _append_params(url, params):
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query))
    query.update({k: str(v) for k, v in params.items() if v is not None})
    return urlunparse(parsed._replace(query=urlencode(query)))


def build_registration_url(app, code):
    """构建接入方注册页跳转地址；未配置或校验不通过返回 None（回退内置页）。"""
    if not app or not app.registration_page_url:
        return None
    if not url_allowed_for_app(app, app.registration_page_url):
        return None
    ts = int(time.time())
    return _append_params(app.registration_page_url, {
        "code": code,
        "ts": ts,
        "sign": sign_invite_jump(app.app_secret, code, ts),
    })


def build_success_url(app, user):
    """构建注册成功后的浏览器跳转地址；未配置或校验不通过返回 None。"""
    if not app or not app.registration_success_url:
        return None
    if not url_allowed_for_app(app, app.registration_success_url):
        return None
    ts = int(time.time())
    payload = f"{user.id}.{user.username}"
    return _append_params(app.registration_success_url, {
        "user_id": user.id,
        "username": user.username,
        "ts": ts,
        "sign": sign_invite_jump(app.app_secret, payload, ts),
    })


def _json_safe(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def dispatch_register_webhook(app, tenant, user, invite_code, extra_fields):
    """注册成功后异步投递 Webhook；返回 event_id 或 None（未配置/校验不通过）。"""
    if not app or not app.webhook_url:
        return None
    if not url_allowed_for_app(app, app.webhook_url):
        return None

    event_id = uuid.uuid4()
    payload = {
        "event": "invite.registered",
        "event_id": str(event_id),
        "timestamp": int(time.time()),
        "app_key": app.app_key,
        "tenant_id": tenant.id,
        "data": {
            "user_id": user.id,
            "username": user.username,
            "user_type": user.user_type,
            "invite_code_id": invite_code.id,
            "invite_short_code": invite_code.short_code,
            "fields": {k: _json_safe(v) for k, v in (extra_fields or {}).items()},
        },
    }
    WebhookDelivery.objects.create(
        app=app, tenant=tenant, event="invite.registered",
        event_id=event_id, url=app.webhook_url, payload=payload, status="pending",
    )
    threading.Thread(target=_deliver_webhook, args=(str(event_id),), daemon=True).start()
    return str(event_id)


def _deliver_webhook(event_id):
    """线程内投递：签名 + 指数退避重试 + 每次尝试落库。"""
    delivery = WebhookDelivery.objects.filter(event_id=event_id).select_related("app").first()
    if delivery is None:
        return

    body = json.dumps(delivery.payload, ensure_ascii=False, separators=(",", ":"))
    raw = body.encode("utf-8")
    secret = delivery.app.app_secret

    for attempt, delay in enumerate(WEBHOOK_RETRY_DELAYS, start=1):
        if delay:
            time.sleep(delay)
        ts = str(int(time.time()))
        signature = "sha256=" + hmac.new(
            secret.encode("utf-8"), f"{ts}.".encode("utf-8") + raw, hashlib.sha256
        ).hexdigest()
        delivery.attempts = attempt
        try:
            resp = requests.post(
                delivery.url, data=raw, timeout=WEBHOOK_TIMEOUT, allow_redirects=False,
                headers={
                    "Content-Type": "application/json",
                    "X-UAIS-Signature": signature,
                    "X-UAIS-Event": delivery.event,
                    "X-UAIS-Event-Id": str(delivery.event_id),
                },
            )
            delivery.last_status_code = resp.status_code
            if 200 <= resp.status_code < 300:
                delivery.status = "success"
                delivery.last_error = None
                delivery.finished_at = timezone.now()
                delivery.save(update_fields=[
                    "attempts", "last_status_code", "status", "last_error", "finished_at",
                ])
                return
            delivery.last_error = f"HTTP {resp.status_code}"
        except Exception as exc:  # 网络异常等，记录后重试
            delivery.last_error = str(exc)[:500]
        delivery.save(update_fields=["attempts", "last_status_code", "last_error"])

    delivery.status = "failed"
    delivery.finished_at = timezone.now()
    delivery.save(update_fields=["status", "finished_at"])
