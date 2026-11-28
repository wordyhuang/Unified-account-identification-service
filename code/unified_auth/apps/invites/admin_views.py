from datetime import datetime

import re
import secrets

from django.core.cache import cache
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.accounts.models import Tenant, User
from apps.audit.models import AuditLog
from apps.invites.appearance import (
    PAGE_TYPES, appearance_changed_detail, normalize_appearance, resolve_appearance,
    tenant_appearance_defaults,
)
from apps.invites.fields import FIELD_REGISTRY
from apps.invites.models import (
    InviteCode, ProfileCompletionCode, WechatBindCode, generate_code, generate_short_code,
)
from common.errors import ErrorCode
from common.response import success, error

from .views import INVITE_EXTRA_FIELDS, _parse_expires_at


def _links(request, code, short_code, page_path):
    """生成页面长链接与短链接（域名取当前请求）。"""
    return {
        "page_url": request.build_absolute_uri(f"{page_path}/{code}"),
        "short_url": request.build_absolute_uri(f"/s/{short_code}"),
    }


def _invite_serialize(obj, request):
    data = {
        "id": obj.id,
        "code": obj.code,
        "short_code": obj.short_code,
        "remark": obj.remark,
        "allowed_phones": obj.allowed_phones or [],
        "user_type": obj.user_type,
        "max_uses": obj.max_uses,
        "used_count": obj.used_count,
        "expires_at": obj.expires_at,
        "status": obj.status,
        "fields": obj.fields,
        "app_id": obj.app_id,
        "app_name": obj.app.name if obj.app else None,
        "registration_mode": "app" if obj.app_id else "builtin",
        "appearance": obj.appearance,
        "appearance_effective": resolve_appearance(obj, obj.tenant, "invite"),
        "auto_group_ids": obj.auto_group_ids or [],
        "created_by": obj.created_by,
        "created_at": obj.created_at,
    }
    data.update(_links(request, obj.code, obj.short_code, "/invite"))
    return data


def _resolve_invite_app(body, tenant_id):
    """解析并校验邀请码绑定的接入应用；返回 (app, error_message)。"""
    raw = body.get("app_id")
    if raw in (None, "", 0, "0"):
        return None, None
    from apps.applications.models import Application
    app = Application.objects.filter(id=raw, tenant_id=tenant_id).first()
    if app is None:
        return None, "接入应用不存在或不属于当前租户"
    if not app.status:
        return None, "接入应用已停用"
    return app, None


def _completion_serialize(obj, request):
    data = {
        "id": obj.id,
        "code": obj.code,
        "short_code": obj.short_code,
        "mode": obj.mode,
        "user_id": obj.user_id,
        "username": obj.user.username if obj.user else None,
        "fields": obj.fields or [],
        "field_labels": [
            FIELD_REGISTRY[f]["label"] for f in (obj.fields or []) if f in FIELD_REGISTRY
        ],
        "allow_repeated": obj.allow_repeated,
        "max_uses": obj.max_uses,
        "used_count": obj.used_count,
        "expires_at": obj.expires_at,
        "status": obj.status,
        "appearance": obj.appearance,
        "appearance_effective": resolve_appearance(obj, obj.tenant, "completion"),
        "created_by": obj.created_by,
        "created_at": obj.created_at,
    }
    data.update(_links(request, obj.code, obj.short_code, "/profile-completion"))
    return data


def _normalize_phones(raw):
    """白名单手机号规范化：字符串列表、去空、去重。"""
    if raw is None:
        return None
    if not isinstance(raw, list):
        return None
    phones = []
    for item in raw:
        phone = str(item).strip()
        if not phone or not phone.isdigit() or len(phone) > 20:
            return None
        if phone not in phones:
            phones.append(phone)
    return phones


def _parse_appearance_field(body):
    """解析请求体中的 appearance 字段。

    返回 (appearance, error_message)：
    - 未传该字段   → (UNSET, None)，保持现值不变
    - 传 null      → (None, None)，清除码级覆盖
    - 传对象/{}    → (规范化 dict, None) 或 (None, 错误)
    """
    UNSET = object()
    if "appearance" not in body:
        return UNSET, None
    appearance, err = normalize_appearance(body.get("appearance"))
    return appearance, err


def _parse_auto_group_ids(raw, tenant_id):
    """解析并校验自动入组 id 列表；返回 (ids, error_message)。"""
    if raw in (None, ""):
        return [], None
    if not isinstance(raw, list):
        return None, "自动入组必须是用户组 id 数组"
    ids = []
    for value in raw:
        try:
            gid = int(value)
        except (TypeError, ValueError):
            return None, "自动入组中存在非法的用户组 id"
        if gid not in ids:
            ids.append(gid)

    from apps.users.models import UserGroup
    valid_ids = set(
        UserGroup.objects.filter(id__in=ids, tenant_id=tenant_id).values_list("id", flat=True)
    )
    invalid = [gid for gid in ids if gid not in valid_ids]
    if invalid:
        return None, "以下用户组不存在或不属于当前租户：%s" % invalid
    return ids, None


