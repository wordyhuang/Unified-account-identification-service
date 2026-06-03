from django.conf import settings
from django.utils import timezone
from django.db import transaction
from rest_framework.decorators import api_view
from rest_framework.response import Response
from common.response import success, error
from common.errors import ErrorCode
from common.utils import create_access_token, generate_refresh_token, is_superadmin_credentials
from services.sms_service import send_sms, generate_code
from apps.applications.models import Application
from .models import Tenant, User, SocialAccount, UserProfile
from apps.audit.models import AuditLog
from .serializers import (
    LoginSerializer, SmsSendSerializer, SmsLoginSerializer,
    SocialLoginSerializer, RefreshSerializer, UserInfoSerializer,
    UpdateUserInfoSerializer, ChangePasswordSerializer,
    UserProfileSerializer, UpdateUserProfileSerializer,
)


@api_view(["POST"])
def login(request):
    ser = LoginSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    username = ser.validated_data["username"]
    password = ser.validated_data["password"]

    ip_address = request.META.get('REMOTE_ADDR', '')
    user_agent = request.META.get('HTTP_USER_AGENT', '')

    superadmin = is_superadmin_credentials(username, password)
    if superadmin:
        access_token = create_access_token({
            "username": username,
            "is_superadmin": True,
            "tenant_id": None,
        })
        refresh_token = generate_refresh_token()

        from django.core.cache import cache
        cache.set(
            f"refresh_payload:{refresh_token}",
            {"username": username, "is_superadmin": True, "tenant_id": None},
            timeout=86400,
        )

        try:
            AuditLog.objects.create(
                tenant=None,
                actor_name=username,
                action="superadmin.login",
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except Exception:
            pass

        return Response(success({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "username": username,
            "is_superadmin": True,
            "is_superuser": True,
            "is_staff": True,
        }))

    user = User.objects.filter(username=username).first()
    if user is None:
        return Response(error(ErrorCode.USER_NOT_FOUND), status=404)
    if user.status == 0:
        return Response(error(ErrorCode.USER_DISABLED), status=403)
    if not user.check_password(password):
        return Response(error(ErrorCode.PARAM_INVALID, message="密码错误"), status=400)

    user.last_login_at = timezone.now()
    user.save(update_fields=["last_login_at"])

    access_token = create_access_token({
        "user_id": user.id,
        "tenant_id": user.tenant_id,
        "user_type": user.user_type,
    })
    refresh_token = generate_refresh_token()

    from django.core.cache import cache
    cache.set(
        f"refresh_payload:{refresh_token}",
        {"user_id": user.id, "tenant_id": user.tenant_id, "user_type": user.user_type},
        timeout=86400,
    )

    return Response(success({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "user_type": user.user_type,
        "is_superuser": user.is_superuser,
        "is_staff": user.is_staff,
    }))


@api_view(["POST"])
def sms_send(request):
    ser = SmsSendSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    phone = ser.validated_data["phone"]
    ip = request.META.get('REMOTE_ADDR', '')

    from django.core.cache import cache

    # ---- 同一手机号冷却期检查（默认60秒内不可重复发送） ----
    phone_cooldown_key = f"sms:rate:phone:{phone}"
    if cache.get(phone_cooldown_key):
        return Response(
            error(ErrorCode.RATE_LIMIT_EXCEEDED, message="短信发送太频繁，请稍后再试"),
            status=429,
        )

    # ---- 同一手机号每日上限检查 ----
    phone_daily_key = f"sms:daily:phone:{phone}:{timezone.now().strftime('%Y%m%d')}"
    phone_daily_count = cache.get(phone_daily_key) or 0
    daily_limit = getattr(settings, 'SMS_PHONE_DAILY_LIMIT', 5)
    if phone_daily_count >= daily_limit:
        return Response(
            error(ErrorCode.RATE_LIMIT_EXCEEDED, message="该手机号今日短信发送次数已达上限"),
            status=429,
        )

    # ---- 同一IP短信专用限频 ----
    ip_rate_key = f"sms:rate:ip:{ip}"
    ip_max_per_minute = getattr(settings, 'SMS_IP_RATE_PER_MINUTE', 10)

    # 用列表结构 + TTL 实现滑动窗口
    ip_records = cache.get(ip_rate_key) or []
    now = timezone.now().timestamp()
    ip_records = [t for t in ip_records if now - t < 60]
    if len(ip_records) >= ip_max_per_minute:
        return Response(
            error(ErrorCode.RATE_LIMIT_EXCEEDED, message="IP请求太频繁，请稍后再试"),
            status=429,
        )

    code = generate_code()

    tenant = None
    app_key = ser.validated_data.get("app_key")
    if app_key:
        app = Application.objects.filter(app_key=app_key, status=True).first()
        if app:
            tenant = Tenant.objects.filter(id=app.tenant_id).first()

    ok, msg = send_sms(phone, code, tenant=tenant)
    if not ok:
        return Response(
            error(ErrorCode.SMS_SEND_FAILED, message=msg),
            status=500,
        )

    # 发送成功后才更新限频计数器
    cooldown_sec = getattr(settings, 'SMS_PHONE_COOLDOWN_SECONDS', 60)
    cache.set(phone_cooldown_key, 1, timeout=cooldown_sec)
    cache.set(phone_daily_key, phone_daily_count + 1, timeout=86400)
    ip_records.append(now)
    cache.set(ip_rate_key, ip_records, timeout=60)

    cache.set(f"sms:{phone}", code, timeout=300)

    return Response(success({"phone": phone}))


@api_view(["POST"])
def sms_login(request):
    ser = SmsLoginSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    phone = ser.validated_data["phone"]
    code = ser.validated_data["code"]

    from django.core.cache import cache
    cached = cache.get(f"sms:{phone}")
    if cached is None:
        return Response(error(ErrorCode.SMS_CODE_EXPIRED), status=400)
    if cached != code:
        return Response(error(ErrorCode.SMS_CODE_INVALID), status=400)

    cache.delete(f"sms:{phone}")

    tenant = Tenant.objects.first()
    user, created = User.objects.get_or_create(
        tenant=tenant,
        phone=phone,
        defaults={
            "username": phone,
            "user_type": "external",
            "nickname": f"用户{phone[-4:]}",
        },
    )
    if user.status == 0:
        return Response(error(ErrorCode.USER_DISABLED), status=403)

    user.last_login_at = timezone.now()
    user.save(update_fields=["last_login_at"])

    access_token = create_access_token({
        "user_id": user.id,
        "tenant_id": user.tenant_id,
        "user_type": user.user_type,
    })
    refresh_token = generate_refresh_token()

    from django.core.cache import cache
    cache.set(
        f"refresh_payload:{refresh_token}",
        {"user_id": user.id, "tenant_id": user.tenant_id, "user_type": user.user_type},
        timeout=86400,
    )

    return Response(success({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_id": user.id,
        "is_new": created,
    }))


@api_view(["POST"])
def social_login(request):
    ser = SocialLoginSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    provider = ser.validated_data["provider"]
    code = ser.validated_data["code"]
    app_key = ser.validated_data.get("app_key")

    app_wechat_config = {}
    mock_mode = False
    if provider in ("wechat_mp", "wechat_web"):
        if not app_key:
            if not getattr(settings, 'MOCK_ENABLED', False):
                return Response(error(ErrorCode.WECHAT_NOT_CONFIGURED), status=400)
            mock_mode = True
        else:
            app = Application.objects.filter(app_key=app_key, status=True).first()
            if not app:
                return Response(error(ErrorCode.APP_KEY_INVALID), status=400)
            if provider == "wechat_mp":
                if app.wechat_mp_app_id and app.wechat_mp_app_secret:
                    app_wechat_config = {
                        "app_id": app.wechat_mp_app_id,
                        "app_secret": app.wechat_mp_app_secret,
                    }
                elif not getattr(settings, 'MOCK_ENABLED', False):
                    return Response(error(ErrorCode.WECHAT_NOT_CONFIGURED), status=400)
                else:
                    mock_mode = True
            elif provider == "wechat_web":
                if app.wechat_web_app_id and app.wechat_web_app_secret:
                    app_wechat_config = {
                        "app_id": app.wechat_web_app_id,
                        "app_secret": app.wechat_web_app_secret,
                    }
                elif not getattr(settings, 'MOCK_ENABLED', False):
                    return Response(error(ErrorCode.WECHAT_NOT_CONFIGURED), status=400)
                else:
                    mock_mode = True

    if mock_mode:
        open_id = f"mock_{provider}_{code[:8]}"
        union_id = None
    elif app_wechat_config:
        try:
            open_id, union_id = _exchange_wechat_code(provider, code, app_wechat_config)
        except ValueError as e:
            return Response(error(ErrorCode.WECHAT_API_ERROR, data={"detail": str(e)}), status=400)

    with transaction.atomic():
        social = SocialAccount.objects.filter(
            provider=provider, open_id=open_id
        ).first()

        if social:
            created = False
            user = social.user
            if user.status == 0:
                return Response(error(ErrorCode.USER_DISABLED), status=403)
        else:
            created = True
            tenant = Tenant.objects.first()
            user = User.objects.create(
                tenant=tenant,
                username=f"{provider}_{open_id[-8:]}",
                user_type="external",
                nickname=f"用户({provider})",
            )
            social = SocialAccount.objects.create(
                user=user,
                provider=provider,
                open_id=open_id,
                union_id=union_id,
                extra_data={"code": code, "app_key": app_key},
            )

    user.last_login_at = timezone.now()
    user.save(update_fields=["last_login_at"])

    access_token = create_access_token({
        "user_id": user.id,
        "tenant_id": user.tenant_id,
        "user_type": user.user_type,
    })
    refresh_token = generate_refresh_token()

    from django.core.cache import cache
    cache.set(
        f"refresh_payload:{refresh_token}",
        {"user_id": user.id, "tenant_id": user.tenant_id, "user_type": user.user_type},
        timeout=86400,
    )

    return Response(success({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_id": user.id,
        "is_new": created,
    }))


def _exchange_wechat_code(provider, code, config):
    """
    通过微信授权码换取 open_id / union_id
    支持微信小程序(wechat_mp)和微信网页(wechat_web)
    使用应用自定义的 AppID/AppSecret
    """
    import requests as http_requests

    app_id = config["app_id"]
    app_secret = config["app_secret"]

    if provider == "wechat_mp":
        url = (
            f"https://api.weixin.qq.com/sns/jscode2session"
            f"?appid={app_id}&secret={app_secret}&js_code={code}&grant_type=authorization_code"
        )
    else:
        url = (
            f"https://api.weixin.qq.com/sns/oauth2/access_token"
            f"?appid={app_id}&secret={app_secret}&code={code}&grant_type=authorization_code"
        )

    try:
        resp = http_requests.get(url, timeout=10)
        data = resp.json()
        if "errcode" in data and data["errcode"] != 0:
            errcode = data["errcode"]
            errmsg = data.get("errmsg", "微信API返回错误")
            import logging
            logging.getLogger(__name__).error(
                "微信登录API错误: errcode=%s, errmsg=%s", errcode, errmsg
            )
            if errcode in (40029, 40125):
                raise ValueError(f"无效的微信授权码: {errmsg}")
            raise ValueError(f"微信API返回错误: {errmsg}")
        open_id = data.get("openid")
        if not open_id:
            raise ValueError("微信API响应中未找到openid")
        union_id = data.get("unionid")
        return open_id, union_id
    except ValueError:
        raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("微信登录接口调用失败: %s", str(e))
        raise ValueError(f"微信登录接口调用失败: {str(e)}")


@api_view(["POST"])
def refresh(request):
    ser = RefreshSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID), status=400)

    refresh_token = ser.validated_data["refresh_token"]
    if len(refresh_token) < 32:
        return Response(error(ErrorCode.TOKEN_INVALID), status=401)

    from django.core.cache import cache
    cache_key = f"refresh:{refresh_token}"

    if cache.get(cache_key) == "used":
        return Response(error(ErrorCode.TOKEN_INVALID), status=401)

    user_payload = cache.get(f"refresh_payload:{refresh_token}")
    if not user_payload:
        return Response(error(ErrorCode.TOKEN_INVALID), status=401)

    cache.set(cache_key, "used", timeout=86400)
    cache.delete(f"refresh_payload:{refresh_token}")

    if user_payload.get("is_superadmin"):
        return Response(success({
            "access_token": create_access_token({
                "username": user_payload["username"],
                "is_superadmin": True,
                "tenant_id": None,
            }),
            "refresh_token": generate_refresh_token(),
        }))

    return Response(success({
        "access_token": create_access_token({
            "user_id": user_payload["user_id"],
            "tenant_id": user_payload["tenant_id"],
            "user_type": user_payload["user_type"],
        }),
        "refresh_token": generate_refresh_token(),
    }))


