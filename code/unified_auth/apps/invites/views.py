import secrets
import time
from datetime import datetime

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import render
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.accounts.models import User, UserProfile
from apps.audit.models import AuditLog
from apps.invites.appearance import resolve_appearance
from apps.invites.fields import FIELD_REGISTRY
from apps.invites.models import (
    InviteCode, ProfileCompletionCode, generate_code, generate_short_code,
)
from common.errors import ErrorCode
from common.response import success, error

# 补全会话凭证缓存前缀与有效期（秒）
COMPLETION_SESSION_PREFIX = "pc_session:"
COMPLETION_SESSION_TTL = 600


# ==================== 邀请注册字段解析 ====================

# 系统默认字段（租户与邀请码均未配置时使用，兼容升级前行为）
DEFAULT_INVITE_FIELDS = [
    {"key": "nickname", "required": False},
    {"key": "phone", "required": False},
]

# 不在 FIELD_REGISTRY 中但注册页可用的特殊字段
INVITE_EXTRA_FIELDS = {
    "phone": {"label": "手机号", "model": "user", "type": "text"},
}

# 固定字段：恒必填、不允许配置
INVITE_FIXED_FIELD_KEYS = ("username", "password")


def invite_field_meta(key):
    """字段元数据（label/type/options），支持 FIELD_REGISTRY 与特殊字段。"""
    info = FIELD_REGISTRY.get(key) or INVITE_EXTRA_FIELDS.get(key)
    if not info:
        return None
    meta = {"key": key, "label": info["label"], "type": info.get("type", "text")}
    if info.get("type") == "select":
        meta["options"] = info.get("options", [])
    return meta


def resolve_invite_fields(invite_code, tenant):
    """解析有效注册字段：邀请码覆盖 > 租户默认 > 系统默认。

    返回数组，前两项恒为 username / password（required=True, fixed=True）。
    """
    if invite_code.fields is not None:
        base = invite_code.fields
    elif tenant is not None and tenant.invite_fields is not None:
        base = tenant.invite_fields
    else:
        base = DEFAULT_INVITE_FIELDS

    items = []
    seen = set()
    for raw in base or []:
        if isinstance(raw, dict):
            key = raw.get("key")
            required = bool(raw.get("required"))
        else:
            key = raw
            required = False
        if not isinstance(key, str) or key in INVITE_FIXED_FIELD_KEYS or key in seen:
            continue
        meta = invite_field_meta(key)
        if meta is None:
            continue
        meta["required"] = required
        items.append(meta)
        seen.add(key)

    # 手机白名单联动：配置白名单后手机号必须采集且必填
    if invite_code.allowed_phones:
        phone_meta = next((i for i in items if i["key"] == "phone"), None)
        if phone_meta:
            phone_meta["required"] = True
        else:
            meta = invite_field_meta("phone")
            meta["required"] = True
            items.append(meta)

    fixed = [
        {"key": "username", "label": "用户名", "type": "text", "required": True, "fixed": True},
        {"key": "password", "label": "密码", "type": "password", "required": True, "fixed": True},
    ]
    return fixed + items


def invite_texts(tenant):
    """注册页文案：空值回退默认。"""
    if tenant is None:
        return {"submit": "注册账号", "success": "", "agreement": ""}
    return {
        "submit": tenant.invite_submit_text or "注册账号",
        "success": tenant.invite_success_text or "",
        "agreement": tenant.invite_agreement or "",
    }


# ==================== 防刷频控 ====================


def _throttle_count(key, ttl):
    """固定窗口计数器：首次写入返回 1，之后自增。"""
    if cache.add(key, 1, ttl):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        cache.add(key, 1, ttl)
        return 1


