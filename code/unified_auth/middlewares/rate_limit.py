import time
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from common.response import api_response
from common.errors import ErrorCode


class RateLimitMiddleware(MiddlewareMixin):
    _requests = {}

    def process_request(self, request):
        if request.path.startswith("/admin/"):
            return None
        if request.path.startswith("/static/"):
            return None
        if request.path == "/favicon.ico":
            return None
        key = self._get_key(request)
        now = time.time()
        window = 60
        max_requests = 60 if not getattr(request, "app_key", None) else 1000

        records = self._requests.get(key, [])
        records = [t for t in records if now - t < window]
        if len(records) >= max_requests:
            return JsonResponse(
                api_response(ErrorCode.RATE_LIMIT_EXCEEDED),
                status=429,
            )
        records.append(now)
        self._requests[key] = records
        return None

    def _get_key(self, request):
        app_key = getattr(request, "app_key", None)
        if app_key:
            return f"app:{app_key}"
        ip = request.META.get("REMOTE_ADDR", "unknown")
        return f"ip:{ip}"
