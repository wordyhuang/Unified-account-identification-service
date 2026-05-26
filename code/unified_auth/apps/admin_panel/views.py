import json
import csv
import io
import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from django.conf import settings
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone as tz
from rest_framework.decorators import api_view
from rest_framework.response import Response
from common.response import success, error
from common.errors import ErrorCode
from common.utils import create_access_token, generate_refresh_token
from apps.accounts.models import Tenant, User, Department
from apps.applications.models import Application
from apps.rbac.models import Role, ApiPermission, RolePermission, AppRoleBinding
from apps.audit.models import AuditLog
from .serializers import (
    AdminCreateUserSerializer, AdminUpdateUserSerializer,
    AdminUserStatusSerializer, AdminResetPasswordSerializer,
    AdminCreateAppSerializer, AdminUpdateAppSerializer,
    AdminAppStatusSerializer,
    AdminCreateRoleSerializer, AdminUpdateRoleSerializer,
    AdminBatchUserStatusSerializer, AdminBatchUserDeleteSerializer,
    AdminDepartmentSerializer, AdminDepartmentUpdateSerializer,
    AdminAppPermissionSerializer, AdminCopyRoleSerializer,
    AdminUserImportSerializer, AdminImpersonateSerializer,
    SuperAdminCreateTenantSerializer, SuperAdminUpdateTenantSerializer,
)


