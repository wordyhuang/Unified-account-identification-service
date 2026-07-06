import uuid
from django.utils import timezone
from datetime import timedelta
from .models import AuthCode, Application, User


def validate_redirect_uri(app: Application, redirect_uri: str) -> bool:
    callback_urls = app.callback_urls or []
    if not callback_urls:
        return False
    for allowed_uri in callback_urls:
        if redirect_uri == allowed_uri or redirect_uri.startswith(allowed_uri):
            return True
    return False


def generate_auth_code(app: Application, user: User, redirect_uri: str, state: str = "") -> AuthCode:
    code = uuid.uuid4().hex + uuid.uuid4().hex[:16]
    return AuthCode.objects.create(
        code=code,
        app=app,
        user=user,
        redirect_uri=redirect_uri,
        state=state or "",
        expires_at=timezone.now() + timedelta(minutes=5),
    )


def verify_app_secret(app: Application, app_secret_input: str) -> bool:
    return app_secret_input == app.app_secret