@api_view(["POST"])
def logout(request):
    return Response(success())


@api_view(["GET", "PUT"])
def userinfo(request):
    if request.method == "GET":
        ser = UserInfoSerializer(request.user)
        return Response(success(ser.data))

    ser = UpdateUserInfoSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    phone = ser.validated_data.get("phone")
    if phone is not None:
        if User.objects.filter(
            tenant_id=request.user.tenant_id,
            phone=phone,
        ).exclude(id=request.user.id).exists():
            return Response(error(ErrorCode.PARAM_INVALID, message="手机号已被占用"), status=400)

    for field, value in ser.validated_data.items():
        setattr(request.user, field, value)
    request.user.save(update_fields=ser.validated_data.keys())

    return Response(success({"user_id": request.user.id}))


@api_view(["PATCH"])
def change_password(request):
    ser = ChangePasswordSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    if not request.user.check_password(ser.validated_data["old_password"]):
        return Response(error(ErrorCode.PARAM_INVALID, message="原密码错误"), status=400)

    request.user.set_password(ser.validated_data["new_password"])
    request.user.save(update_fields=["password"])
    return Response(success())


@api_view(["GET"])
def profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    ser = UserProfileSerializer(profile)
    return Response(success(ser.data))


@api_view(["PUT"])
def update_profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    ser = UpdateUserProfileSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    for field, value in ser.validated_data.items():
        setattr(profile, field, value)
    profile.save(update_fields=ser.validated_data.keys())

    return Response(success({"profile_id": profile.id}))
