from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from common.response import api_response
from common.errors import ErrorCode
from common.utils import decode_access_token
from apps.accounts.models import User


class AdminAuthenticationMiddleware(MiddlewareMixin):
    ADMIN_API_PREFIX = "/api/v1/admin/"
    SUPERADMIN_API_PREFIX = "/api/v1/superadmin/"
    ADMIN_PAGE_PREFIX = "/admin-panel/"

    def process_request(self, request):
        path = request.path
        is_admin_api = path.startswith(self.ADMIN_API_PREFIX)
        is_superadmin_api = path.startswith(self.SUPERADMIN_API_PREFIX)
        is_page = path.startswith(self.ADMIN_PAGE_PREFIX)
        is_api = is_admin_api or is_superadmin_api

        if not is_api and not is_page:
            return None
        if request.method == "OPTIONS":
            return None
        if is_page and path == self.ADMIN_PAGE_PREFIX.rstrip("/"):
            return None

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            if is_page:
                return None
            return JsonResponse(
                api_response(ErrorCode.TOKEN_INVALID, message="缺少 Token"),
                status=401,
            )

        token = auth_header[7:]
        payload = decode_access_token(token)
        if payload is None:
            if is_page:
                return None
            return JsonResponse(api_response(ErrorCode.TOKEN_EXPIRED), status=401)

        if payload.get("is_superadmin"):
            request.is_superadmin = True
            request.superadmin_username = payload.get("username")
            is_impersonated = payload.get("impersonated")
            
            if is_impersonated:
                if is_superadmin_api and not path.startswith("/api/v1/superadmin/impersonate/exit"):
                    return JsonResponse(
                        api_response(ErrorCode.PERMISSION_DENIED, message="模拟模式下禁止访问超级管理员API"),
                        status=403,
                    )
                request.tenant_id = payload.get("tenant_id")
                class _ImpersonatedUser:
                    username = payload.get("username", "superadmin")
                    id = None
                    is_authenticated = True
                request.user = _ImpersonatedUser()
                request.user_id = None
            else:
                request.tenant_id = None
                request.user = None
                request.user_id = None
            return None

        try:
            user = User.objects.get(id=payload["user_id"], status=1)
        except User.DoesNotExist:
            if is_page:
                return None
            return JsonResponse(api_response(ErrorCode.USER_NOT_FOUND), status=401)

        if is_superadmin_api:
            return JsonResponse(
                api_response(ErrorCode.PERMISSION_DENIED, message="仅超级管理员可访问"),
                status=403,
            )

        if is_admin_api and not user.is_superuser and not user.is_staff:
            return JsonResponse(
                api_response(ErrorCode.PERMISSION_DENIED, message="仅管理员可访问"),
                status=403,
            )

        request.is_superadmin = False
        request.user = user
        request.user_id = user.id
        request.tenant_id = user.tenant_id
        return None