def _validate_invite_group_requirement(app, user_type, auto_group_ids):
    """应用启用组准入时，内部用户邀请码必须配置自动入组，且组必须已绑定到该应用。"""
    if app is None or user_type != "internal":
        return None
    from apps.users.access import is_open_app
    from apps.users.models import AppGroupBinding

    if is_open_app(app):
        return None
    bound_ids = set(
        AppGroupBinding.objects.filter(app=app).values_list("group_id", flat=True)
    )
    if not bound_ids:
        return None
    if not auto_group_ids:
        return "该应用已启用用户组准入，请为邀请码配置注册后自动加入的用户组"
    extra = [gid for gid in auto_group_ids if gid not in bound_ids]
    if extra:
        return "自动入组必须是该应用已绑定的用户组：%s" % extra
    return None


# ==================== 邀请码管理 ====================


@api_view(["GET", "POST"])
def invite_codes_view(request):
    if request.method == "GET":
        search = (request.GET.get("search") or "").strip()
        status_filter = request.GET.get("status", "")
        page = max(int(request.GET.get("page", 1) or 1), 1)
        page_size = min(max(int(request.GET.get("page_size", 20) or 20), 1), 100)

        qs = InviteCode.objects.filter(tenant_id=request.tenant_id)
        if search:
            from django.db.models import Q
            qs = qs.filter(Q(remark__icontains=search) | Q(short_code__icontains=search))
        if status_filter in ("0", "1"):
            qs = qs.filter(status=int(status_filter))
        total = qs.count()
        items = qs[(page - 1) * page_size: page * page_size]
        return Response(success({
            "items": [_invite_serialize(o, request) for o in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }))

    body = request.data if isinstance(request.data, dict) else {}
    allowed_phones = _normalize_phones(body.get("allowed_phones"))
    if body.get("allowed_phones") is not None and allowed_phones is None:
        return Response(error(ErrorCode.PARAM_INVALID, message="手机白名单格式错误"), status=400)

    user_type = body.get("user_type") or "external"
    if user_type not in ("internal", "external"):
        return Response(error(ErrorCode.PARAM_INVALID, message="用户类型不合法"), status=400)

    # 防刷：使用次数上限强制生效，未指定时默认 10，范围 1-1000
    max_uses = body.get("max_uses")
    if max_uses is None:
        max_uses = 10
    else:
        try:
            max_uses = int(max_uses)
            if not 1 <= max_uses <= 1000:
                raise ValueError
        except (TypeError, ValueError):
            return Response(error(ErrorCode.PARAM_INVALID, message="使用次数上限不合法（1-1000）"), status=400)

    expires_at = _parse_expires_at(body.get("expires_at"))
    if body.get("expires_at") and expires_at is None:
        return Response(error(ErrorCode.PARAM_INVALID, message="有效期格式错误"), status=400)

    # 注册字段覆盖（null 继承租户默认）与注册页承载应用
    invite_fields, fields_err = _normalize_invite_fields(body.get("fields"))
    if fields_err:
        return Response(error(ErrorCode.PARAM_INVALID, message=fields_err), status=400)
    app, app_err = _resolve_invite_app(body, request.tenant_id)
    if app_err:
        return Response(error(ErrorCode.PARAM_INVALID, message=app_err), status=400)

    # 码级页面外观覆盖（未传或传 null 均为使用默认外观）
    appearance, appearance_err = _parse_appearance_field(body)
    if appearance_err:
        return Response(error(ErrorCode.PARAM_INVALID, message=appearance_err), status=400)
    appearance_value = appearance if isinstance(appearance, dict) else None

    auto_group_ids, auto_group_err = _parse_auto_group_ids(
        body.get("auto_group_ids"), request.tenant_id
    )
    if auto_group_err:
        return Response(error(ErrorCode.PARAM_INVALID, message=auto_group_err), status=400)
    group_req_err = _validate_invite_group_requirement(app, user_type, auto_group_ids)
    if group_req_err:
        return Response(error(ErrorCode.PARAM_INVALID, message=group_req_err), status=400)

    while True:
        code = generate_code(32)
        if not InviteCode.objects.filter(code=code).exists():
            break
    while True:
        short_code = generate_short_code(8)
        if not InviteCode.objects.filter(short_code=short_code).exists():
            break

    obj = InviteCode.objects.create(
        tenant_id=request.tenant_id,
        code=code,
        short_code=short_code,
        remark=str(body.get("remark") or "").strip() or None,
        allowed_phones=allowed_phones,
        user_type=user_type,
        max_uses=max_uses,
        expires_at=expires_at,
        fields=invite_fields,
        app=app,
        appearance=appearance_value,
        auto_group_ids=auto_group_ids,
        created_by=request.user.username if request.user else None,
    )
    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username if request.user else "",
        action="admin.invite_code.create",
        resource_type="invite_code",
        resource_id=obj.id,
        detail={
            "short_code": obj.short_code,
            "allowed_phones_count": len(allowed_phones or []),
            **({"appearance_fields": list(appearance_value.keys())} if appearance_value else {}),
            **({"auto_group_ids": auto_group_ids} if auto_group_ids else {}),
        },
    )
    return Response(success(_invite_serialize(obj, request)))


