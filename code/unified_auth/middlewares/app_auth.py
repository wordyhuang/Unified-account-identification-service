import time
from datetime import date
from django.http import JsonResponse
from django.db.models import F
from django.utils.deprecation import MiddlewareMixin
from common.response import api_response
from common.errors import ErrorCode
from common.utils import verify_signature, decode_access_token
from apps.applications.models import Application, AppApiCallStat


class AppAuthenticationMiddleware(MiddlewareMixin):
    def _validate_url_access_token(self, request):
        """验证 URL 中的 access_token，适用于 /api/v1/auth/* 路径"""
        access_token = request.GET.get("access_token")
        if not access_token:
            return None, JsonResponse(
                api_response(ErrorCode.APP_KEY_INVALID, message="缺少 access_token（请通过 URL 参数 ?access_token= 传递）"),
                status=401,
            )
        payload = decode_access_token(access_token)
        if payload is None:
            return None, JsonResponse(
                api_response(ErrorCode.TOKEN_EXPIRED, message="应用Token无效或已过期"),
                status=401,
            )
        if payload.get("token_type") != "app":
            return None, JsonResponse(
                api_response(ErrorCode.TOKEN_INVALID, message="非应用Token"),
                status=401,
            )
        try:
            app = Application.objects.get(id=payload["app_id"], status=True)
        except Application.DoesNotExist:
            return None, JsonResponse(api_response(ErrorCode.APP_KEY_INVALID), status=401)
        return app, None

    def process_request(self, request):
        is_open_path = request.path.startswith("/api/v1/open/")
        is_auth_path = request.path.startswith("/api/v1/auth/")

        if not (is_open_path or is_auth_path):
            return None
        if request.method == "OPTIONS":
            return None

        # --- /api/v1/auth/* 路径：仅验证 URL access_token（AppKey+Signature 仅用于开放API） ---
        # refresh token 端点不需要 access_token
        if is_auth_path:
            if request.path == "/api/v1/auth/token/refresh" or request.path == "/api/v1/auth/token/refresh/":
                return None
            app, error_response = self._validate_url_access_token(request)
            if error_response:
                return error_response
            request.app = app
            request.app_key = app.app_key
            request.tenant_id = app.tenant_id
            self._record_api_call(request, app)
            return None

        # --- /api/v1/open/* 路径（原逻辑） ---

        # /api/v1/open/token 接口使用 AppKey+Secret 换取 Token，无需中间件认证
        if request.path == "/api/v1/open/token" or request.path == "/api/v1/open/token/":
            return None

        # 认证方式1：AppKey + Signature 认证
        app_key = request.headers.get("X-App-Key")
        timestamp = request.headers.get("X-Timestamp")
        signature = request.headers.get("X-Signature")

        if all([app_key, timestamp, signature]):
            now = time.time()
            if abs(now - int(timestamp)) > 300:
                return JsonResponse(
                    api_response(ErrorCode.SIGNATURE_INVALID, message="请求已过期"),
                    status=401,
                )

            try:
                app = Application.objects.get(app_key=app_key, status=True)
            except Application.DoesNotExist:
                return JsonResponse(api_response(ErrorCode.APP_KEY_INVALID), status=401)

            request_params = {}
            if request.method in ("POST", "PUT", "PATCH"):
                try:
                    request_params = request.data.copy() if hasattr(request, 'data') else {}
                except Exception:
                    pass

            query_params = request.GET.dict()
            if query_params:
                request_params.update(query_params)

            if verify_signature(app.app_secret, request_params, timestamp, signature):
                pass
            elif verify_signature(app.app_secret, {}, timestamp, signature):
                pass
            else:
                return JsonResponse(api_response(ErrorCode.SIGNATURE_INVALID), status=401)

            request.app = app
            request.app_key = app_key
            request.tenant_id = app.tenant_id
            self._record_api_call(request, app)
            return None

        # 认证方式2：URL Access Token 认证（access_token 在 URL query 中传递）
        # 仅当未使用 Signature 认证时才尝试此方式，避免与端点参数冲突
        access_token = request.GET.get("access_token")
        if access_token:
            payload = decode_access_token(access_token)
            if payload is None:
                return JsonResponse(
                    api_response(ErrorCode.TOKEN_EXPIRED, message="应用Token无效或已过期"),
                    status=401,
                )
            if payload.get("token_type") != "app":
                return JsonResponse(
                    api_response(ErrorCode.TOKEN_INVALID, message="非应用Token"),
                    status=401,
                )
            try:
                app = Application.objects.get(id=payload["app_id"], status=True)
            except Application.DoesNotExist:
                return JsonResponse(api_response(ErrorCode.APP_KEY_INVALID), status=401)
            request.app = app
            request.app_key = app.app_key
            request.tenant_id = app.tenant_id
            self._record_api_call(request, app)
            return None

        # 两种认证方式均未提供
        return JsonResponse(
            api_response(ErrorCode.APP_KEY_INVALID, message="缺少认证参数（需要 AppKey+Signature 或 URL access_token）"),
            status=401,
        )

    def _record_api_call(self, request, app):
        try:
            today = date.today()
            affected = AppApiCallStat.objects.filter(
                app=app, api_path=request.path, call_date=today
            ).update(call_count=F("call_count") + 1)
            if affected == 0:
                AppApiCallStat.objects.create(
                    app=app, tenant=app.tenant, api_path=request.path,
                    call_date=today, call_count=1,
                )
        except Exception:
            pass
