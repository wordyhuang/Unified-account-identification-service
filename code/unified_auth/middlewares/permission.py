from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from common.response import api_response
from common.errors import ErrorCode


class PermissionMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not request.path.startswith("/api/v1/open/"):
            return None
        if request.method == "OPTIONS":
            return None

        app = getattr(request, "app", None)
        if app is None:
            return None

        path = request.path
        method = request.method
        path_template = self._path_to_template(path)

        from apps.rbac.models import AppRoleBinding, ApiPermission

        has_perm = AppRoleBinding.objects.filter(
            app=app,
            permission__method=method,
            permission__path=path_template,
        ).exists()

        if not has_perm:
            return JsonResponse(
                api_response(ErrorCode.NO_API_PERMISSION), status=403
            )
        return None

    def _path_to_template(self, path):
        parts = path.strip("/").split("/")
        cleaned = []
        for part in parts:
            if part.isdigit():
                cleaned.append(":id")
            else:
                cleaned.append(part)
        return "/" + "/".join(cleaned)