@api_view(["GET", "PATCH", "DELETE"])
def invite_code_detail_view(request, code_id):
    try:
        obj = InviteCode.objects.get(id=code_id, tenant_id=request.tenant_id)
    except InviteCode.DoesNotExist:
        return Response(error(ErrorCode.USER_NOT_FOUND, message="邀请码不存在"), status=404)

    if request.method == "GET":
        return Response(success(_invite_serialize(obj, request)))

    if request.method == "PATCH":
        body = request.data if isinstance(request.data, dict) else {}
        changed = []

        if "status" in body:
            status_value = body.get("status")
            if status_value not in (0, 1, "0", "1"):
                return Response(error(ErrorCode.PARAM_INVALID, message="status 取值不合法"), status=400)
            obj.status = int(status_value)
            changed.append("status")

        if "remark" in body:
            obj.remark = str(body.get("remark") or "").strip() or None
            changed.append("remark")

        if "allowed_phones" in body:
            allowed_phones = _normalize_phones(body.get("allowed_phones"))
            if body.get("allowed_phones") is not None and allowed_phones is None:
                return Response(error(ErrorCode.PARAM_INVALID, message="手机白名单格式错误"), status=400)
            obj.allowed_phones = allowed_phones
            changed.append("allowed_phones")

        if "fields" in body:
            invite_fields, fields_err = _normalize_invite_fields(body.get("fields"))
            if fields_err:
                return Response(error(ErrorCode.PARAM_INVALID, message=fields_err), status=400)
            obj.fields = invite_fields
            changed.append("fields")

        if "app_id" in body:
            app, app_err = _resolve_invite_app(body, request.tenant_id)
            if app_err:
                return Response(error(ErrorCode.PARAM_INVALID, message=app_err), status=400)
            obj.app = app
            changed.append("app_id")

        if "user_type" in body:
            user_type = body.get("user_type")
            if user_type not in ("internal", "external"):
                return Response(error(ErrorCode.PARAM_INVALID, message="用户类型不合法"), status=400)
            obj.user_type = user_type
            changed.append("user_type")

        if "max_uses" in body:
            # 防刷：1-1000 且不得低于已使用次数
            try:
                max_uses = int(body.get("max_uses"))
                if not 1 <= max_uses <= 1000:
                    raise ValueError
            except (TypeError, ValueError):
                return Response(error(ErrorCode.PARAM_INVALID, message="使用次数上限不合法（1-1000）"), status=400)
            if max_uses < obj.used_count:
                return Response(error(ErrorCode.PARAM_INVALID, message="使用次数上限不能低于已使用次数"), status=400)
            obj.max_uses = max_uses
            changed.append("max_uses")

        if "expires_at" in body:
            expires_at = _parse_expires_at(body.get("expires_at"))
            if body.get("expires_at") and expires_at is None:
                return Response(error(ErrorCode.PARAM_INVALID, message="有效期格式错误"), status=400)
            obj.expires_at = expires_at
            changed.append("expires_at")

        if "appearance" in body:
            appearance, appearance_err = _parse_appearance_field(body)
            if appearance_err:
                return Response(error(ErrorCode.PARAM_INVALID, message=appearance_err), status=400)
            appearance_changes = appearance_changed_detail(obj.appearance, appearance)
            obj.appearance = appearance
            changed.append("appearance")

        if "auto_group_ids" in body:
            auto_group_ids, auto_group_err = _parse_auto_group_ids(
                body.get("auto_group_ids"), request.tenant_id
            )
            if auto_group_err:
                return Response(error(ErrorCode.PARAM_INVALID, message=auto_group_err), status=400)
            obj.auto_group_ids = auto_group_ids
            changed.append("auto_group_ids")

        # 承载应用/用户类型/自动入组任一变化时，重新校验组准入闭环
        if "app_id" in body or "user_type" in body or "auto_group_ids" in body:
            group_req_err = _validate_invite_group_requirement(
                obj.app, obj.user_type, obj.auto_group_ids or []
            )
            if group_req_err:
                return Response(error(ErrorCode.PARAM_INVALID, message=group_req_err), status=400)

        if not changed:
            return Response(error(ErrorCode.PARAM_MISSING, message="缺少需要修改的配置项"), status=400)

        obj.save()
        audit_detail = {"changed": changed}
        if "appearance" in changed and appearance_changes:
            audit_detail["appearance_changed"] = appearance_changes
        if "auto_group_ids" in changed:
            audit_detail["auto_group_ids"] = obj.auto_group_ids or []
        AuditLog.objects.create(
            tenant_id=request.tenant_id,
            actor_id=request.user_id,
            actor_name=request.user.username if request.user else "",
            action="admin.invite_code.update",
            resource_type="invite_code",
            resource_id=obj.id,
            detail=audit_detail,
        )
        return Response(success(_invite_serialize(obj, request)))

    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username if request.user else "",
        action="admin.invite_code.delete",
        resource_type="invite_code",
        resource_id=obj.id,
        detail={"short_code": obj.short_code},
    )
    obj.delete()
    return Response(success())


