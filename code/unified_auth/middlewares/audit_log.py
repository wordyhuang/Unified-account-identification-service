import json
from django.utils.deprecation import MiddlewareMixin
from apps.audit.models import AuditLog


class AuditLogMiddleware(MiddlewareMixin):
    SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

    def process_response(self, request, response):
        if request.method in self.SAFE_METHODS:
            return response
        if request.path.startswith("/admin/"):
            return response

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return response

        try:
            tenant_id = getattr(request, "tenant_id", None)
            AuditLog.objects.create(
                tenant_id=tenant_id if tenant_id else None,
                actor_id=user.id,
                actor_name=user.username,
                action=f"{request.method}:{request.path}",
                detail={
                    "params": dict(request.GET) if request.GET else {},
                    "body": self._safe_body(request),
                },
                ip_address=request.META.get("REMOTE_ADDR", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
            )
        except Exception:
            pass
        return response

    def _safe_body(self, request):
        try:
            if hasattr(request, 'body') and request.body:
                body = json.loads(request.body)
                if "password" in body:
                    body["password"] = "***"
                if "app_secret" in body:
                    body["app_secret"] = "***"
                return body
        except Exception:
            return {}
