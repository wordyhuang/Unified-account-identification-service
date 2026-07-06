import json
import pytest
from apps.audit.models import AuditLog


pytestmark = pytest.mark.django_db


class TestMiddlewareExecutionOrder:
    """TC-GW-001: 中间件执行顺序验证"""

    def test_middleware_order(self, api_client):
        """TC-GW-001: 验证中间件栈按正确顺序执行"""
        resp = api_client.get("/api/v1/nonexistent")
        assert resp.status_code in (401, 404)


class TestAppSignatureAuth:
    """TC-GW-002~006: 应用签名认证"""

    def test_valid_signature(self, api_client, app_with_all_perms, app_headers):
        """TC-GW-002: 应用签名认证 — 有效签名"""
        resp = api_client.get("/api/v1/open/users", **app_headers)
        assert resp.status_code == 200

    def test_invalid_app_key(self, api_client):
        """TC-GW-003: 应用签名认证 — 无效 AppKey"""
        import time, hmac, hashlib
        ts = str(int(time.time()))
        sig = hmac.new(b"unknown", f"{{}}{ts}".encode(), hashlib.sha256).hexdigest()
        headers = {
            "HTTP_X_APP_KEY": "invalid_key",
            "HTTP_X_TIMESTAMP": ts,
            "HTTP_X_SIGNATURE": sig,
        }
        resp = api_client.get("/api/v1/open/users", **headers)
        assert resp.status_code == 401

    def test_tampered_signature(self, api_client, app):
        """TC-GW-004: 应用签名认证 — 签名篡改"""
        import time
        headers = {
            "HTTP_X_APP_KEY": app.app_key,
            "HTTP_X_TIMESTAMP": str(int(time.time())),
            "HTTP_X_SIGNATURE": "deadbeef",
        }
        resp = api_client.get("/api/v1/open/users", **headers)
        assert resp.status_code == 401

    def test_expired_timestamp(self, api_client, app):
        """TC-GW-005: 应用签名认证 — 时间戳防重放"""
        import time, hmac, hashlib
        old_ts = str(int(time.time()) - 600)
        sig = hmac.new(
            app.app_secret.encode("utf-8"),
            f"{{}}{old_ts}".encode(),
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "HTTP_X_APP_KEY": app.app_key,
            "HTTP_X_TIMESTAMP": old_ts,
            "HTTP_X_SIGNATURE": sig,
        }
        resp = api_client.get("/api/v1/open/users", **headers)
        assert resp.status_code == 401

    def test_duplicate_signature(self, api_client, app_with_all_perms):
        """TC-GW-006: 应用签名认证 — 重复使用签名（当前实现无nonce，允许重复）"""
        import time, hmac, hashlib
        ts = str(int(time.time()))
        sig = hmac.new(
            app_with_all_perms.app_secret.encode("utf-8"),
            f"{{}}{ts}".encode(),
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "HTTP_X_APP_KEY": app_with_all_perms.app_key,
            "HTTP_X_TIMESTAMP": ts,
            "HTTP_X_SIGNATURE": sig,
        }
        resp1 = api_client.get("/api/v1/open/users", **headers)
        assert resp1.status_code == 200
        resp2 = api_client.get("/api/v1/open/users", **headers)
        assert resp2.status_code == 200


class TestTokenAuth:
    """TC-GW-007~012: Token 认证"""

    def test_valid_token(self, api_client, staff_auth_headers, app_access_token):
        """TC-GW-007: Token 认证 — 有效 Token"""
        resp = api_client.get(f"/api/v1/auth/me?access_token={app_access_token}", **staff_auth_headers)
        assert resp.status_code == 200

    def test_invalid_token(self, api_client, invalid_token_headers, app_access_token):
        """TC-GW-008: Token 认证 — 无效 Token"""
        resp = api_client.get(f"/api/v1/auth/me?access_token={app_access_token}", **invalid_token_headers)
        assert resp.status_code == 401

    def test_expired_token(self, api_client, expired_token_headers, app_access_token):
        """TC-GW-009: Token 认证 — 过期 Token"""
        resp = api_client.get(f"/api/v1/auth/me?access_token={app_access_token}", **expired_token_headers)
        assert resp.status_code == 401

    def test_missing_auth_header(self, api_client, app_access_token):
        """TC-GW-011: Token 认证 — 缺少 Authorization 头"""
        resp = api_client.get(f"/api/v1/auth/me?access_token={app_access_token}")
        assert resp.status_code == 401

    def test_wrong_auth_format(self, api_client, app_access_token):
        """TC-GW-012: Token 认证 — 格式错误"""
        resp = api_client.get(
            f"/api/v1/auth/me?access_token={app_access_token}",
            HTTP_AUTHORIZATION="NotBearer xxxxx",
        )
        assert resp.status_code == 401