@api_view(["GET"])
def completion_fields_view(request):
    """资料补全码可配置字段白名单（供前端生成勾选框）。"""
    items = [
        {"name": name, "label": info["label"], "type": info.get("type", "text")}
        for name, info in FIELD_REGISTRY.items()
    ]
    return Response(success({"items": items}))


# ==================== 资料补全码管理 ====================


@api_view(["GET", "POST"])
def completion_codes_view(request):
    if request.method == "GET":
        search = (request.GET.get("search") or "").strip()
        page = max(int(request.GET.get("page", 1) or 1), 1)
        page_size = min(max(int(request.GET.get("page_size", 20) or 20), 1), 100)

        qs = ProfileCompletionCode.objects.filter(tenant_id=request.tenant_id)
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(user__username__icontains=search) | Q(short_code__icontains=search)
            )
        total = qs.count()
        items = qs[(page - 1) * page_size: page * page_size]
        return Response(success({
            "items": [_completion_serialize(o, request) for o in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }))

    body = request.data if isinstance(request.data, dict) else {}
    mode = body.get("mode") or "single"
    if mode not in ("single", "shared"):
        return Response(error(ErrorCode.PARAM_INVALID, message="mode 不合法"), status=400)

    # 字段白名单校验
    fields = body.get("fields")
    if not isinstance(fields, list) or not fields:
        return Response(error(ErrorCode.PARAM_INVALID, message="fields 必须为非空字段数组"), status=400)
    fields = [str(f).strip() for f in fields]
    invalid = [f for f in fields if f not in FIELD_REGISTRY]
    if invalid:
        return Response(
            error(ErrorCode.PARAM_INVALID, message=f"不支持的补全字段: {', '.join(invalid)}"),
            status=400,
        )
    fields = list(dict.fromkeys(fields))

    user = None
    if mode == "single":
        user_id = body.get("user_id")
        if not user_id:
            return Response(error(ErrorCode.PARAM_MISSING, message="单人模式必须指定用户"), status=400)
        user = User.objects.filter(id=user_id, tenant_id=request.tenant_id).first()
        if user is None:
            return Response(error(ErrorCode.USER_NOT_FOUND), status=404)
    else:
        if body.get("user_id"):
            return Response(
                error(ErrorCode.PARAM_INVALID, message="多人通用模式不能绑定用户"), status=400
            )

    allow_repeated = bool(body.get("allow_repeated", False))
    max_uses = body.get("max_uses")
    if mode == "shared" or allow_repeated:
        if max_uses is not None:
            try:
                max_uses = int(max_uses)
                if max_uses < 1:
                    raise ValueError
            except (TypeError, ValueError):
                return Response(error(ErrorCode.PARAM_INVALID, message="使用次数上限不合法"), status=400)

    expires_at = _parse_expires_at(body.get("expires_at"))
    if body.get("expires_at") and expires_at is None:
        return Response(error(ErrorCode.PARAM_INVALID, message="有效期格式错误"), status=400)

    # 码级页面外观覆盖（未传或传 null 均为使用默认外观）
    appearance, appearance_err = _parse_appearance_field(body)
    if appearance_err:
        return Response(error(ErrorCode.PARAM_INVALID, message=appearance_err), status=400)
    appearance_value = appearance if isinstance(appearance, dict) else None

    while True:
        code = generate_code(32)
        if not ProfileCompletionCode.objects.filter(code=code).exists():
            break
    while True:
        short_code = generate_short_code(8)
        if not ProfileCompletionCode.objects.filter(short_code=short_code).exists():
            break

    obj = ProfileCompletionCode.objects.create(
        tenant_id=request.tenant_id,
        user=user,
        code=code,
        short_code=short_code,
        mode=mode,
        fields=fields,
        allow_repeated=allow_repeated,
        max_uses=max_uses,
        expires_at=expires_at,
        appearance=appearance_value,
        created_by=request.user.username if request.user else None,
    )
    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username if request.user else "",
        action="admin.completion_code.create",
        resource_type="profile_completion_code",
        resource_id=obj.id,
        detail={
            "mode": mode, "fields": fields, "username": user.username if user else None,
            **({"appearance_fields": list(appearance_value.keys())} if appearance_value else {}),
        },
    )
    return Response(success(_completion_serialize(obj, request)))


