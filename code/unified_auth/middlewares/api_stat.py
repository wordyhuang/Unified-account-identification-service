from datetime import date
from django.db.models import F
from django.utils.deprecation import MiddlewareMixin
from apps.applications.models import TenantApiCallStat


class ApiStatMiddleware(MiddlewareMixin):
    SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
    SKIP_PREFIXES = ("/static/", "/admin/", "/favicon.ico")

    def process_response(self, request, response):
        if request.method in self.SAFE_METHODS:
            return response
        if any(request.path.startswith(p) for p in self.SKIP_PREFIXES):
            return response
        if request.path.startswith("/api/v1/open/"):
            return response

        tenant_id = getattr(request, "tenant_id", None)
        if not tenant_id:
            return response

        try:
            today = date.today()
            affected = TenantApiCallStat.objects.filter(
                tenant_id=tenant_id, api_path=request.path, call_date=today
            ).update(call_count=F("call_count") + 1)
            if affected == 0:
                TenantApiCallStat.objects.create(
                    tenant_id=tenant_id, api_path=request.path,
                    call_date=today, call_count=1,
                )
        except Exception:
            pass

        return response
