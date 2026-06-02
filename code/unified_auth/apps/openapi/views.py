import logging
import requests

from rest_framework.decorators import api_view
from rest_framework.response import Response
from common.response import success, error
from common.errors import ErrorCode
from common.utils import decode_access_token
from apps.accounts.models import User, Department, UserProfile
from apps.accounts.serializers import UserInfoSerializer
from apps.applications.models import Application
from apps.rbac.models import UserRole, RolePermission, Role
from .serializers import (
    VerifyTokenSerializer, CreateUserSerializer, UpdateUserSerializer,
    StatusUpdateSerializer, CheckPermissionSerializer,
    WeChatPhoneSerializer, WeChatTokenSerializer,
    ProfileByTokenSerializer, UpdateProfileByTokenSerializer,
)

logger = logging.getLogger(__name__)


@api_view(["POST"])
def verify_token(request):
    ser = VerifyTokenSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    payload = decode_access_token(ser.validated_data["token"])
    if payload is None:
        return Response(success({
            "valid": False,
            "user_id": None,
            "tenant_id": None,
            "user_type": None,
        }))

    return Response(success({
        "valid": True,
        "user_id": payload["user_id"],
        "tenant_id": payload["tenant_id"],
        "user_type": payload.get("user_type"),
    }))


@api_view(["GET", "POST"])
def users_view(request):
    if request.method == "GET":
        users = User.objects.filter(tenant_id=request.tenant_id)
        ser = UserInfoSerializer(users, many=True)
        return Response(success({"users": ser.data, "total": users.count()}))

    ser = CreateUserSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    data = ser.validated_data
    if User.objects.filter(tenant_id=request.tenant_id, username=data["username"]).exists():
        return Response(
            error(ErrorCode.PARAM_INVALID, message="用户名已存在"), status=400
        )

    dept_code = data.get("dept_code")
    dept_id = None
    if dept_code:
        dept = Department.objects.filter(code=dept_code, tenant_id=request.tenant_id).first()
        if not dept:
            return Response(
                error(ErrorCode.PARAM_INVALID, message="指定的部门编码不存在"), status=400
            )
        dept_id = dept.id

    role_codes = data.get("role_codes", [])
    roles = []
    if role_codes:
        roles = list(Role.objects.filter(code__in=role_codes, tenant_id=request.tenant_id))
        if len(roles) != len(role_codes):
            invalid_codes = set(role_codes) - set(r.code for r in roles)
            return Response(
                error(ErrorCode.PARAM_INVALID, message=f"角色编码不存在: {', '.join(invalid_codes)}"), status=400
            )

    user = User.objects.create(
        tenant_id=request.tenant_id,
        user_type=data["user_type"],
        username=data["username"],
        email=data.get("email"),
        phone=data.get("phone"),
        nickname=data.get("nickname"),
        department=data.get("department"),
        dept_id=dept_id,
    )
    user.set_password(data["password"])
    user.save(update_fields=["password"])

    for role in roles:
        UserRole.objects.create(user=user, role=role)

    ser = UserInfoSerializer(user)
    return Response(success(ser.data), status=201)


@api_view(["GET", "PUT"])
def user_detail_view(request, user_id):
    try:
        user = User.objects.get(id=user_id, tenant_id=request.tenant_id)
    except User.DoesNotExist:
        return Response(error(ErrorCode.USER_NOT_FOUND), status=404)

    if request.method == "GET":
        ser = UserInfoSerializer(user)
        return Response(success(ser.data))

    ser = UpdateUserSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    data = ser.validated_data

    dept_code = data.get("dept_code")
    if dept_code is not None:
        if dept_code == "":
            user.dept_id = None
        else:
            dept = Department.objects.filter(code=dept_code, tenant_id=request.tenant_id).first()
            if not dept:
                return Response(
                    error(ErrorCode.PARAM_INVALID, message="指定的部门编码不存在"), status=400
                )
            user.dept_id = dept.id

    if "role_codes" in data:
        role_codes = data.get("role_codes") or []
        roles = []
        if role_codes:
            roles = list(Role.objects.filter(code__in=role_codes, tenant_id=request.tenant_id))
            if len(roles) != len(role_codes):
                invalid_codes = set(role_codes) - set(r.code for r in roles)
                return Response(
                    error(ErrorCode.PARAM_INVALID, message=f"角色编码不存在: {', '.join(invalid_codes)}"), status=400
                )
        UserRole.objects.filter(user=user).delete()
        for role in roles:
            UserRole.objects.create(user=user, role=role)

    phone = data.get("phone")
    if phone is not None:
        if User.objects.filter(
            tenant_id=request.tenant_id,
            phone=phone,
        ).exclude(id=user.id).exists():
            return Response(error(ErrorCode.PARAM_INVALID, message="手机号已被占用"), status=400)

    update_fields = []
    for field in ["nickname", "email", "phone", "avatar", "department"]:
        if field in data and data[field] is not None:
            setattr(user, field, data[field])
            update_fields.append(field)

    if dept_code is not None:
        update_fields.append("dept_id")

    if update_fields:
        user.save(update_fields=update_fields)

    return Response(success({"user_id": user.id}))