class TestPermissionCheck:
    """TC-GW-013~015: 权限校验"""

    def test_has_permission_pass(self, api_client, app_with_all_perms, app_headers):
        """TC-GW-013: 权限校验 — 有权限放行"""
        resp = api_client.get("/api/v1/open/users", **app_headers)
        assert resp.status_code == 200

    def test_no_permission_reject(self, api_client, app, app_headers):
        """TC-GW-014: 权限校验 — 无权限拒绝（应用未绑定 user:read）"""
        resp = api_client.get("/api/v1/open/users", **app_headers)
        assert resp.status_code == 403


class TestAuditLog:
    """TC-GW-016~018: 审计日志"""

    def test_write_operation_records_log(self, api_client, staff_auth_headers, app_access_token):
        """TC-GW-016: 审计日志 — 写操作记录"""
        before_count = AuditLog.objects.count()
        api_client.put(
            f"/api/v1/auth/me?access_token={app_access_token}",
            {"nickname": "审计测试"},
            content_type="application/json",
            **staff_auth_headers,
        )
        after_count = AuditLog.objects.count()
        assert after_count > before_count

    def test_get_operation_not_recorded(self, api_client, staff_auth_headers, app_access_token):
        """TC-GW-017: 审计日志 — GET 操作不记录"""
        before_count = AuditLog.objects.count()
        api_client.get(f"/api/v1/auth/me?access_token={app_access_token}", **staff_auth_headers)
        after_count = AuditLog.objects.count()
        assert after_count == before_count


class TestDataIsolation:
    """TC-GW-019~020: 数据隔离"""

    def test_cross_tenant_token_isolation(self, api_client, staff_auth_headers, tenant_b, user_b):
        """TC-GW-019: Token 跨租户 — staff_user 只能看到自己的租户数据"""
        resp = api_client.get("/api/v1/admin/users", **staff_auth_headers)
        data = json.loads(resp.content)
        for user in data["data"]["users"]:
            assert user["tenant_id"] != tenant_b.id

    def test_admin_api_tenant_isolation(self, api_client, staff_auth_headers,
                                         staff_user_b, tenant_b):
        """TC-GW-020: 管理 API 跨租户 — 租户B的管理员仅看到B的数据"""
        token_b = __import__("common.utils").utils.create_access_token({
            "user_id": staff_user_b.id,
            "tenant_id": staff_user_b.tenant_id,
            "user_type": staff_user_b.user_type,
        })
        headers_b = {"HTTP_AUTHORIZATION": f"Bearer {token_b}"}
        resp = api_client.get("/api/v1/admin/users", **headers_b)
        data = json.loads(resp.content)
        for user in data["data"]["users"]:
            assert user["tenant_id"] == tenant_b.id


class TestNonOpenApiBypass:
    """TC-GW-021: 非开放 API 绕过应用认证"""

    def test_non_open_api_not_intercepted(self, api_client, app_access_token):
        """TC-GW-021: 非开放 API（登录）不受 AppAuth 拦截"""
        resp = api_client.post(
            f"/api/v1/auth/login?access_token={app_access_token}",
            {"username": "nonexistent", "password": "test"},
            content_type="application/json",
        )
        assert resp.status_code != 401


class TestNonExistentRoute:
    """TC-GW-022: 不存在路由"""

    def test_nonexistent_route(self, api_client):
        resp = api_client.get("/api/v1/nonexistent")
        assert resp.status_code in (401, 404)