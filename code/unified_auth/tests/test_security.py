import json
import pytest
from apps.accounts.models import User
from apps.applications.models import Application


pytestmark = pytest.mark.django_db


class TestSecurity:
    """SEC-001~009: 安全测试"""

    def test_password_stored_as_hash(self, api_client, staff_user):
        """SEC-001: 密码明文检测 — 数据库密码为哈希值"""
        user = User.objects.get(id=staff_user.id)
        assert not user.password.startswith("$2")
        assert not user.password.startswith("pbkdf2_sha256$") is False
        assert user.password.startswith("pbkdf2_sha256$")

    def test_secret_stored_as_hash(self, api_client, staff_auth_headers):
        """SEC-002: Secret 明文检测 — 通过API创建应用后，数据库存储的是哈希值"""
        resp = api_client.post(
            "/api/v1/admin/applications",
            {"name": "安全测试应用"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        app_id = data["data"]["id"]
        raw_secret = data["data"]["app_secret_raw"]

        from apps.applications.models import Application
        app_obj = Application.objects.get(id=app_id)
        import hashlib
        expected_hash = hashlib.sha256(raw_secret.encode()).hexdigest()
        assert app_obj.app_secret_hash == expected_hash
        assert app_obj.app_secret_hash != raw_secret

    def test_sql_injection_protection(self, api_client):
        """SEC-003: SQL 注入防护"""
        resp = api_client.post(
            "/api/v1/auth/login",
            {"username": "' OR 1=1 --", "password": "test"},
            content_type="application/json",
        )
        assert resp.status_code in (400, 404)
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_xss_protection(self, api_client):
        """SEC-004: XSS 防护 — 用户名字段传入脚本"""
        resp = api_client.post(
            "/api/v1/auth/login",
            {"username": "<script>alert('xss')</script>", "password": "test1234"},
            content_type="application/json",
        )
        assert resp.status_code in (400, 404)

    def test_error_response_no_stacktrace(self, api_client):
        """SEC-006: 敏感信息泄露 — 错误响应不暴露堆栈信息"""
        resp = api_client.get("/api/v1/auth/userinfo")
        body = resp.content.decode()
        assert "Traceback" not in body
        assert "File \"" not in body

    def test_token_forgery_protection(self, api_client):
        """SEC-007: Token 伪造 — 修改 JWT payload 应失败"""
        import jwt
        from django.conf import settings
        from datetime import datetime, timedelta, timezone

        forged_token = jwt.encode(
            {"user_id": 1, "tenant_id": 1, "user_type": "internal",
             "exp": datetime.now(timezone.utc) + timedelta(hours=1),
             "iat": datetime.now(timezone.utc)},
            "wrong_secret_key",
            algorithm="HS256",
        )
        resp = api_client.get(
            "/api/v1/auth/userinfo",
            HTTP_AUTHORIZATION=f"Bearer {forged_token}",
        )
        assert resp.status_code == 401

    def test_privilege_escalation(self, api_client, normal_auth_headers):
        """SEC-008: 权限提升 — 普通用户访问管理 API"""
        resp = api_client.get("/api/v1/admin/stats", **normal_auth_headers)
        assert resp.status_code == 403

    def test_horizontal_privilege_escalation(self, api_client, staff_auth_headers, user_b):
        """SEC-009: 水平越权 — 用户A无法访问用户B的数据"""
        resp = api_client.get(f"/api/v1/admin/users/{user_b.id}", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] < 0 or resp.status_code == 404