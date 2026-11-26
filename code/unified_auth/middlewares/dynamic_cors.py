"""按接入应用动态放行跨域请求（数据库驱动，60 秒缓存）。"""

from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

CACHE_KEY = "dynamic_cors:allowed_origins"
CACHE_TTL = 60


def _origin(url):
    parsed = urlparse(str(url or ""))
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def allowed_origins():
    """汇总启用应用的跨域/页面对接域与注册页地址 origin；结果缓存 60 秒。"""
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached
    from apps.applications.models import Application

    origins = set()
    for app in Application.objects.filter(status=True).only(
        "cors_origins", "registration_page_url", "registration_success_url"
    ):
        urls = list(app.cors_origins or [])
        urls.extend([app.registration_page_url, app.registration_success_url])
        for raw in urls:
            origin = _origin(raw)
            if origin:
                origins.add(origin)
    cache.set(CACHE_KEY, origins, CACHE_TTL)
    return origins


class DynamicCorsMiddleware:
    """放在 CorsMiddleware 之前：request 阶段处理预检短路，response 阶段补头。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.META.get("HTTP_ORIGIN")
        if not origin or settings.DEBUG:
            return self.get_response(request)

        allowed = origin in allowed_origins()
        if request.method == "OPTIONS" and request.META.get("HTTP_ACCESS_CONTROL_REQUEST_METHOD"):
            # 预检：只回 CORS 头，不进入业务中间件
            response = HttpResponse(status=200)
            if allowed:
                self._apply(response, origin, request, preflight=True)
            else:
                response.status_code = 403
            return response

        response = self.get_response(request)
        if allowed and not response.get("Access-Control-Allow-Origin"):
            self._apply(response, origin, request)
        return response

    @staticmethod
    def _apply(response, origin, request, preflight=False):
        response["Access-Control-Allow-Origin"] = origin
        response["Access-Control-Allow-Credentials"] = "true"
        if response.get("Vary"):
            response["Vary"] = response["Vary"] + ", Origin"
        else:
            response["Vary"] = "Origin"
        if preflight:
            response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            requested = request.META.get("HTTP_ACCESS_CONTROL_REQUEST_HEADERS")
            response["Access-Control-Allow-Headers"] = requested or "Content-Type, Authorization"
            response["Access-Control-Max-Age"] = "600"
