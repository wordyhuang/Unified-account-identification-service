from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from common.response import api_response
from common.errors import ErrorCode
from common.utils import decode_access_token
from apps.accounts.models import User


PUBLIC_PATHS = [
    "/api/v1/auth/login",
    "/api/v1/auth/sms/send",
    "/api/v1/auth/sms/verify",
    "/api/v1/auth/sms/login",
    "/api/v1/auth/social/login",
    "/api/v1/auth/wechat/login",
    "/api/v1/auth/token/refresh",
]


# 强制改密状态下仍可访问的路径（改密闭环白名单）
PASSWORD_CHANGE_ALLOWED_PATHS = (
    "/api/v1/auth/me",
    "/api/v1/auth/me/password",
    "/api/v1/auth/logout",
    "/api/v1/auth/token/refresh",
)


class TokenAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.path.startswith("/admin/"):
            return None
        if request.path.startswith("/admin-panel/"):
            return None
        if request.path.startswith("/static/"):
            return None
        if request.path == "/favicon.ico":
            return None
        if request.method == "OPTIONS":
            return None
        # 自助凭证码：公开 API 与扫码页面/短链（无登录态，码即凭证）
        if request.path.startswith("/api/v1/public/"):
            return None
        if request.path.startswith("/invite/") or request.path.startswith("/profile-completion/"):
            return None
        if request.path.startswith("/appearance-preview/"):
            return None
        if request.path.startswith("/s/"):
            return None
        for p in PUBLIC_PATHS:
            if request.path == p or request.path == p + "/":
                return None
        if request.path.startswith("/api/v1/open/"):
            return None
        if request.path.startswith("/api/v1/superadmin/"):
            return None
        if request.path.startswith("/api/v1/admin/"):
            return None
        if request.path.startswith("/oauth/"):
            return None

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JsonResponse(
                api_response(ErrorCode.TOKEN_INVALID, message="缺少 Token"),
                status=401,
            )

        token = auth_header[7:]
        payload = decode_access_token(token)
        if payload is None:
            return JsonResponse(api_response(ErrorCode.TOKEN_EXPIRED), status=401)

        try:
            user = User.objects.get(id=payload["user_id"], status=1)
            if payload.get("app_id"):
                from apps.applications.models import Application
                from apps.users.access import evaluate_app_access

                app = Application.objects.filter(
                    id=payload["app_id"], status=True
                ).first()
                if app is None:
                    return JsonResponse(
                        api_response(ErrorCode.APP_KEY_INVALID, message="应用不存在或已停用"),
                        status=403,
                    )
                allowed, _reason, _group_id = evaluate_app_access(user, app)
                if not allowed:
                    return JsonResponse(
                        api_response(ErrorCode.USER_ACCESS_DENIED), status=403
                    )
        except User.DoesNotExist:
            return JsonResponse(
                api_response(ErrorCode.USER_NOT_FOUND), status=401
            )

        request.user = user
        request.user_id = user.id
        request.tenant_id = user.tenant_id
        request.app_id = payload.get("app_id")

        # 强制改密全量拦截：密码被管理员重置后，仅放行改密闭环白名单路径
        # 以数据库实时值为准，改密成功清除标志后立即放行
        if getattr(user, "must_change_password", False):
            if request.path.rstrip("/") not in PASSWORD_CHANGE_ALLOWED_PATHS:
                return JsonResponse(
                    api_response(ErrorCode.PASSWORD_CHANGE_REQUIRED),
                    status=403,
                )
        return None
