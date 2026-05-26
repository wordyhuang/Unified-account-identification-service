from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from common.response import api_response
from common.errors import ErrorCode
from common.utils import decode_access_token
from apps.accounts.models import User


PUBLIC_PATHS = [
    "/api/v1/auth/login",
    "/api/v1/auth/sms/send",
    "/api/v1/auth/sms/login",
    "/api/v1/auth/social/login",
    "/api/v1/auth/refresh",
]


class TokenAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.path.startswith("/admin/"):
            return None
        if request.path.startswith("/admin-panel/"):
            return None
        if request.method == "OPTIONS":
            return None
        if request.path in PUBLIC_PATHS:
            return None
        if request.path.startswith("/api/v1/open/"):
            return None
        if request.path.startswith("/api/v1/superadmin/"):
            return None
        if request.path.startswith("/api/v1/admin/"):
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
                from apps.users.models import UserAppAccess
                from apps.applications.models import Application
                app = Application.objects.get(id=payload["app_id"])
                has_access = UserAppAccess.objects.filter(
                    user=user, app=app, status="active"
                ).exists()
                user_type_in_default = (
                    user.user_type in (app.default_access_user_types or [])
                )
                if not has_access and not user_type_in_default:
                    return JsonResponse(
                        api_response(ErrorCode.USER_ACCESS_DENIED), status=403
                    )
        except User.DoesNotExist:
            return JsonResponse(api_response(ErrorCode.USER_NOT_FOUND), status=401)

        request.user = user
        request.user_id = user.id
        request.tenant_id = user.tenant_id
        request.app_id = payload.get("app_id")
        return None
