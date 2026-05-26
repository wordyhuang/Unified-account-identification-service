import json
import time
import hmac
import hashlib
import pytest
import os
from django.test import Client
from django.core.cache import cache
from apps.accounts.models import Tenant, User, Department
from apps.applications.models import Application
from apps.rbac.models import ApiPermission, Role, RolePermission, UserRole, AppRoleBinding
from apps.audit.models import AuditLog
from common.utils import create_access_token


# Superadmin credentials must be set before tests
os.environ["SUPERADMIN_ACCOUNTS"] = json.dumps([
    {"username": "admin", "password": "admin123456"},
])
os.environ["SMS_PROVIDER"] = "mock"


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    from middlewares.rate_limit import RateLimitMiddleware
    RateLimitMiddleware._requests = {}


@pytest.fixture
def tenant_default():
    return Tenant.objects.create(name="默认企业", slug="default")


@pytest.fixture
def tenant_b():
    return Tenant.objects.create(name="测试企业B", slug="test_b")


@pytest.fixture
def staff_user(tenant_default):
    return User.objects.create_user(
        tenant=tenant_default,
        username="staff_user",
        password="test1234",
        user_type="internal",
        is_staff=True,
    )


@pytest.fixture
def normal_user(tenant_default):
    return User.objects.create_user(
        tenant=tenant_default,
        username="normal_user",
        password="test1234",
        user_type="internal",
    )


@pytest.fixture
def external_user(tenant_default):
    return User.objects.create_user(
        tenant=tenant_default,
        username="external_user",
        password="test1234",
        user_type="external",
    )


@pytest.fixture
def disabled_user(tenant_default):
    return User.objects.create_user(
        tenant=tenant_default,
        username="disabled_user",
        password="test1234",
        user_type="internal",
        status=0,
    )


@pytest.fixture
def user_b(tenant_b):
    return User.objects.create_user(
        tenant=tenant_b,
        username="user_b",
        password="test1234",
        user_type="internal",
    )


@pytest.fixture
def staff_user_b(tenant_b):
    return User.objects.create_user(
        tenant=tenant_b,
        username="staff_b",
        password="test1234",
        user_type="internal",
        is_staff=True,
    )


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def staff_auth_headers(staff_user):
    token = create_access_token({
        "user_id": staff_user.id,
        "tenant_id": staff_user.tenant_id,
        "user_type": staff_user.user_type,
    })
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


@pytest.fixture
def normal_auth_headers(normal_user):
    token = create_access_token({
        "user_id": normal_user.id,
        "tenant_id": normal_user.tenant_id,
        "user_type": normal_user.user_type,
    })
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


@pytest.fixture
def app(tenant_default):
    app_secret = "test_secret_key_for_signing"
    return Application.objects.create(
        tenant=tenant_default,
        name="测试应用",
        app_key="test_key_001",
        app_secret_hash=app_secret,
    )


@pytest.fixture
def app_headers(app):
    timestamp = str(int(time.time()))
    body_str = json.dumps({}, ensure_ascii=False, separators=(",", ":"))
    message = f"{body_str}{timestamp}"
    signature = hmac.new(
        app.app_secret_hash.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "HTTP_X_APP_KEY": app.app_key,
        "HTTP_X_TIMESTAMP": timestamp,
        "HTTP_X_SIGNATURE": signature,
    }


@pytest.fixture
def app_b(tenant_b):
    app_secret = "test_secret_key_b"
    return Application.objects.create(
        tenant=tenant_b,
        name="B企业应用",
        app_key="test_key_b_002",
        app_secret_hash=app_secret,
    )


@pytest.fixture
def app_b_headers(app_b):
    timestamp = str(int(time.time()))
    body_str = json.dumps({}, ensure_ascii=False, separators=(",", ":"))
    message = f"{body_str}{timestamp}"
    signature = hmac.new(
        app_b.app_secret_hash.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "HTTP_X_APP_KEY": app_b.app_key,
        "HTTP_X_TIMESTAMP": timestamp,
        "HTTP_X_SIGNATURE": signature,
    }


@pytest.fixture
def disabled_app(tenant_default):
    return Application.objects.create(
        tenant=tenant_default,
        name="已禁用应用",
        app_key="disabled_key_003",
        app_secret_hash="disabled_secret",
        status=False,
    )


@pytest.fixture
def permissions():
    perms = []
    perm_data = [
        ("token:verify", "验证Token", "POST", "/api/v1/open/verify_token", "auth"),
        ("user:read", "读取用户", "GET", "/api/v1/open/users", "user"),
        ("user:read_detail", "读取用户详情", "GET", "/api/v1/open/users/:id", "user"),
        ("user:create", "创建用户", "POST", "/api/v1/open/users", "user"),
        ("user:update", "修改用户", "PUT", "/api/v1/open/users/:id", "user"),
        ("user:status", "修改用户状态", "PATCH", "/api/v1/open/users/:id/status", "user"),
        ("permission:check", "校验权限", "POST", "/api/v1/open/check_permission", "permission"),
    ]
    for code, name, method, path, cat in perm_data:
        p, _ = ApiPermission.objects.get_or_create(
            code=code,
            defaults={"name": name, "method": method, "path": path, "category": cat},
        )
        perms.append(p)
    return perms


@pytest.fixture
def role_with_all_perms(tenant_default, permissions):
    role, _ = Role.objects.get_or_create(
        tenant=tenant_default,
        code="admin",
        defaults={"name": "管理员"},
    )
    for p in permissions:
        RolePermission.objects.get_or_create(role=role, permission=p)
    return role


@pytest.fixture
def role_without_perms(tenant_default):
    role, _ = Role.objects.get_or_create(
        tenant=tenant_default,
        code="no_perm_role",
        defaults={"name": "无权限角色"},
    )
    return role


@pytest.fixture
def staff_user_role(staff_user, role_with_all_perms):
    UserRole.objects.get_or_create(user=staff_user, role=role_with_all_perms)
    return staff_user


@pytest.fixture
def app_with_all_perms(app, permissions):
    for p in permissions:
        AppRoleBinding.objects.get_or_create(app=app, permission=p)
    return app


@pytest.fixture
def audit_logs(tenant_default, staff_user):
    logs = []
    for i in range(25):
        log = AuditLog.objects.create(
            tenant=tenant_default,
            actor_id=staff_user.id,
            actor_name=staff_user.username,
            action="user.login" if i < 15 else "admin.user.create",
            resource_type="user" if i >= 15 else None,
            resource_id=i if i >= 15 else None,
            detail={"test": f"data_{i}"},
            ip_address="127.0.0.1",
        )
        logs.append(log)
    return logs


@pytest.fixture
def department(tenant_default):
    return Department.objects.create(
        tenant=tenant_default,
        name="研发部",
        sort_order=1,
    )


@pytest.fixture
def superadmin_headers():
    """Superadmin login via env credentials returns a special token"""
    from common.utils import create_access_token, generate_refresh_token
    token = create_access_token({
        "username": "admin",
        "is_superadmin": True,
        "tenant_id": None,
    })
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


@pytest.fixture
def impersonate_headers():
    token = create_access_token({
        "username": "admin",
        "is_superadmin": True,
        "tenant_id": None,
        "impersonated": True,
    })
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


@pytest.fixture
def expired_token_headers():
    import jwt
    from django.conf import settings
    from datetime import datetime, timedelta, timezone
    payload = {
        "user_id": 99999,
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


@pytest.fixture
def invalid_token_headers():
    return {"HTTP_AUTHORIZATION": "Bearer invalid.jwt.token"}