@api_view(["GET", "PATCH", "DELETE"])
def completion_code_detail_view(request, code_id):
    try:
        obj = ProfileCompletionCode.objects.get(id=code_id, tenant_id=request.tenant_id)
    except ProfileCompletionCode.DoesNotExist:
        return Response(error(ErrorCode.USER_NOT_FOUND, message="补全码不存在"), status=404)

    if request.method == "GET":
        return Response(success(_completion_serialize(obj, request)))

    if request.method == "PATCH":
        body = request.data if isinstance(request.data, dict) else {}
        changed = []

        if "mode" in body and body.get("mode") != obj.mode:
            return Response(error(ErrorCode.PARAM_INVALID, message="mode 创建后不可修改"), status=400)

        if "status" in body:
            status_value = body.get("status")
            if status_value not in (0, 1, "0", "1"):
                return Response(error(ErrorCode.PARAM_INVALID, message="status 取值不合法"), status=400)
            obj.status = int(status_value)
            changed.append("status")

        if "fields" in body:
            fields = body.get("fields")
            if not isinstance(fields, list) or not fields:
                return Response(error(ErrorCode.PARAM_INVALID, message="fields 必须为非空字段数组"), status=400)
            fields = [str(f).strip() for f in fields]
            invalid = [f for f in fields if f not in FIELD_REGISTRY]
            if invalid:
                return Response(
                    error(ErrorCode.PARAM_INVALID, message=f"不支持的补全字段: {', '.join(invalid)}"),
                    status=400,
                )
            obj.fields = list(dict.fromkeys(fields))
            changed.append("fields")

        if "allow_repeated" in body:
            if obj.mode != "single":
                return Response(error(ErrorCode.PARAM_INVALID, message="多人通用模式不支持该配置"), status=400)
            obj.allow_repeated = bool(body.get("allow_repeated"))
            changed.append("allow_repeated")

        if "user_id" in body:
            if obj.mode != "single":
                return Response(error(ErrorCode.PARAM_INVALID, message="多人通用模式不能绑定用户"), status=400)
            user = User.objects.filter(id=body.get("user_id"), tenant_id=request.tenant_id).first()
            if user is None:
                return Response(error(ErrorCode.USER_NOT_FOUND), status=404)
            obj.user = user
            changed.append("user_id")

        if "max_uses" in body:
            try:
                max_uses = int(body.get("max_uses"))
                if max_uses < 1:
                    raise ValueError
            except (TypeError, ValueError):
                return Response(error(ErrorCode.PARAM_INVALID, message="使用次数上限不合法"), status=400)
            if max_uses < obj.used_count:
                return Response(error(ErrorCode.PARAM_INVALID, message="使用次数上限不能低于已使用次数"), status=400)
            obj.max_uses = max_uses
            changed.append("max_uses")

        if "expires_at" in body:
            expires_at = _parse_expires_at(body.get("expires_at"))
            if body.get("expires_at") and expires_at is None:
                return Response(error(ErrorCode.PARAM_INVALID, message="有效期格式错误"), status=400)
            obj.expires_at = expires_at
            changed.append("expires_at")

        if "appearance" in body:
            appearance, appearance_err = _parse_appearance_field(body)
            if appearance_err:
                return Response(error(ErrorCode.PARAM_INVALID, message=appearance_err), status=400)
            appearance_changes = appearance_changed_detail(obj.appearance, appearance)
            obj.appearance = appearance
            changed.append("appearance")

        if not changed:
            return Response(error(ErrorCode.PARAM_MISSING, message="缺少需要修改的配置项"), status=400)

        obj.save()
        audit_detail = {"changed": changed}
        if "appearance" in changed and appearance_changes:
            audit_detail["appearance_changed"] = appearance_changes
        AuditLog.objects.create(
            tenant_id=request.tenant_id,
            actor_id=request.user_id,
            actor_name=request.user.username if request.user else "",
            action="admin.completion_code.update",
            resource_type="profile_completion_code",
            resource_id=obj.id,
            detail=audit_detail,
        )
        return Response(success(_completion_serialize(obj, request)))

    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username if request.user else "",
        action="admin.completion_code.delete",
        resource_type="profile_completion_code",
        resource_id=obj.id,
        detail={"short_code": obj.short_code, "mode": obj.mode},
    )
    obj.delete()
    return Response(success())


# ==================== 微信绑定码管理 ====================


def _wechat_serialize(obj):
    data = {
        "id": obj.id,
        "code": obj.code,
        "short_code": obj.short_code,
        "mode": obj.mode,
        "user_id": obj.user_id,
        "username": obj.user.username if obj.user else None,
        "max_uses": obj.max_uses,
        "used_count": obj.used_count,
        "expires_at": obj.expires_at,
        "status": obj.status,
        "remark": obj.remark,
        "created_by": obj.created_by,
        "created_at": obj.created_at,
    }
    return data


