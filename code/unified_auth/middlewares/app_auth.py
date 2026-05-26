import time
from datetime import date
from django.http import JsonResponse
from django.db.models import F
from django.utils.deprecation import MiddlewareMixin
from common.response import api_response
from common.errors import ErrorCode
from common.utils import verify_signature
from apps.applications.models import Application, AppApiCallStat


class AppAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not request.path.startswith("/api/v1/open/"):
            return None
        if request.method == "OPTIONS":
            return None

        app_key = request.headers.get("X-App-Key")
        timestamp = request.headers.get("X-Timestamp")
        signature = request.headers.get("X-Signature")

        if not all([app_key, timestamp, signature]):
            return JsonResponse(
                api_response(ErrorCode.APP_KEY_INVALID, message="缺少认证参数"),
                status=401,
            )

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

        if not verify_signature(app.app_secret_hash, {}, timestamp, signature):
            return JsonResponse(api_response(ErrorCode.SIGNATURE_INVALID), status=401)

        request.app = app
        request.app_key = app_key
        request.tenant_id = app.tenant_id

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

        return None