@api_view(["PATCH"])
def update_user_status(request, user_id):
    try:
        user = User.objects.get(id=user_id, tenant_id=request.tenant_id)
    except User.DoesNotExist:
        return Response(error(ErrorCode.USER_NOT_FOUND), status=404)

    ser = StatusUpdateSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    user.status = ser.validated_data["status"]
    user.save(update_fields=["status"])
    return Response(success({
        "user_id": user.id, "user_uuid": str(user.uuid), "status": user.status
    }))


@api_view(["POST"])
def check_permission(request):
    ser = CheckPermissionSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    data = ser.validated_data
    try:
        user = User.objects.get(id=data["user_id"], tenant_id=request.tenant_id)
    except User.DoesNotExist:
        return Response(error(ErrorCode.USER_NOT_FOUND), status=404)

    has_perm = UserRole.objects.filter(
        user=user,
        role__permissions__code=data["permission_code"],
    ).exists()

    return Response(success({
        "user_id": user.id,
        "user_uuid": str(user.uuid),
        "permission_code": data["permission_code"],
        "has_permission": has_perm,
    }))


@api_view(["GET", "PUT"])
def user_profile_by_token(request):
    """通过用户Token获取/修改用户资料

    GET  权限码: user:profile:read
    PUT  权限码: user:profile:update
    认证方式: AppKey + Signature（由中间件自动处理）

    GET 请求 token 参数可放在 query string 或 request body 中
    PUT 请求 token 及更新字段放在 request body 中
    """
    if request.method == "GET":
        data = request.query_params.dict() if request.query_params else (request.data or {})
        ser = ProfileByTokenSerializer(data=data)
    else:
        ser = UpdateProfileByTokenSerializer(data=request.data)

    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    payload = decode_access_token(ser.validated_data["user_token"])
    if payload is None:
        return Response(error(ErrorCode.TOKEN_INVALID), status=401)

    user_id = payload.get("user_id")
    if not user_id:
        return Response(error(ErrorCode.TOKEN_INVALID), status=401)

    try:
        from apps.accounts.models import User as UserModel
        user = UserModel.objects.get(id=user_id, status=1)
    except UserModel.DoesNotExist:
        return Response(error(ErrorCode.USER_NOT_FOUND), status=404)

    profile, created = UserProfile.objects.get_or_create(user=user)

    if request.method == "GET":
        from datetime import date as date_type
        return Response(success({
            "user_id": user.id, "username": user.username, "nickname": user.nickname,
            "avatar": profile.avatar, "real_name": profile.real_name,
            "gender": profile.gender,
            "birthday": profile.birthday.isoformat() if profile.birthday else None,
            "id_card": profile.id_card, "nationality": profile.nationality,
            "address": profile.address, "zip_code": profile.zip_code,
            "emergency_contact": profile.emergency_contact,
            "emergency_phone": profile.emergency_phone,
            "job_title": profile.job_title, "employee_id": profile.employee_id,
            "hire_date": profile.hire_date.isoformat() if profile.hire_date else None,
            "work_email": profile.work_email, "work_phone": profile.work_phone,
            "wechat": profile.wechat, "qq": profile.qq, "weibo": profile.weibo,
            "bio": profile.bio, "interests": profile.interests,
            "tags": profile.tags, "extra_data": profile.extra_data,
        }))

    data = ser.validated_data
    fields = [
        "avatar", "real_name", "gender", "birthday", "id_card", "nationality",
        "address", "zip_code", "emergency_contact", "emergency_phone",
        "job_title", "employee_id", "hire_date", "work_email", "work_phone",
        "wechat", "qq", "weibo", "bio", "interests", "tags", "extra_data",
    ]
    update_fields = []
    for field in fields:
        if field in data:
            setattr(profile, field, data[field])
            update_fields.append(field)

    if update_fields:
        profile.save(update_fields=update_fields)

    return Response(success({"profile_id": profile.id}))