@api_view(["GET", "POST"])
def wechat_bind_codes_view(request):
    if request.method == "GET":
        search = (request.GET.get("search") or "").strip()
        status_filter = request.GET.get("status", "")
        page = max(int(request.GET.get("page", 1) or 1), 1)
        page_size = min(max(int(request.GET.get("page_size", 20) or 20), 1), 100)

        qs = WechatBindCode.objects.filter(tenant_id=request.tenant_id)
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(short_code__icontains=search) | Q(remark__icontains=search)
                | Q(user__username__icontains=search)
            )
        if status_filter in ("0", "1"):
            qs = qs.filter(status=int(status_filter))
        total = qs.count()
        items = qs[(page - 1) * page_size: page * page_size]
        return Response(success({
            "items": [_wechat_serialize(o) for o in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }))

    body = request.data if isinstance(request.data, dict) else {}
    mode = body.get("mode") or "single"
    if mode not in ("single", "shared"):
        return Response(error(ErrorCode.PARAM_INVALID, message="mode 不合法"), status=400)

    user = None
    if mode == "single":
        user_id = body.get("user_id")
        if not user_id:
            return Response(error(ErrorCode.PARAM_MISSING, message="单人模式必须指定用户"), status=400)
        user = User.objects.filter(id=user_id, tenant_id=request.tenant_id).first()
        if user is None:
            return Response(error(ErrorCode.USER_NOT_FOUND), status=404)
    else:
        if body.get("user_id"):
            return Response(
                error(ErrorCode.PARAM_INVALID, message="多人通用模式不能绑定用户"), status=400
            )

    max_uses = body.get("max_uses")
    if max_uses is not None:
        try:
            max_uses = int(max_uses)
            if max_uses < 1:
                raise ValueError
        except (TypeError, ValueError):
            return Response(error(ErrorCode.PARAM_INVALID, message="使用次数上限不合法"), status=400)

    expires_at = _parse_expires_at(body.get("expires_at"))
    if body.get("expires_at") and expires_at is None:
        return Response(error(ErrorCode.PARAM_INVALID, message="有效期格式错误"), status=400)

    remark = str(body.get("remark") or "").strip() or None
    if remark and len(remark) > 255:
        return Response(error(ErrorCode.PARAM_INVALID, message="备注过长"), status=400)

    while True:
        code = generate_code(32)
        if not WechatBindCode.objects.filter(code=code).exists():
            break
    while True:
        short_code = generate_short_code(8)
        if not WechatBindCode.objects.filter(short_code=short_code).exists():
            break

    obj = WechatBindCode.objects.create(
        tenant_id=request.tenant_id,
        user=user,
        code=code,
        short_code=short_code,
        mode=mode,
        max_uses=max_uses,
        expires_at=expires_at,
        remark=remark,
        created_by=request.user.username if request.user else None,
    )
    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username if request.user else "",
        action="admin.wechat_bind_code.create",
        resource_type="wechat_bind_code",
        resource_id=obj.id,
        detail={"mode": mode, "username": user.username if user else None, "short_code": obj.short_code},
    )
    return Response(success(_wechat_serialize(obj)))


@api_view(["GET", "PATCH", "DELETE"])
def wechat_bind_code_detail_view(request, code_id):
    try:
        obj = WechatBindCode.objects.get(id=code_id, tenant_id=request.tenant_id)
    except WechatBindCode.DoesNotExist:
        return Response(error(ErrorCode.USER_NOT_FOUND, message="绑定码不存在"), status=404)

    if request.method == "GET":
        return Response(success(_wechat_serialize(obj)))

    if request.method == "PATCH":
        body = request.data if isinstance(request.data, dict) else {}
        changed = []

        if "mode" in body and body.get("mode") != obj.mode:
            return Response(error(ErrorCode.PARAM_INVALID, message="mode 创建后不可修改"), status=400)

        if "status" in body:
            status_value = body.get("status")
            if status_value not in (0, 1, "0", "1"):
                return Response(error(ErrorCode.PARAM_INVALID, message="status 取值不合法"), status=400)
            obj.status = int(status_value)
            changed.append("status")

        if "user_id" in body:
            if obj.mode != "single":
                return Response(error(ErrorCode.PARAM_INVALID, message="多人通用模式不能绑定用户"), status=400)
            user = User.objects.filter(id=body.get("user_id"), tenant_id=request.tenant_id).first()
            if user is None:
                return Response(error(ErrorCode.USER_NOT_FOUND), status=404)
            obj.user = user
            changed.append("user_id")

        if "max_uses" in body:
            try:
                max_uses = int(body.get("max_uses"))
                if max_uses < 1:
                    raise ValueError
            except (TypeError, ValueError):
                return Response(error(ErrorCode.PARAM_INVALID, message="使用次数上限不合法"), status=400)
            if max_uses < obj.used_count:
                return Response(error(ErrorCode.PARAM_INVALID, message="使用次数上限不能低于已使用次数"), status=400)
            obj.max_uses = max_uses
            changed.append("max_uses")

        if "expires_at" in body:
            expires_at = _parse_expires_at(body.get("expires_at"))
            if body.get("expires_at") and expires_at is None:
                return Response(error(ErrorCode.PARAM_INVALID, message="有效期格式错误"), status=400)
            obj.expires_at = expires_at
            changed.append("expires_at")

        if "remark" in body:
            remark = str(body.get("remark") or "").strip() or None
            if remark and len(remark) > 255:
                return Response(error(ErrorCode.PARAM_INVALID, message="备注过长"), status=400)
            obj.remark = remark
            changed.append("remark")

        if not changed:
            return Response(error(ErrorCode.PARAM_MISSING, message="缺少需要修改的配置项"), status=400)

        obj.save()
        AuditLog.objects.create(
            tenant_id=request.tenant_id,
            actor_id=request.user_id,
            actor_name=request.user.username if request.user else "",
            action="admin.wechat_bind_code.update",
            resource_type="wechat_bind_code",
            resource_id=obj.id,
            detail={"changed": changed},
        )
        return Response(success(_wechat_serialize(obj)))

    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username if request.user else "",
        action="admin.wechat_bind_code.delete",
        resource_type="wechat_bind_code",
        resource_id=obj.id,
        detail={"short_code": obj.short_code, "mode": obj.mode},
    )
    obj.delete()
    return Response(success())