def _user_serialize(u):
    role_ids = list(u.roles.values_list("id", flat=True))
    role_names = list(u.roles.values_list("name", flat=True))
    return {
        "id": u.id, "username": u.username, "user_type": u.user_type,
        "email": u.email, "phone": u.phone, "nickname": u.nickname,
        "avatar": u.avatar, "department": u.department,
        "dept_id": u.dept_id,
        "status": u.status, "is_staff": u.is_staff,
        "is_superuser": u.is_superuser,
        "tenant_id": u.tenant_id,
        "role_ids": role_ids,
        "role_names": role_names,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def _app_serialize(a):
    from apps.rbac.models import AppRoleBinding
    bindings = AppRoleBinding.objects.filter(app=a)
    permission_ids = [b.permission_id for b in bindings]
    return {
        "id": a.id, "tenant_id": a.tenant_id, "name": a.name,
        "app_key": a.app_key,
        "callback_urls": a.callback_urls,
        "default_access_user_types": a.default_access_user_types or [],
        "permission_ids": permission_ids,
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


def _role_serialize(r):
    return {
        "id": r.id, "tenant_id": r.tenant_id, "name": r.name,
        "code": r.code,
        "permission_ids": list(r.permissions.values_list("id", flat=True)),
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ======================== 仪表盘 ========================


@api_view(["GET"])
def stats(request):
    total_users = User.objects.filter(tenant_id=request.tenant_id).count()
    active_users = User.objects.filter(tenant_id=request.tenant_id, status=1).count()
    total_apps = Application.objects.filter(tenant_id=request.tenant_id).count()
    active_apps = Application.objects.filter(tenant_id=request.tenant_id, status=True).count()
    today = tz.now().date()
    today_users = User.objects.filter(tenant_id=request.tenant_id, created_at__date=today).count()
    total_roles = Role.objects.filter(tenant_id=request.tenant_id).count()

    from apps.applications.models import AppApiCallStat
    from django.db.models import Sum
    seven_days_ago = today - timedelta(days=6)
    apps = Application.objects.filter(tenant_id=request.tenant_id).values("id", "name", "app_key", "status", "created_at")
    app_stats = []
    for app in apps:
        call_count = AppApiCallStat.objects.filter(
            app_id=app["id"], call_date__gte=seven_days_ago
        ).aggregate(total=Sum("call_count"))["total"] or 0
        app_stats.append({
            "id": app["id"],
            "name": app["name"],
            "app_key": app["app_key"][:8] + "..." if app["app_key"] else "",
            "status": app["status"],
            "call_count_7d": call_count,
            "created_at": app["created_at"].isoformat() if app["created_at"] else None,
        })

    return Response(success({
        "total_users": total_users,
        "active_users": active_users,
        "total_apps": total_apps,
        "active_apps": active_apps,
        "today_new_users": today_users,
        "total_roles": total_roles,
        "app_stats": app_stats,
    }))


@api_view(["GET"])
def recent_activities(request):
    logs = AuditLog.objects.filter(tenant_id=request.tenant_id).order_by("-created_at")[:10]
    return Response(success({
        "activities": [
            {
                "id": log.id,
                "actor_name": log.actor_name,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "detail": log.detail,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }))



# ======================== 统计报表 API ========================


def _login_action_filter():
    return {"action__in": ["auth.login", "sms_login", "social_login", "superadmin.login"]}


def _login_trend_data(tenant_id, days):
    from django.db.models.functions import TruncDate
    qs = AuditLog.objects.filter(**_login_action_filter())
    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)
    start = datetime.now(tz.get_current_timezone()).date() - timedelta(days=days - 1)
    qs = qs.filter(created_at__date__gte=start)
    return (
        qs.annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )


@api_view(["GET"])
def login_trend_view(request):
    days = _parse_days(request, 7)
    data = _login_trend_data(request.tenant_id, days)
    return Response(success({
        "days": days,
        "trend": [{"date": d["date"].isoformat(), "total": d["count"], "success": d["count"], "fail": 0} for d in data],
    }))


@api_view(["GET"])
def login_distribution_view(request):
    qs = AuditLog.objects.filter(**_login_action_filter(), tenant_id=request.tenant_id)
    data = qs.values("action").annotate(count=Count("id")).order_by("-count")
    labels = {"auth.login": "密码登录", "sms_login": "短信登录", "social_login": "社交登录", "superadmin.login": "超管登录"}
    total = sum(d["count"] for d in data) or 1
    items = {}
    for d in data:
        label = labels.get(d["action"], d["action"])
        items[label] = {"count": d["count"], "percentage": f"{(d['count'] / total * 100):.1f}%"}
    return Response(success({"items": items}))


@api_view(["GET"])
def user_growth_view(request):
    days = _parse_days(request, 30)
    start = datetime.now(tz.get_current_timezone()).date() - timedelta(days=days - 1)
    from django.db.models.functions import TruncDate
    data = (
        User.objects.filter(tenant_id=request.tenant_id, created_at__date__gte=start)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(new_users=Count("id"))
        .order_by("date")
    )
    return Response(success({
        "days": days,
        "trend": [{"date": d["date"].isoformat(), "new_users": d["new_users"]} for d in data],
        "current_total": User.objects.filter(tenant_id=request.tenant_id).count(),
    }))


@api_view(["GET"])
def user_type_distribution_view(request):
    qs = User.objects.filter(tenant_id=request.tenant_id)
    total = qs.count() or 1
    data = qs.values("user_type").annotate(count=Count("id")).order_by("-count")
    labels = {"internal": "内部用户", "external": "外部用户", "admin": "管理员"}
    items = {}
    for d in data:
        label = labels.get(d["user_type"], d["user_type"])
        items[label] = {"count": d["count"], "percentage": f"{(d['count'] / total * 100):.1f}%"}
    return Response(success({"items": items}))


@api_view(["GET"])
def active_users_view(request):
    from django.db.models.functions import TruncDate
    tenant_id = request.tenant_id
    today = datetime.now(tz.get_current_timezone()).date()
    yesterday = today - timedelta(days=1)

    def dau(date):
        return User.objects.filter(tenant_id=tenant_id, last_login__date=date).count()

    def active_7d(date):
        start = date - timedelta(days=6)
        return User.objects.filter(tenant_id=tenant_id, last_login__date__gte=start).count()

    dau_today = dau(today)
    dau_yesterday = dau(yesterday)
    avg_7d = sum(dau(today - timedelta(days=i)) for i in range(7)) / 7.0
    mau_current = User.objects.filter(
        tenant_id=tenant_id,
        last_login__month=today.month,
        last_login__year=today.year,
    ).count()
    last_month = today.replace(day=1) - timedelta(days=1)
    mau_last = User.objects.filter(
        tenant_id=tenant_id,
        last_login__month=last_month.month,
        last_login__year=last_month.year,
    ).count()
    total = User.objects.filter(tenant_id=tenant_id).count() or 1
    return Response(success({
        "dau": {"today": dau_today, "yesterday": dau_yesterday, "avg_7d": round(avg_7d, 1)},
        "mau": {"current_month": mau_current, "last_month": mau_last},
        "active_rate": f"{(dau_today / total * 100):.1f}%",
    }))


def _parse_days(request, default):
    days = request.GET.get("days", str(default))
    try:
        return max(1, min(365, int(days)))
    except ValueError:
        return default


# ======================== 用户管理 ========================


@api_view(["GET", "POST"])
def users_view(request):
    if request.method == "GET":
        search = request.GET.get("search", "").strip()
        status_filter = request.GET.get("status", "")
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))

        qs = User.objects.filter(tenant_id=request.tenant_id)
        if search:
            qs = qs.filter(
                username__icontains=search
            ) | qs.filter(phone__icontains=search) | qs.filter(email__icontains=search)
        if status_filter in ("0", "1"):
            qs = qs.filter(status=int(status_filter))

        total = qs.count()
        users = qs.order_by("-created_at")[(page - 1) * page_size:page * page_size]
        return Response(success({
            "users": [_user_serialize(u) for u in users],
            "total": total,
            "page": page,
            "page_size": page_size,
        }))

    ser = AdminCreateUserSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    data = ser.validated_data
    if User.objects.filter(tenant_id=request.tenant_id, username=data["username"]).exists():
        return Response(error(ErrorCode.PARAM_INVALID, message="用户名已存在"), status=400)

    user = User.objects.create(
        tenant_id=request.tenant_id,
        user_type=data["user_type"],
        username=data["username"],
        nickname=data.get("nickname"),
        email=data.get("email"),
        phone=data.get("phone"),
        department=data.get("department"),
    )
    user.set_password(data["password"])
    user.save(update_fields=["password"])
    return Response(success(_user_serialize(user)), status=201)


@api_view(["GET", "PUT", "DELETE"])
def user_detail_view(request, user_id):
    try:
        user = User.objects.get(id=user_id, tenant_id=request.tenant_id)
    except User.DoesNotExist:
        return Response(error(ErrorCode.USER_NOT_FOUND), status=404)

    if request.method == "GET":
        return Response(success(_user_serialize(user)))

    if request.method == "DELETE":
        username = user.username
        user.delete()
        AuditLog.objects.create(
            tenant_id=request.tenant_id,
            actor_id=request.user_id,
            actor_name=request.user.username,
            action="admin.user.delete",
            resource_type="user",
            resource_id=user_id,
            detail={"username": username},
        )
        return Response(success())

    ser = AdminUpdateUserSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    for field, value in ser.validated_data.items():
        if value is not None:
            setattr(user, field, value)
    user.save(update_fields=ser.validated_data.keys())
    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.user.update",
        resource_type="user",
        resource_id=user_id,
        detail=ser.validated_data,
    )
    return Response(success(_user_serialize(user)))


@api_view(["GET", "PUT"])
def user_roles_view(request, user_id):
    try:
        user = User.objects.get(id=user_id, tenant_id=request.tenant_id)
    except User.DoesNotExist:
        return Response(error(ErrorCode.USER_NOT_FOUND), status=404)

    if request.method == "GET":
        roles = user.roles.all()
        return Response(success({
            "role_ids": [r.id for r in roles],
            "roles": [{"id": r.id, "name": r.name, "code": r.code} for r in roles],
        }))

    if request.method == "PUT":
        role_ids = request.data.get("role_ids", [])
        if not isinstance(role_ids, list):
            return Response(error(ErrorCode.PARAM_INVALID, message="role_ids必须是数组"), status=400)

        if role_ids:
            valid_roles = Role.objects.filter(id__in=role_ids, tenant_id=request.tenant_id)
            user.roles.set(valid_roles)
        else:
            user.roles.clear()

        AuditLog.objects.create(
            tenant_id=request.tenant_id,
            actor_id=request.user_id,
            actor_name=request.user.username,
            action="admin.user.update",
            resource_type="user",
            resource_id=user_id,
            detail={"role_ids": role_ids},
        )
        return Response(success({
            "role_ids": [r.id for r in user.roles.all()],
            "roles": [{"id": r.id, "name": r.name, "code": r.code} for r in user.roles.all()],
        }))


@api_view(["PATCH"])
def user_status_view(request, user_id):
    try:
        user = User.objects.get(id=user_id, tenant_id=request.tenant_id)
    except User.DoesNotExist:
        return Response(error(ErrorCode.USER_NOT_FOUND), status=404)

    ser = AdminUserStatusSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    old_status = user.status
    user.status = ser.validated_data["status"]
    user.save(update_fields=["status"])
    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.user.status",
        resource_type="user",
        resource_id=user_id,
        detail={"old_status": old_status, "new_status": user.status},
    )
    return Response(success(_user_serialize(user)))