def _invite_ip_key(ip):
    """注册尝试计数（按分钟窗口）：超过上限后拒绝，防暴力探测有效码。"""
    minute = int(time.time() // 60)
    return f"invite_reg:ip:{ip}:{minute}"


def _invite_daily_key(code_id):
    """单码每日成功注册计数（按码隔离，跨天自然过期）。"""
    now = timezone.now()
    if timezone.is_aware(now):
        now = timezone.make_naive(now)
    return f"invite_reg:daily:{code_id}:{now.date().isoformat()}"


# ==================== 校验辅助 ====================


def _check_invite_valid(code_obj, extra_message_prefix="邀请码"):
    """校验邀请码可用性。返回 None 表示可用，否则返回 (ErrorCode, message)。"""
    if code_obj is None or code_obj.status != 1:
        return ErrorCode.INVITE_CODE_INVALID, None
    if code_obj.expires_at and timezone.now() > code_obj.expires_at:
        return ErrorCode.INVITE_CODE_EXPIRED, None
    if code_obj.max_uses is not None and code_obj.used_count >= code_obj.max_uses:
        return ErrorCode.INVITE_CODE_EXHAUSTED, None
    return None


def _check_completion_valid(code_obj):
    if code_obj is None or code_obj.status != 1:
        return ErrorCode.INVITE_CODE_INVALID, "补全码无效或已停用"
    if code_obj.expires_at and timezone.now() > code_obj.expires_at:
        return ErrorCode.INVITE_CODE_EXPIRED, "补全码已过期"
    if (
        code_obj.mode == "shared"
        and code_obj.max_uses is not None
        and code_obj.used_count >= code_obj.max_uses
    ):
        return ErrorCode.INVITE_CODE_EXHAUSTED, "补全码使用次数已达上限"
    if code_obj.mode == "single" and code_obj.user_id is None:
        return ErrorCode.INVITE_CODE_INVALID, "补全码配置错误：未绑定用户"
    return None


def _parse_expires_at(value):
    """解析前端传入的有效期（ISO datetime / date 字符串），返回 naive datetime 或 None。"""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return timezone.make_naive(dt) if timezone.is_aware(dt) else dt


# ==================== 邀请码：公开 API ====================


@api_view(["GET"])
def invite_info(request, code):
    code_obj = InviteCode.objects.filter(code=code).first()
    err = _check_invite_valid(code_obj)
    if err:
        return Response(error(err[0], message=err[1]), status=400)

    tenant = code_obj.tenant
    # 页面外观：码级 > 租户级 > 系统内置（字段级回退，公开接口/页面渲染/预览共用 resolve_appearance）
    appearance = resolve_appearance(code_obj, tenant, "invite")
    return Response(success({
        "require_phone": bool(code_obj.allowed_phones),
        "user_type": code_obj.user_type,
        "expires_at": code_obj.expires_at,
        "remaining_uses": (
            None if code_obj.max_uses is None
            else code_obj.max_uses - code_obj.used_count
        ),
        # 注册页品牌（兼容旧字段结构：name 取解析后的页面标题）
        "brand": {
            "name": appearance["title"],
            "welcome": appearance["welcome"],
            "theme_color": appearance["theme_color"],
            "logo": appearance["logo"],
        },
        # 完整外观（含背景/按钮文字/页脚，模式一前端使用）
        "appearance": appearance,
        # 有效注册字段与文案（模式一/模式二共用）
        "fields": resolve_invite_fields(code_obj, tenant),
        "texts": {
            **invite_texts(tenant),
            # 按钮文字：解析值优先，未配置回退原租户文案，再回退默认
            "submit": appearance["button_text"] or invite_texts(tenant)["submit"],
        },
    }))


@api_view(["POST"])
def invite_register(request, code):
    # 防刷频控①：单 IP 每分钟注册尝试上限（先于码校验，防暴力探测有效码）
    ip = request.META.get("REMOTE_ADDR", "unknown")
    if _throttle_count(_invite_ip_key(ip), ttl=120) > settings.INVITE_REGISTER_IP_LIMIT_PER_MINUTE:
        return Response(error(ErrorCode.RATE_LIMIT_EXCEEDED), status=429)

    code_obj = InviteCode.objects.filter(code=code).first()
    err = _check_invite_valid(code_obj)
    if err:
        return Response(error(err[0], message=err[1]), status=400)

    # 防刷频控②：单码每日成功注册上限（按码隔离）
    if cache.get(_invite_daily_key(code_obj.id), 0) >= settings.INVITE_REGISTER_CODE_DAILY_LIMIT:
        return Response(error(ErrorCode.RATE_LIMIT_EXCEEDED), status=429)

    body = request.data if isinstance(request.data, dict) else {}
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")

    if not username or not password:
        return Response(error(ErrorCode.PARAM_INVALID, message="用户名和密码不能为空"), status=400)
    if len(password) < 6:
        return Response(error(ErrorCode.PARAM_INVALID, message="密码长度不能少于6位"), status=400)

    # 字段白名单：只接受按配置解析出的字段（username/password 固定放行）
    field_meta = resolve_invite_fields(code_obj, code_obj.tenant)
    allowed_keys = {f["key"] for f in field_meta} - set(INVITE_FIXED_FIELD_KEYS)
    unknown = [k for k in body.keys() if k not in allowed_keys and k not in INVITE_FIXED_FIELD_KEYS]
    if unknown:
        return Response(
            error(ErrorCode.PARAM_INVALID, message=f"不允许提交的字段: {', '.join(unknown)}"),
            status=400,
        )

    # 必填与类型校验（select 校验选项，date 转日期对象）
    extra_values = {}
    for field in field_meta:
        key = field["key"]
        if key in INVITE_FIXED_FIELD_KEYS:
            continue
        value = body.get(key)
        if isinstance(value, str):
            value = value.strip()
        if value in (None, ""):
            if field["required"]:
                return Response(
                    error(ErrorCode.PARAM_INVALID, message=f"缺少必填项: {field['label']}"),
                    status=400,
                )
            continue
        info = FIELD_REGISTRY.get(key) or INVITE_EXTRA_FIELDS.get(key)
        if info.get("type") == "select":
            options = [o["value"] for o in info.get("options", [])]
            if value not in options:
                return Response(
                    error(ErrorCode.PARAM_INVALID, message=f"{info['label']} 取值不合法"),
                    status=400,
                )
        if info.get("type") == "date":
            try:
                value = datetime.strptime(str(value), "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    error(ErrorCode.PARAM_INVALID, message=f"{info['label']} 日期格式应为 YYYY-MM-DD"),
                    status=400,
                )
        extra_values[key] = value

    phone = str(extra_values.get("phone") or "").strip()

    # 手机白名单校验：配置了白名单则必须命中
    if code_obj.allowed_phones:
        if not phone or phone not in [str(p).strip() for p in code_obj.allowed_phones]:
            return Response(error(ErrorCode.INVITE_PHONE_NOT_ALLOWED), status=403)

    # 租户内唯一性校验（用户名/手机号/邮箱）
    if User.objects.filter(tenant=code_obj.tenant, username=username).exists():
        return Response(error(ErrorCode.PARAM_INVALID, message="用户名已被占用"), status=400)
    if phone and User.objects.filter(tenant=code_obj.tenant, phone=phone).exists():
        return Response(error(ErrorCode.PARAM_INVALID, message="手机号已被占用"), status=400)
    email_value = extra_values.get("email")
    if email_value and User.objects.filter(tenant=code_obj.tenant, email=email_value).exists():
        return Response(error(ErrorCode.PARAM_INVALID, message="邮箱已被占用"), status=400)

    # 按字段归属分流：User 字段直接落库，profile 字段写 UserProfile
    user_kwargs = {}
    profile_values = {}
    for key, value in extra_values.items():
        info = FIELD_REGISTRY.get(key) or INVITE_EXTRA_FIELDS.get(key)
        if info.get("model") == "user":
            user_kwargs[key] = value
        else:
            profile_values[key] = value

    if not user_kwargs.get("nickname"):
        user_kwargs["nickname"] = username
    if phone:
        user_kwargs["phone"] = phone

    user = User.objects.create(
        tenant=code_obj.tenant,
        username=username,
        user_type=code_obj.user_type,
        **user_kwargs,
    )
    user.set_password(password)
    user.save(update_fields=["password"])

    if profile_values:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        for key, value in profile_values.items():
            setattr(profile, key, value)
        profile.save(update_fields=list(profile_values.keys()))

    # 注册后自动入组：应用启用用户组准入时，邀请码上配置的组在此写入（幂等）
    auto_group_ids = code_obj.auto_group_ids or []
    if auto_group_ids:
        from apps.users.models import UserGroup, UserGroupMember
        valid_group_ids = list(
            UserGroup.objects.filter(
                id__in=auto_group_ids, tenant_id=code_obj.tenant_id
            ).values_list("id", flat=True)
        )
        for gid in valid_group_ids:
            UserGroupMember.objects.get_or_create(group_id=gid, user=user)
        if valid_group_ids:
            AuditLog.objects.create(
                tenant_id=code_obj.tenant_id,
                actor_id=user.id,
                actor_name=user.username,
                action="invite.register.auto_group",
                resource_type="user",
                resource_id=user.id,
                detail={"group_ids": valid_group_ids, "invite_code_id": code_obj.id},
                ip_address=request.META.get("REMOTE_ADDR", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
            )

    code_obj.used_count += 1
    if code_obj.max_uses is not None and code_obj.used_count >= code_obj.max_uses:
        code_obj.status = 0
    code_obj.save(update_fields=["used_count", "status", "updated_at"])

    # 防刷频控②：仅成功注册计数（TTL 覆盖至跨天后自然过期）
    _throttle_count(_invite_daily_key(code_obj.id), ttl=90000)

    AuditLog.objects.create(
        tenant=code_obj.tenant,
        actor_id=user.id,
        actor_name=user.username,
        action="invite.register",
        resource_type="user",
        resource_id=user.id,
        detail={"invite_code_id": code_obj.id, "user_type": user.user_type},
        ip_address=request.META.get("REMOTE_ADDR", ""),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
    )

    # 模式二：绑定接入应用时，返回成功页跳转地址并异步投递 Webhook
    redirect_url = None
    if code_obj.app_id:
        from .services import build_success_url, dispatch_register_webhook
        redirect_url = build_success_url(code_obj.app, user)
        dispatch_register_webhook(code_obj.app, code_obj.tenant, user, code_obj, extra_values)

    return Response(success({
        "user_id": user.id,
        "username": user.username,
        "redirect_url": redirect_url,
    }))


# ==================== 补全码：公开 API ====================


def _completion_fields_meta(code_obj):
    """返回码允许字段的白名单元信息（label/type/options）。"""
    meta = []
    for name in (code_obj.fields or []):
        info = FIELD_REGISTRY.get(name)
        if not info:
            continue
        item = {"name": name, "label": info["label"], "type": info.get("type", "text")}
        if info.get("type") == "select":
            item["options"] = info.get("options", [])
        meta.append(item)
    return meta


def _completion_prefill(code_obj, user):
    """返回字段当前值（user 字段 + profile 字段）。"""
    profile = UserProfile.objects.filter(user=user).first()
    values = {}
    for name in (code_obj.fields or []):
        info = FIELD_REGISTRY.get(name)
        if not info:
            continue
        if info["model"] == "user":
            values[name] = getattr(user, name, None)
        elif profile is not None:
            values[name] = getattr(profile, name, None)
    return values


@api_view(["GET"])
def completion_info(request, code):
    code_obj = ProfileCompletionCode.objects.filter(code=code).first()
    err = _check_completion_valid(code_obj)
    if err:
        return Response(error(err[0], message=err[1]), status=400)

    data = {
        "mode": code_obj.mode,
        "fields": _completion_fields_meta(code_obj),
        "expires_at": code_obj.expires_at,
        # 页面外观（码级 > 租户级 > 系统内置）
        "appearance": resolve_appearance(code_obj, code_obj.tenant, "completion"),
    }
    if code_obj.mode == "single":
        data["prefill"] = _completion_prefill(code_obj, code_obj.user)
        data["allow_repeated"] = code_obj.allow_repeated
        data["username"] = code_obj.user.username
    return Response(success(data))


@api_view(["POST"])
def completion_send_sms(request, code):
    """多人通用模式：向用户手机号发送补全身份验证码。"""
    code_obj = ProfileCompletionCode.objects.filter(code=code).first()
    err = _check_completion_valid(code_obj)
    if err:
        return Response(error(err[0], message=err[1]), status=400)
    if code_obj.mode != "shared":
        return Response(error(ErrorCode.PARAM_INVALID, message="单人补全码无需身份验证"), status=400)

    body = request.data if isinstance(request.data, dict) else {}
    phone = str(body.get("phone") or "").strip()
    if not phone:
        return Response(error(ErrorCode.PARAM_MISSING, message="缺少手机号"), status=400)

    # 身份校验：必须是本租户下绑定该手机号的用户
    user = User.objects.filter(tenant=code_obj.tenant, phone=phone, status=1).first()
    if user is None:
        return Response(error(ErrorCode.USER_NOT_FOUND, message="该手机号未匹配到本企业用户"), status=404)

    from apps.accounts.views import _dispatch_sms_code
    ip = request.META.get("REMOTE_ADDR", "")
    ok, err_response = _dispatch_sms_code(
        phone, ip, f"sms:pc:{code}:{phone}", tenant=code_obj.tenant
    )
    if not ok:
        return err_response

    return Response(success({"phone": phone}))


@api_view(["POST"])
def completion_login(request, code):
    """多人通用模式：校验短信验证码，签发受限补全会话凭证。"""
    code_obj = ProfileCompletionCode.objects.filter(code=code).first()
    err = _check_completion_valid(code_obj)
    if err:
        return Response(error(err[0], message=err[1]), status=400)
    if code_obj.mode != "shared":
        return Response(error(ErrorCode.PARAM_INVALID, message="单人补全码无需身份验证"), status=400)

    from django.core.cache import cache
    body = request.data if isinstance(request.data, dict) else {}
    phone = str(body.get("phone") or "").strip()
    sms_code = str(body.get("sms_code") or "").strip()
    if not phone or not sms_code:
        return Response(error(ErrorCode.PARAM_MISSING, message="缺少手机号或验证码"), status=400)

    cache_key = f"sms:pc:{code}:{phone}"
    cached = cache.get(cache_key)
    if cached is None:
        return Response(error(ErrorCode.SMS_CODE_EXPIRED), status=400)
    if cached != sms_code:
        return Response(error(ErrorCode.SMS_CODE_INVALID), status=400)
    cache.delete(cache_key)

    user = User.objects.filter(tenant=code_obj.tenant, phone=phone, status=1).first()
    if user is None:
        return Response(error(ErrorCode.USER_NOT_FOUND, message="该手机号未匹配到本企业用户"), status=404)

    session_token = secrets.token_urlsafe(32)
    cache.set(
        f"{COMPLETION_SESSION_PREFIX}{session_token}",
        {"code_id": code_obj.id, "user_id": user.id},
        timeout=COMPLETION_SESSION_TTL,
    )
    return Response(success({
        "session_token": session_token,
        "expires_in": COMPLETION_SESSION_TTL,
        "fields": _completion_fields_meta(code_obj),
        "prefill": _completion_prefill(code_obj, user),
    }))


@api_view(["PUT"])
def completion_submit(request, code):
    """提交资料补全。

    single 模式：码本身即凭证；allow_repeated=False 时提交后码作废。
    shared 模式：需携带 completion_login 签发的会话凭证（请求头 X-Completion-Token）。
    """
    from django.core.cache import cache

    code_obj = ProfileCompletionCode.objects.filter(code=code).first()
    err = _check_completion_valid(code_obj)
    if err:
        return Response(error(err[0], message=err[1]), status=400)

    if code_obj.mode == "shared":
        session_token = request.headers.get("X-Completion-Token", "")
        session_data = cache.get(f"{COMPLETION_SESSION_PREFIX}{session_token}") if session_token else None
        if not session_data or session_data.get("code_id") != code_obj.id:
            return Response(error(ErrorCode.COMPLETION_SESSION_INVALID), status=401)
        user = User.objects.filter(id=session_data.get("user_id"), tenant=code_obj.tenant).first()
        if user is None:
            return Response(error(ErrorCode.USER_NOT_FOUND), status=404)
    else:
        user = code_obj.user

    body = request.data if isinstance(request.data, dict) else {}
    if not body:
        return Response(error(ErrorCode.PARAM_MISSING, message="缺少提交内容"), status=400)

    allowed = set(code_obj.fields or [])
    unknown = [k for k in body.keys() if k not in allowed]
    if unknown:
        return Response(
            error(ErrorCode.PARAM_INVALID, message=f"不允许修改的字段: {', '.join(unknown)}"),
            status=400,
        )

    user_fields = {}
    profile_fields = {}
    for name, value in body.items():
        info = FIELD_REGISTRY[name]
        if info["model"] == "user":
            user_fields[name] = value
        else:
            profile_fields[name] = value

    if user_fields:
        for name, value in user_fields.items():
            setattr(user, name, value)
        user.save(update_fields=user_fields.keys())
    if profile_fields:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        for name, value in profile_fields.items():
            setattr(profile, name, value)
        profile.save(update_fields=profile_fields.keys())

    # 记使用并按策略作废
    code_obj.used_count += 1
    if code_obj.mode == "single" and not code_obj.allow_repeated:
        code_obj.status = 0
    if (
        code_obj.mode == "shared"
        and code_obj.max_uses is not None
        and code_obj.used_count >= code_obj.max_uses
    ):
        code_obj.status = 0
    code_obj.save(update_fields=["used_count", "status", "updated_at"])

    if code_obj.mode == "shared":
        cache.delete(f"{COMPLETION_SESSION_PREFIX}{session_token}")

    AuditLog.objects.create(
        tenant=code_obj.tenant,
        actor_id=user.id,
        actor_name=user.username,
        action="profile_completion.submit",
        resource_type="user",
        resource_id=user.id,
        detail={"completion_code_id": code_obj.id, "fields": list(body.keys())},
        ip_address=request.META.get("REMOTE_ADDR", ""),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
    )

    return Response(success({"user_id": user.id}))


# ==================== 公开页面 ====================


def invite_page(request, code):
    """邀请注册页：邀请码绑定了接入应用则 302 到其自建注册页，否则渲染内置页。"""
    from .services import build_registration_url

    invite = InviteCode.objects.select_related("app").filter(code=code).first()
    if invite and invite.app_id:
        target = build_registration_url(invite.app, invite.code)
        if target:
            return HttpResponseRedirect(target)
    return render(request, "invites/invite_page.html", {"code": code})


def completion_page(request, code):
    return render(request, "invites/completion_page.html", {"code": code})


def appearance_preview_page(request, token):
    """外观预览页：按 token 渲染，按钮禁用、不落地任何数据。

    token 在 TTL 内可重复访问：管理端抽屉 iframe 与「新窗口完整预览」共享同一
    预览地址，一次性消费会导致完整预览失效，故改为 10 分钟内可复用。
    """
    cache_key = f"appearance_preview:{token}"
    data = cache.get(cache_key)
    if not data:
        return HttpResponseNotFound("预览链接无效或已过期")
    return render(request, "invites/appearance_preview.html", {
        "page_type": data.get("page_type", "invite"),
        "appearance": data.get("effective", {}),
    })


def short_link(request, short_code):
    """短链跳转：/s/{short_code} → 接入方注册页（已绑定应用）或内置扫码页面。"""
    from .services import build_registration_url

    invite = InviteCode.objects.select_related("app").filter(short_code=short_code).first()
    if invite:
        if invite.app_id:
            target = build_registration_url(invite.app, invite.code)
            if target:
                return HttpResponseRedirect(target)
        return HttpResponseRedirect(f"/invite/{invite.code}")
    completion = ProfileCompletionCode.objects.filter(short_code=short_code).only("code").first()
    if completion:
        return HttpResponseRedirect(f"/profile-completion/{completion.code}")
    return HttpResponseNotFound("链接无效或已失效")