# ==================== 邀请注册页品牌与字段配置 ====================

THEME_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
LOGO_MAX_LENGTH = 300000  # 约 220KB 图片（data URI base64）


def _normalize_invite_fields(raw):
    """校验并规范化注册字段配置；返回 (fields, error_message)。"""
    if raw is None:
        return None, None
    if not isinstance(raw, list):
        return None, "字段配置必须为数组"
    out = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            return None, "字段配置元素必须为对象"
        key = str(item.get("key") or "").strip()
        if not key:
            return None, "字段配置缺少 key"
        if key in ("username", "password"):
            return None, "用户名与密码为固定字段，不可配置"
        if key not in FIELD_REGISTRY and key not in INVITE_EXTRA_FIELDS:
            return None, f"不支持的字段: {key}"
        if key in seen:
            continue
        out.append({"key": key, "required": bool(item.get("required"))})
        seen.add(key)
    return out, None


@api_view(["GET", "PUT"])
def invite_brand_view(request):
    """当前租户的邀请注册页配置（品牌 + 默认字段 + 文案）。"""
    tenant = Tenant.objects.filter(id=request.tenant_id).first()
    if tenant is None:
        if request.method == "GET":
            return Response(success({
                "brand_name": "", "welcome": "", "theme_color": "", "logo": "",
                "fields": None, "submit_text": "", "success_text": "", "agreement": "",
                "background": "", "footer_text": "",
            }))
        return Response(error(ErrorCode.PARAM_INVALID, message="租户不存在"), status=404)

    if request.method == "GET":
        return Response(success({
            "brand_name": tenant.invite_brand_name or "",
            "welcome": tenant.invite_welcome or "",
            "theme_color": tenant.invite_theme_color or "",
            "logo": tenant.invite_logo or "",
            "fields": tenant.invite_fields,
            "submit_text": tenant.invite_submit_text or "",
            "success_text": tenant.invite_success_text or "",
            "agreement": tenant.invite_agreement or "",
            "background": tenant.invite_background or "",
            "footer_text": tenant.invite_footer_text or "",
        }))

    body = request.data if isinstance(request.data, dict) else {}
    brand_name = str(body.get("brand_name") or "").strip()[:128]
    welcome = str(body.get("welcome") or "").strip()[:255]
    theme_color = str(body.get("theme_color") or "").strip()
    logo = str(body.get("logo") or "").strip()
    submit_text = str(body.get("submit_text") or "").strip()[:32]
    success_text = str(body.get("success_text") or "").strip()[:255]
    agreement = str(body.get("agreement") or "").strip()[:255]

    if theme_color and not THEME_COLOR_PATTERN.match(theme_color):
        return Response(error(ErrorCode.PARAM_INVALID, message="主题色格式应为 #RRGGBB"), status=400)
    if len(logo) > LOGO_MAX_LENGTH:
        return Response(error(ErrorCode.PARAM_INVALID, message="Logo 体积过大（上限约 220KB）"), status=400)

    # 扩展默认外观项：背景（#RRGGBB 或图片）与页脚文案
    background = str(body.get("background") or "").strip()
    if background and not THEME_COLOR_PATTERN.match(background):
        from .appearance import _validate_image
        img_err = _validate_image(background)
        if img_err:
            return Response(error(ErrorCode.PARAM_INVALID, message=f"背景 {img_err}"), status=400)
    footer_text = str(body.get("footer_text") or "").strip()[:100]

    invite_fields = tenant.invite_fields
    if "fields" in body:
        invite_fields, fields_err = _normalize_invite_fields(body.get("fields"))
        if fields_err:
            return Response(error(ErrorCode.PARAM_INVALID, message=fields_err), status=400)

    tenant.invite_brand_name = brand_name
    tenant.invite_welcome = welcome
    tenant.invite_theme_color = theme_color
    tenant.invite_logo = logo
    tenant.invite_fields = invite_fields
    tenant.invite_submit_text = submit_text
    tenant.invite_success_text = success_text
    tenant.invite_agreement = agreement
    tenant.invite_background = background
    tenant.invite_footer_text = footer_text
    tenant.save(update_fields=[
        "invite_brand_name", "invite_welcome", "invite_theme_color", "invite_logo",
        "invite_fields", "invite_submit_text", "invite_success_text", "invite_agreement",
        "invite_background", "invite_footer_text",
    ])

    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username if request.user else "",
        action="admin.invite_brand.update",
        resource_type="tenant",
        resource_id=tenant.id,
        detail={
            "brand_name": brand_name, "theme_color": theme_color, "has_logo": bool(logo),
            "fields_count": len(invite_fields or []),
            "has_background": bool(background), "has_footer_text": bool(footer_text),
        },
    )
    return Response(success({
        "brand_name": brand_name,
        "welcome": welcome,
        "theme_color": theme_color,
        "logo": logo,
        "fields": invite_fields,
        "submit_text": submit_text,
        "success_text": success_text,
        "agreement": agreement,
        "background": background,
        "footer_text": footer_text,
    }))