@api_view(["POST"])
def user_reset_password_view(request, user_id):
    try:
        user = User.objects.get(id=user_id, tenant_id=request.tenant_id)
    except User.DoesNotExist:
        return Response(error(ErrorCode.USER_NOT_FOUND), status=404)

    ser = AdminResetPasswordSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    user.set_password(ser.validated_data["new_password"])
    user.save(update_fields=["password"])
    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.user.reset_password",
        resource_type="user",
        resource_id=user_id,
    )
    return Response(success())


# ======================== 应用管理 ========================


@api_view(["GET", "POST"])
def apps_view(request):
    if request.method == "GET":
        search = request.GET.get("search", "").strip()
        status_filter = request.GET.get("status", "")
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))

        qs = Application.objects.filter(tenant_id=request.tenant_id)
        if search:
            qs = qs.filter(name__icontains=search)
        if status_filter in ("true", "false"):
            qs = qs.filter(status=(status_filter == "true"))

        total = qs.count()
        apps = qs.order_by("-created_at")[(page - 1) * page_size:page * page_size]
        return Response(success({
            "apps": [_app_serialize(a) for a in apps],
            "total": total,
            "page": page,
            "page_size": page_size,
        }))

    ser = AdminCreateAppSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    data = ser.validated_data
    app_key = hashlib.sha256(secrets.token_bytes(32)).hexdigest()[:32]
    app_secret_raw = secrets.token_hex(32)
    app_secret_hash = hashlib.sha256(app_secret_raw.encode()).hexdigest()

    app = Application.objects.create(
        tenant_id=request.tenant_id,
        name=data["name"],
        app_key=app_key,
        app_secret_hash=app_secret_hash,
        callback_urls=data.get("callback_urls"),
        default_access_user_types=data.get("default_access_user_types"),
    )
    result = _app_serialize(app)
    result["app_secret_raw"] = app_secret_raw

    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.app.create",
        resource_type="application",
        resource_id=app.id,
        detail={"name": data["name"]},
    )
    return Response(success(result), status=201)


@api_view(["GET", "PUT"])
def app_detail_view(request, app_id):
    try:
        app = Application.objects.get(id=app_id, tenant_id=request.tenant_id)
    except Application.DoesNotExist:
        return Response(error(ErrorCode.APP_KEY_INVALID), status=404)

    if request.method == "GET":
        return Response(success(_app_serialize(app)))

    ser = AdminUpdateAppSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    data = ser.validated_data
    permission_ids = data.pop("permission_ids", None)

    for field, value in data.items():
        if value is not None:
            setattr(app, field, value)
    app.save(update_fields=data.keys())

    if permission_ids is not None:
        from apps.rbac.models import AppRoleBinding
        AppRoleBinding.objects.filter(app=app).delete()
        for pid in permission_ids:
            AppRoleBinding.objects.create(app=app, permission_id=pid)

    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.app.update",
        resource_type="application",
        resource_id=app_id,
        detail=ser.validated_data,
    )
    return Response(success(_app_serialize(app)))


@api_view(["PATCH"])
def app_status_view(request, app_id):
    try:
        app = Application.objects.get(id=app_id, tenant_id=request.tenant_id)
    except Application.DoesNotExist:
        return Response(error(ErrorCode.APP_KEY_INVALID), status=404)

    ser = AdminAppStatusSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    app.status = ser.validated_data["status"]
    app.save(update_fields=["status"])
    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.app.status",
        resource_type="application",
        resource_id=app_id,
        detail={"new_status": app.status},
    )
    return Response(success(_app_serialize(app)))


@api_view(["POST"])
def app_regenerate_secret_view(request, app_id):
    try:
        app = Application.objects.get(id=app_id, tenant_id=request.tenant_id)
    except Application.DoesNotExist:
        return Response(error(ErrorCode.APP_KEY_INVALID), status=404)

    new_secret = secrets.token_hex(32)
    app.app_secret_hash = hashlib.sha256(new_secret.encode()).hexdigest()
    app.save(update_fields=["app_secret_hash"])
    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.app.regenerate_secret",
        resource_type="application",
        resource_id=app_id,
    )
    return Response(success({"app_id": app.id, "app_secret_raw": new_secret}))


# ======================== 角色权限 ========================