# ================== 微信小程序辅助接口 ==================

WECHAT_ACCESS_TOKEN_CACHE_PREFIX = "wechat:access_token:"


def _get_cached_access_token(app_id):
    """从缓存获取 access_token"""
    from django.core.cache import cache
    return cache.get(WECHAT_ACCESS_TOKEN_CACHE_PREFIX + app_id)


def _set_cached_access_token(app_id, token):
    """缓存 access_token，有效期7000秒（微信官方7200秒）"""
    from django.core.cache import cache
    cache.set(WECHAT_ACCESS_TOKEN_CACHE_PREFIX + app_id, token, timeout=7000)


def _fetch_access_token_from_wechat(app_id, app_secret):
    """调用微信接口获取 access_token"""
    url = (
        f"https://api.weixin.qq.com/cgi-bin/token"
        f"?grant_type=client_credential&appid={app_id}&secret={app_secret}"
    )
    resp = requests.get(url, timeout=10)
    data = resp.json()
    if "access_token" in data:
        return data["access_token"]
    logger.error("微信获取access_token失败: %s, app_id=%s", data, app_id)
    return None


def _get_app_wechat_config(app_key, tenant_id, app_id=None):
    """根据 app_key 和 app_id 查找微信小程序配置"""
    app = Application.objects.filter(
        app_key=app_key, tenant_id=tenant_id, status=True
    ).first()
    if not app:
        return None, ErrorCode.APP_KEY_INVALID

    if not app.wechat_mp_app_id or not app.wechat_mp_app_secret:
        return None, ErrorCode.WECHAT_NOT_CONFIGURED

    if app_id and app_id != app.wechat_mp_app_id:
        return None, ErrorCode.PARAM_INVALID

    return app, None


@api_view(["GET"])
def get_access_token(request):
    """获取微信小程序 access_token（自动缓存）

    权限码: wechat:access_token
    认证方式: AppKey + Signature（由中间件自动处理）
    """
    app_key = getattr(request, "app_key", None) or request.headers.get("X-App-Key")
    tenant_id = getattr(request, "tenant_id", None)

    app, err = _get_app_wechat_config(app_key, tenant_id)
    if err:
        return Response(error(err), status=400 if err == ErrorCode.PARAM_INVALID else 401)

    cached = _get_cached_access_token(app.wechat_mp_app_id)
    if cached:
        return Response(success({
            "access_token": cached,
            "source": "cache",
            "app_id": app.wechat_mp_app_id,
        }))

    token = _fetch_access_token_from_wechat(app.wechat_mp_app_id, app.wechat_mp_app_secret)
    if not token:
        return Response(error(ErrorCode.WECHAT_API_ERROR), status=502)

    _set_cached_access_token(app.wechat_mp_app_id, token)

    return Response(success({
        "access_token": token,
        "source": "wechat",
        "app_id": app.wechat_mp_app_id,
    }))


@api_view(["POST"])
def get_phone_number(request):
    """通过微信小程序 code 获取用户手机号

    权限码: wechat:phone
    认证方式: AppKey + Signature（由中间件自动处理）
    """
    ser = WeChatPhoneSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    code = ser.validated_data["code"]
    app_key = getattr(request, "app_key", None) or request.headers.get("X-App-Key")
    tenant_id = getattr(request, "tenant_id", None)

    app, err = _get_app_wechat_config(app_key, tenant_id)
    if err:
        return Response(error(err), status=400 if err == ErrorCode.PARAM_INVALID else 401)

    access_token = _get_cached_access_token(app.wechat_mp_app_id)
    if not access_token:
        access_token = _fetch_access_token_from_wechat(
            app.wechat_mp_app_id, app.wechat_mp_app_secret
        )
        if not access_token:
            return Response(error(ErrorCode.WECHAT_API_ERROR), status=502)
        _set_cached_access_token(app.wechat_mp_app_id, access_token)

    url = f"https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token={access_token}"
    resp = requests.post(url, json={"code": code}, timeout=10)
    data = resp.json()

    if data.get("errcode") != 0:
        logger.error("微信获取手机号失败: %s", data)
        return Response(error(ErrorCode.WECHAT_API_ERROR, message=data.get("errmsg", "微信接口调用失败")), status=502)

    phone_info = data.get("phone_info", {})
    return Response(success({
        "phone_number": phone_info.get("phoneNumber", ""),
        "country_code": phone_info.get("countryCode", ""),
        "pure_phone_number": phone_info.get("purePhoneNumber", ""),
    }))