@api_view(["GET", "PUT"])
def completion_brand_view(request):
    """当前租户的资料补全页默认外观（租户级，逐项回退邀请品牌与系统默认）。"""
    tenant = Tenant.objects.filter(id=request.tenant_id).first()
    if tenant is None:
        if request.method == "GET":
            return Response(success({"appearance": {}, "appearance_effective": {}}))
        return Response(error(ErrorCode.PARAM_INVALID, message="租户不存在"), status=404)

    if request.method == "GET":
        return Response(success({
            "appearance": tenant.completion_appearance or {},
            "appearance_effective": tenant_appearance_defaults(tenant, "completion"),
        }))

    body = request.data if isinstance(request.data, dict) else {}
    appearance, err = normalize_appearance(body.get("appearance"))
    if err:
        return Response(error(ErrorCode.PARAM_INVALID, message=err), status=400)

    # 传 null 或 {} 均表示清除租户级覆盖，回退邀请品牌与系统默认
    tenant.completion_appearance = appearance if appearance else None
    tenant.save(update_fields=["completion_appearance"])

    changed = appearance_changed_detail(
        {}, tenant.completion_appearance or {}
    )
    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username if request.user else "",
        action="admin.completion_brand.update",
        resource_type="tenant",
        resource_id=tenant.id,
        detail={"appearance_fields": list((tenant.completion_appearance or {}).keys()), "changed": changed},
    )
    return Response(success({
        "appearance": tenant.completion_appearance or {},
        "appearance_effective": tenant_appearance_defaults(tenant, "completion"),
    }))


@api_view(["GET"])
def invite_fields_registry_view(request):
    """注册页可选字段清单（FIELD_REGISTRY + 手机号等特殊字段）。"""
    items = []
    for name, info in FIELD_REGISTRY.items():
        item = {"key": name, "label": info["label"], "type": info.get("type", "text")}
        if info.get("type") == "select":
            item["options"] = info.get("options", [])
        items.append(item)
    for name, info in INVITE_EXTRA_FIELDS.items():
        if name in FIELD_REGISTRY:
            continue
        items.append({"key": name, "label": info["label"], "type": info.get("type", "text")})
    return Response(success({"items": items}))


# ==================== 页面外观预览 ====================

PREVIEW_CACHE_PREFIX = "appearance_preview:"
PREVIEW_TTL = 600  # 预览 token 10 分钟有效


@api_view(["POST"])
def appearance_preview_view(request):
    """外观实时预览：以「待保存的临时配置」参与解析，返回生效值与一次性预览 token。"""
    body = request.data if isinstance(request.data, dict) else {}

    page_type = body.get("page_type") or "invite"
    if page_type not in PAGE_TYPES:
        return Response(error(ErrorCode.PARAM_INVALID, message="page_type 不合法"), status=400)

    # 临时配置：传了就用临时值（预览即将保存的效果），未传则取码上已存值
    code_id = body.get("code_id")
    code_obj = None
    if "appearance" not in body and code_id:
        model = InviteCode if page_type == "invite" else ProfileCompletionCode
        code_obj = model.objects.filter(id=code_id, tenant_id=request.tenant_id).first()

    if "appearance" in body:
        appearance, appearance_err = normalize_appearance(body.get("appearance"))
        if appearance_err:
            return Response(error(ErrorCode.PARAM_INVALID, message=appearance_err), status=400)
        preview_cfg = appearance if isinstance(appearance, dict) else {}
    else:
        preview_cfg = (code_obj.appearance or {}) if code_obj else {}

    tenant = Tenant.objects.filter(id=request.tenant_id).first()

    class _PreviewCode:
        """临时码对象：仅携带待预览的外观配置，不触碰数据库。"""
        appearance = preview_cfg

    effective = resolve_appearance(_PreviewCode(), tenant, page_type)

    token = f"pv_{secrets.token_urlsafe(24)}"
    cache.set(
        f"{PREVIEW_CACHE_PREFIX}{token}",
        {"page_type": page_type, "effective": effective},
        timeout=PREVIEW_TTL,
    )
    return Response(success({
        "appearance_effective": effective,
        "preview_token": token,
    }))