@api_view(["GET"])
def permissions_view(request):
    perms = ApiPermission.objects.all().order_by("category", "code")
    return Response(success({
        "permissions": [
            {
                "id": p.id, "code": p.code, "name": p.name,
                "method": p.method, "path": p.path, "category": p.category,
            }
            for p in perms
        ],
    }))


@api_view(["GET", "POST"])
def roles_view(request):
    if request.method == "GET":
        roles = Role.objects.filter(tenant_id=request.tenant_id).order_by("-created_at")
        return Response(success({"roles": [_role_serialize(r) for r in roles]}))

    ser = AdminCreateRoleSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    data = ser.validated_data
    if Role.objects.filter(tenant_id=request.tenant_id, code=data["code"]).exists():
        return Response(error(ErrorCode.PARAM_INVALID, message="角色编码已存在"), status=400)

    role = Role.objects.create(
        tenant_id=request.tenant_id,
        name=data["name"],
        code=data["code"],
    )
    for pid in data.get("permission_ids", []):
        RolePermission.objects.get_or_create(role=role, permission_id=pid)

    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.role.create",
        resource_type="role",
        resource_id=role.id,
        detail={"name": data["name"], "code": data["code"]},
    )
    return Response(success(_role_serialize(role)), status=201)


@api_view(["GET", "PUT"])
def role_detail_view(request, role_id):
    try:
        role = Role.objects.get(id=role_id, tenant_id=request.tenant_id)
    except Role.DoesNotExist:
        return Response(error(ErrorCode.PERMISSION_DENIED), status=404)

    if request.method == "GET":
        return Response(success(_role_serialize(role)))

    ser = AdminUpdateRoleSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    if "name" in ser.validated_data and ser.validated_data["name"]:
        role.name = ser.validated_data["name"]

    if "permission_ids" in ser.validated_data:
        role.permissions.clear()
        for pid in ser.validated_data["permission_ids"]:
            RolePermission.objects.get_or_create(role=role, permission_id=pid)

    role.save(update_fields=["name"])
    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.role.update",
        resource_type="role",
        resource_id=role_id,
        detail=ser.validated_data,
    )
    return Response(success(_role_serialize(role)))


# ======================== 审计日志 ========================


@api_view(["GET"])
def audit_logs_view(request):
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 20))
    action = request.GET.get("action", "").strip()
    actor = request.GET.get("actor", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    qs = AuditLog.objects.filter(tenant_id=request.tenant_id)
    if action:
        qs = qs.filter(action__icontains=action)
    if actor:
        qs = qs.filter(actor_name__icontains=actor)
    if date_from:
        qs = qs.filter(created_at__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__lte=date_to + " 23:59:59")

    total = qs.count()
    logs = qs.order_by("-created_at")[(page - 1) * page_size : page * page_size]
    return Response(success({
        "logs": [
            {
                "id": log.id, "actor_id": log.actor_id,
                "actor_name": log.actor_name, "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "detail": log.detail,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }))


def superadmin_audit_log(request, action, resource_type=None, resource_id=None, detail=None):
    """
    记录超级管理员操作日志
    """
    ip_address = request.META.get('REMOTE_ADDR', '')
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    AuditLog.objects.create(
        tenant=None,
        actor_name=getattr(request, 'superadmin_username', 'unknown'),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@api_view(["GET"])
def superadmin_global_stats(request):
    """
    全局统计数据（超级管理员）
    """
    from django.db.models import Count, Sum
    from apps.applications.models import Application, AppApiCallStat

    total_tenants = Tenant.objects.count()
    active_tenants = Tenant.objects.filter(status=True).count()
    total_users = User.objects.count()
    active_users = User.objects.filter(status=1).count()
    total_apps = Application.objects.count()
    active_apps = Application.objects.filter(status=True).count()
    total_roles = Role.objects.count()

    tenant_stats = Tenant.objects.annotate(
        user_count=Count('user', distinct=True),
        app_count=Count('application', distinct=True),
    ).values('id', 'name', 'slug', 'status', 'user_count', 'app_count', 'created_at')

    today = tz.now().date()
    seven_days_ago = today - timedelta(days=6)
    app_call_stats = (
        AppApiCallStat.objects.filter(call_date__gte=seven_days_ago)
        .values("app_id", "app__name", "app__tenant__name")
        .annotate(total_calls=Sum("call_count"))
        .order_by("-total_calls")[:10]
    )
    app_stats = [
        {
            "app_id": s["app_id"],
            "app_name": s["app__name"],
            "tenant_name": s["app__tenant__name"],
            "call_count_7d": s["total_calls"],
        }
        for s in app_call_stats
    ]

    return Response(success({
        "total_tenants": total_tenants,
        "active_tenants": active_tenants,
        "total_users": total_users,
        "active_users": active_users,
        "total_apps": total_apps,
        "active_apps": active_apps,
        "total_roles": total_roles,
        "tenant_stats": [
            {
                "id": t["id"], "name": t["name"], "slug": t["slug"],
                "status": t["status"], "user_count": t["user_count"],
                "app_count": t["app_count"],
                "created_at": t["created_at"].isoformat() if t["created_at"] else None,
            }
            for t in tenant_stats
        ],
        "app_stats": app_stats,
    }))


@api_view(["GET", "POST"])
def superadmin_tenants_view(request):
    """
    租户列表和创建（超级管理员）
    """
    if request.method == "GET":
        search = request.GET.get("search", "").strip()
        status_filter = request.GET.get("status", "")
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))

        qs = Tenant.objects.all()
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(slug__icontains=search)
        if status_filter in ["true", "false"]:
            qs = qs.filter(status=(status_filter == "true"))

        total = qs.count()
        tenants = qs.order_by("-created_at")[(page - 1) * page_size : page * page_size]

        return Response(success({
            "tenants": [
                {
                    "id": t.id, "name": t.name, "slug": t.slug,
                    "status": t.status,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                }
                for t in tenants
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }))

    ser = SuperAdminCreateTenantSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    data = ser.validated_data
    if Tenant.objects.filter(slug=data["slug"]).exists():
        return Response(error(ErrorCode.PARAM_INVALID, message="租户标识已存在"), status=400)

    tenant = Tenant.objects.create(**data)
    superadmin_audit_log(request, "superadmin.tenant.create", "tenant", tenant.id, data)

    return Response(success({
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "status": tenant.status,
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
    }), status=201)


@api_view(["GET", "PUT", "DELETE"])
def superadmin_tenant_detail_view(request, tenant_id):
    """
    租户详情、更新、删除（超级管理员）
    """
    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return Response(error(ErrorCode.PARAM_INVALID, message="租户不存在"), status=404)

    if request.method == "GET":
        return Response(success({
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "status": tenant.status,
            "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
            "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
        }))

    if request.method == "DELETE":
        tenant.delete()
        superadmin_audit_log(request, "superadmin.tenant.delete", "tenant", tenant_id)
        return Response(success())

    ser = SuperAdminUpdateTenantSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    for field, value in ser.validated_data.items():
        if value is not None:
            setattr(tenant, field, value)
    tenant.save(update_fields=ser.validated_data.keys())
    superadmin_audit_log(request, "superadmin.tenant.update", "tenant", tenant_id, ser.validated_data)

    return Response(success({
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "status": tenant.status,
        "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
    }))


@api_view(["GET"])
def superadmin_audit_logs_view(request):
    """
    全局审计日志（超级管理员）
    """
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 20))
    action = request.GET.get("action", "").strip()
    actor = request.GET.get("actor", "").strip()
    tenant_id = request.GET.get("tenant_id", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    qs = AuditLog.objects.all()
    if action:
        qs = qs.filter(action__icontains=action)
    if actor:
        qs = qs.filter(actor_name__icontains=actor)
    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)
    if date_from:
        qs = qs.filter(created_at__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__lte=date_to + " 23:59:59")

    total = qs.count()
    logs = qs.order_by("-created_at")[(page - 1) * page_size : page * page_size]

    return Response(success({
        "logs": [
            {
                "id": log.id, "tenant_id": log.tenant_id,
                "tenant_name": log.tenant.name if log.tenant else None,
                "actor_id": log.actor_id,
                "actor_name": log.actor_name, "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "detail": log.detail,
                "ip_address": log.ip_address, "user_agent": log.user_agent,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            } for log in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }))


# ======================== 全局配置展示（只读） ========================


def _safe_setting(key, default="未配置"):
    return os.getenv(key, getattr(settings, key, default))


@api_view(["GET"])
def superadmin_platform_config(request):
    config_groups = [
        {
            "group": "邮件服务",
            "items": [
                {"key": "EMAIL_HOST", "value": _safe_setting("EMAIL_HOST"), "sensitive": False},
                {"key": "EMAIL_PORT", "value": _safe_setting("EMAIL_PORT", "25"), "sensitive": False},
                {"key": "EMAIL_HOST_USER", "value": _safe_setting("EMAIL_HOST_USER"), "sensitive": False},
                {"key": "EMAIL_HOST_PASSWORD", "value": "***", "sensitive": True},
                {"key": "EMAIL_USE_TLS", "value": _safe_setting("EMAIL_USE_TLS", "False"), "sensitive": False},
                {"key": "EMAIL_FROM_NAME", "value": _safe_setting("EMAIL_FROM_NAME"), "sensitive": False},
            ],
        },
        {
            "group": "短信服务",
            "items": [
                {"key": "SMS_PROVIDER", "value": os.getenv("SMS_PROVIDER", "未配置"), "sensitive": False},
                {"key": "SMS_ACCESS_KEY_ID", "value": os.getenv("SMS_ACCESS_KEY_ID", "未配置"), "sensitive": False},
                {"key": "SMS_ACCESS_KEY_SECRET", "value": "***", "sensitive": True},
                {"key": "SMS_SIGN_NAME", "value": os.getenv("SMS_SIGN_NAME", "未配置"), "sensitive": False},
                {"key": "SMS_TEMPLATE_CODE", "value": os.getenv("SMS_TEMPLATE_CODE", "未配置"), "sensitive": False},
            ],
        },
        {
            "group": "安全策略",
            "items": [
                {"key": "PASSWORD_MIN_LENGTH", "value": os.getenv("PASSWORD_MIN_LENGTH", "8"), "sensitive": False},
                {"key": "PASSWORD_MUST_HAVE_DIGIT", "value": os.getenv("PASSWORD_MUST_HAVE_DIGIT", "False"), "sensitive": False},
                {"key": "PASSWORD_MUST_HAVE_UPPER", "value": os.getenv("PASSWORD_MUST_HAVE_UPPER", "False"), "sensitive": False},
                {"key": "ACCOUNT_LOCKOUT_THRESHOLD", "value": os.getenv("ACCOUNT_LOCKOUT_THRESHOLD", "5"), "sensitive": False},
                {"key": "ACCOUNT_LOCKOUT_MINUTES", "value": os.getenv("ACCOUNT_LOCKOUT_MINUTES", "30"), "sensitive": False},
            ],
        },
        {
            "group": "Token 策略",
            "items": [
                {"key": "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "value": _safe_setting("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "120"), "sensitive": False},
                {"key": "JWT_REFRESH_TOKEN_EXPIRE_DAYS", "value": _safe_setting("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30"), "sensitive": False},
            ],
        },
        {
            "group": "限流配置",
            "items": [
                {"key": "RATE_LIMIT_IP_DEFAULT", "value": os.getenv("RATE_LIMIT_IP_DEFAULT", "60"), "sensitive": False},
                {"key": "RATE_LIMIT_APP_DEFAULT", "value": os.getenv("RATE_LIMIT_APP_DEFAULT", "1000"), "sensitive": False},
            ],
        },
    ]
    return Response(success({"configs": config_groups}))


# ======================== 超级管理员模拟租户 ========================


@api_view(["POST"])
def superadmin_impersonate(request, tenant_id):
    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return Response(error(ErrorCode.PARAM_INVALID, message="租户不存在"), status=404)

    if not getattr(request, "is_superadmin", False):
        return Response(error(ErrorCode.PERMISSION_DENIED), status=403)

    access_token = create_access_token({
        "username": request.superadmin_username,
        "is_superadmin": True,
        "tenant_id": tenant.id,
        "impersonated": True,
        "impersonated_tenant_name": tenant.name,
    })
    refresh_token = generate_refresh_token()

    from django.core.cache import cache
    cache.set(
        f"refresh_payload:{refresh_token}",
        {"username": request.superadmin_username, "is_superadmin": True,
         "tenant_id": tenant.id, "impersonated": True,
         "impersonated_tenant_name": tenant.name},
        timeout=86400,
    )

    superadmin_audit_log(request, "superadmin.impersonate", "tenant", tenant_id,
                          {"tenant_name": tenant.name})

    return Response(success({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "impersonated": True,
        "tenant_id": tenant.id,
        "tenant_name": tenant.name,
    }))


@api_view(["POST"])
def superadmin_impersonate_exit(request):
    if not getattr(request, "is_superadmin", False):
        return Response(error(ErrorCode.PERMISSION_DENIED), status=403)

    access_token = create_access_token({
        "username": request.superadmin_username,
        "is_superadmin": True,
        "tenant_id": None,
    })
    refresh_token = generate_refresh_token()

    from django.core.cache import cache
    cache.set(
        f"refresh_payload:{refresh_token}",
        {"username": request.superadmin_username, "is_superadmin": True, "tenant_id": None},
        timeout=86400,
    )

    return Response(success({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "impersonated": False,
    }))


# ======================== 组织架构管理（部门） ========================


def _department_serialize(d):
    return {
        "id": d.id, "tenant_id": d.tenant_id, "name": d.name,
        "parent_id": d.parent_id, "sort_order": d.sort_order,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@api_view(["GET", "POST"])
def departments_view(request):
    if request.method == "GET":
        depts = Department.objects.filter(tenant_id=request.tenant_id).order_by("sort_order", "name")
        return Response(success({
            "departments": [_department_serialize(d) for d in depts],
        }))

    ser = AdminDepartmentSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    data = ser.validated_data
    if Department.objects.filter(tenant_id=request.tenant_id, name=data["name"]).exists():
        return Response(error(ErrorCode.PARAM_INVALID, message="部门名称已存在"), status=400)

    parent = None
    if data.get("parent_id"):
        try:
            parent = Department.objects.get(id=data["parent_id"], tenant_id=request.tenant_id)
        except Department.DoesNotExist:
            return Response(error(ErrorCode.PARAM_INVALID, message="上级部门不存在"), status=400)

    dept = Department.objects.create(
        tenant_id=request.tenant_id,
        name=data["name"],
        parent=parent,
        sort_order=data.get("sort_order", 0),
    )
    return Response(success(_department_serialize(dept)), status=201)


@api_view(["GET", "PUT", "DELETE"])
def department_detail_view(request, dept_id):
    try:
        dept = Department.objects.get(id=dept_id, tenant_id=request.tenant_id)
    except Department.DoesNotExist:
        return Response(error(ErrorCode.PARAM_INVALID, message="部门不存在"), status=404)

    if request.method == "GET":
        return Response(success(_department_serialize(dept)))

    if request.method == "DELETE":
        if dept.children.exists():
            return Response(error(ErrorCode.PARAM_INVALID, message="该部门下有子部门，无法删除"), status=400)
        User.objects.filter(dept=dept).update(dept=None)
        dept.delete()
        return Response(success())

    ser = AdminDepartmentUpdateSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    data = ser.validated_data
    if "name" in data and data["name"]:
        dept.name = data["name"]
    if "sort_order" in data:
        dept.sort_order = data["sort_order"]
    if "parent_id" in data:
        if data["parent_id"] == dept.id:
            return Response(error(ErrorCode.PARAM_INVALID, message="部门不能将自身设为上级"), status=400)
        if data["parent_id"] is not None:
            try:
                parent = Department.objects.get(id=data["parent_id"], tenant_id=request.tenant_id)
                dept.parent = parent
            except Department.DoesNotExist:
                return Response(error(ErrorCode.PARAM_INVALID, message="上级部门不存在"), status=400)
        else:
            dept.parent = None
    dept.save()
    return Response(success(_department_serialize(dept)))


# ======================== 用户批量操作 ========================


@api_view(["POST"])
def user_batch_status_view(request):
    ser = AdminBatchUserStatusSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    data = ser.validated_data
    user_ids = data["user_ids"]
    new_status = data["status"]

    updated = User.objects.filter(id__in=user_ids, tenant_id=request.tenant_id).update(status=new_status)

    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.user.batch_status",
        resource_type="user",
        detail={"user_ids": user_ids, "new_status": new_status, "count": updated},
    )

    return Response(success({"updated_count": updated}))


@api_view(["POST"])
def user_batch_delete_view(request):
    ser = AdminBatchUserDeleteSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    user_ids = ser.validated_data["user_ids"]
    users = User.objects.filter(id__in=user_ids, tenant_id=request.tenant_id)
    count = users.count()
    users.delete()

    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.user.batch_delete",
        resource_type="user",
        detail={"user_ids": user_ids, "count": count},
    )

    return Response(success({"deleted_count": count}))


# ======================== 用户导入/导出 ========================


@api_view(["GET"])
def users_export_view(request):
    users = User.objects.filter(tenant_id=request.tenant_id).order_by("-created_at")

    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = f"attachment; filename=users_{request.tenant_id}.csv"

    writer = csv.writer(response)
    writer.writerow(["用户名", "用户类型", "昵称", "邮箱", "手机号", "部门", "状态", "创建时间"])

    status_map = {1: "正常", 0: "禁用"}
    for u in users:
        writer.writerow([
            u.username, u.get_user_type_display(), u.nickname or "",
            u.email or "", u.phone or "", u.department or "",
            status_map.get(u.status, "未知"),
            u.created_at.strftime("%Y-%m-%d %H:%M:%S") if u.created_at else "",
        ])

    return response


@api_view(["POST"])
def users_import_view(request):
    ser = AdminUserImportSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    csv_content = ser.validated_data["csv_content"]
    reader = csv.DictReader(io.StringIO(csv_content))

    created = 0
    errors = []
    for row_num, row in enumerate(reader, start=2):
        username = row.get("用户名", "").strip()
        if not username:
            errors.append({"row": row_num, "message": "用户名为空"})
            continue
        if User.objects.filter(tenant_id=request.tenant_id, username=username).exists():
            errors.append({"row": row_num, "message": f"用户名 '{username}' 已存在"})
            continue

        password = row.get("密码", "12345678")
        user = User.objects.create(
            tenant_id=request.tenant_id,
            username=username,
            user_type=row.get("用户类型", "internal"),
            nickname=row.get("昵称", "") or None,
            email=row.get("邮箱", "") or None,
            phone=row.get("手机号", "") or None,
            department=row.get("部门", "") or None,
        )
        user.set_password(password)
        user.save(update_fields=["password"])
        created += 1

    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.user.import",
        resource_type="user",
        detail={"created": created, "errors": errors},
    )

    return Response(success({
        "created": created,
        "errors": errors,
    }))


# ======================== 应用权限配置 ========================


@api_view(["GET", "PUT"])
def app_permissions_view(request, app_id):
    try:
        app = Application.objects.get(id=app_id, tenant_id=request.tenant_id)
    except Application.DoesNotExist:
        return Response(error(ErrorCode.APP_KEY_INVALID), status=404)

    if request.method == "GET":
        bindings = AppRoleBinding.objects.filter(app=app).select_related("permission")
        bound_permission_ids = [b.permission_id for b in bindings]
        return Response(success({
            "app_id": app.id,
            "permission_ids": bound_permission_ids,
        }))

    ser = AdminAppPermissionSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    permission_ids = ser.validated_data["permission_ids"]
    AppRoleBinding.objects.filter(app=app).delete()
    for pid in permission_ids:
        AppRoleBinding.objects.create(app=app, permission_id=pid)

    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.app.permissions",
        resource_type="application",
        resource_id=app_id,
        detail={"permission_ids": permission_ids},
    )

    return Response(success({
        "app_id": app.id,
        "permission_ids": permission_ids,
    }))


# ======================== 应用API调用统计 ========================

@api_view(["GET"])
def app_api_stats_view(request, app_id):
    from apps.applications.models import AppApiCallStat

    try:
        app = Application.objects.get(id=app_id, tenant_id=request.tenant_id)
    except Application.DoesNotExist:
        return Response(error(ErrorCode.APP_KEY_INVALID), status=404)

    days = request.GET.get("days", "7")
    try:
        days = max(1, min(365, int(days)))
    except ValueError:
        days = 7

    start_date = datetime.now(tz.get_current_timezone()).date() - timedelta(days=days - 1)

    stats = (
        AppApiCallStat.objects
        .filter(app=app, call_date__gte=start_date)
        .values("api_path", "call_date")
        .annotate(call_count=Count("call_count"))
        .order_by("-call_date")
    )

    daily_totals = {}
    path_totals = {}
    for s in stats:
        d = s["call_date"].isoformat() if hasattr(s["call_date"], "isoformat") else str(s["call_date"])
        daily_totals[d] = daily_totals.get(d, 0) + s["call_count"]
        path_totals[s["api_path"]] = path_totals.get(s["api_path"], 0) + s["call_count"]

    return Response(success({
        "app_id": app.id,
        "app_name": app.name,
        "period_days": days,
        "daily_totals": [{"date": d, "count": c} for d, c in sorted(daily_totals.items())],
        "path_totals": [{"api_path": p, "count": c} for p, c in sorted(path_totals.items(), key=lambda x: -x[1])],
    }))


@api_view(["GET"])
def superadmin_api_stats_view(request):
    from apps.applications.models import AppApiCallStat

    days = request.GET.get("days", "30")
    try:
        days = max(1, min(365, int(days)))
    except ValueError:
        days = 30

    start_date = datetime.now(tz.get_current_timezone()).date() - timedelta(days=days - 1)

    stats = (
        AppApiCallStat.objects
        .filter(call_date__gte=start_date)
        .values("app_id", "app__name", "api_path")
        .annotate(total_calls=Count("call_count"))
        .order_by("-total_calls")
    )

    daily_totals = (
        AppApiCallStat.objects
        .filter(call_date__gte=start_date)
        .values("call_date")
        .annotate(total_calls=Count("call_count"))
        .order_by("call_date")
    )

    return Response(success({
        "period_days": days,
        "daily_totals": [{"date": s["call_date"].isoformat() if hasattr(s["call_date"], "isoformat") else str(s["call_date"]), "count": s["total_calls"]} for s in daily_totals],
        "app_rankings": [{"app_id": s["app_id"], "app_name": s["app__name"], "api_path": s["api_path"], "total_calls": s["total_calls"]} for s in stats[:50]],
    }))



# ======================== 超管统计报表 API ========================


@api_view(["GET"])
def superadmin_tenant_growth_view(request):
    days = _parse_days(request, 30)
    start = datetime.now(tz.get_current_timezone()).date() - timedelta(days=days - 1)
    from django.db.models.functions import TruncDate
    data = (
        Tenant.objects.filter(created_at__date__gte=start)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(new_tenants=Count("id"))
        .order_by("date")
    )
    return Response(success({
        "days": days,
        "trend": [{"date": d["date"].isoformat(), "new_tenants": d["new_tenants"]} for d in data],
        "current_total": Tenant.objects.count(),
    }))


@api_view(["GET"])
def superadmin_tenant_activity_ranking_view(request):
    from django.db.models import Count
    from apps.applications.models import Application
    thirty_days_ago = datetime.now(tz.get_current_timezone()).date() - timedelta(days=30)
    tenants = Tenant.objects.annotate(
        active_users=Count("user", filter=Q(user__last_login__date__gte=thirty_days_ago)),
        total_users=Count("user"),
        app_count=Count("application"),
    ).values("id", "name", "slug", "active_users", "total_users", "app_count").order_by("-active_users")[:10]
    return Response(success({
        "rankings": [
            {
                "tenant_id": t["id"], "tenant_name": t["name"],
                "active_users": t["active_users"], "total_users": t["total_users"],
                "app_count": t["app_count"],
            }
            for t in tenants
        ],
    }))


@api_view(["GET"])
def superadmin_global_user_growth_view(request):
    days = _parse_days(request, 30)
    start = datetime.now(tz.get_current_timezone()).date() - timedelta(days=days - 1)
    from django.db.models.functions import TruncDate
    data = (
        User.objects.filter(created_at__date__gte=start)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(new_users=Count("id"))
        .order_by("date")
    )
    return Response(success({
        "days": days,
        "trend": [{"date": d["date"].isoformat(), "new_users": d["new_users"]} for d in data],
        "current_total": User.objects.count(),
    }))


@api_view(["GET"])
def superadmin_global_login_trend_view(request):
    days = _parse_days(request, 7)
    data = _login_trend_data(None, days)
    return Response(success({
        "days": days,
        "trend": [{"date": d["date"].isoformat(), "total": d["count"], "success": d["count"], "fail": 0} for d in data],
    }))


@api_view(["GET"])
def superadmin_global_login_distribution_view(request):
    qs = AuditLog.objects.filter(**_login_action_filter())
    data = qs.values("action").annotate(count=Count("id")).order_by("-count")
    labels = {"auth.login": "密码登录", "sms_login": "短信登录", "social_login": "社交登录", "superadmin.login": "超管登录"}
    total = sum(d["count"] for d in data) or 1
    items = {}
    for d in data:
        label = labels.get(d["action"], d["action"])
        items[label] = {"count": d["count"], "percentage": f"{(d['count'] / total * 100):.1f}%"}
    return Response(success({"items": items}))


@api_view(["GET"])
def superadmin_app_call_ranking_view(request):
    days = _parse_days(request, 30)
    start = datetime.now(tz.get_current_timezone()).date() - timedelta(days=days - 1)
    from apps.applications.models import AppApiCallStat
    data = (
        AppApiCallStat.objects
        .filter(call_date__gte=start)
        .values("app_id", "app__name", "api_path")
        .annotate(total_calls=Sum("call_count"))
        .order_by("-total_calls")[:10]
    )
    return Response(success({
        "period_days": days,
        "rankings": [
            {
                "app_id": s["app_id"], "app_name": s["app__name"],
                "api_path": s["api_path"],
                "total_calls": s["total_calls"],
            }
            for s in data
        ],
    }))


# ======================== 审计日志导出 ========================


@api_view(["GET"])
def audit_logs_export_view(request):
    action = request.GET.get("action", "").strip()
    actor = request.GET.get("actor", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    is_superadmin = getattr(request, "is_superadmin", False)

    if is_superadmin:
        qs = AuditLog.objects.all()
    else:
        qs = AuditLog.objects.filter(tenant_id=request.tenant_id)

    if action:
        qs = qs.filter(action__icontains=action)
    if actor:
        qs = qs.filter(actor_name__icontains=actor)
    if date_from:
        qs = qs.filter(created_at__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__lte=date_to + " 23:59:59")

    logs = qs.order_by("-created_at")

    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    tenant_slug = getattr(request, "tenant_id", "global") if not is_superadmin else "global"
    response["Content-Disposition"] = f"attachment; filename=audit_logs_{tenant_slug}.csv"

    writer = csv.writer(response)
    writer.writerow(["ID", "租户ID", "操作人", "操作类型", "资源类型", "资源ID", "详情", "IP地址", "创建时间"])

    for log in logs:
        writer.writerow([
            log.id, log.tenant_id or "", log.actor_name or "",
            log.action, log.resource_type or "", log.resource_id or "",
            json.dumps(log.detail, ensure_ascii=False) if log.detail else "",
            log.ip_address or "",
            log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "",
        ])

    return response


# ======================== 复制角色 ========================


@api_view(["POST"])
def role_copy_view(request, role_id):
    try:
        source_role = Role.objects.get(id=role_id, tenant_id=request.tenant_id)
    except Role.DoesNotExist:
        return Response(error(ErrorCode.PERMISSION_DENIED), status=404)

    ser = AdminCopyRoleSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    data = ser.validated_data
    if Role.objects.filter(tenant_id=request.tenant_id, code=data["code"]).exists():
        return Response(error(ErrorCode.PARAM_INVALID, message="角色编码已存在"), status=400)

    new_role = Role.objects.create(
        tenant_id=request.tenant_id,
        name=data["name"],
        code=data["code"],
    )

    for rp in RolePermission.objects.filter(role=source_role):
        RolePermission.objects.create(role=new_role, permission_id=rp.permission_id)

    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.role.copy",
        resource_type="role",
        resource_id=new_role.id,
        detail={"source_role_id": role_id, "name": data["name"], "code": data["code"]},
    )

    return Response(success(_role_serialize(new_role)), status=201)
