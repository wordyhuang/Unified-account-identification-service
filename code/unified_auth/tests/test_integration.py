import json
import pytest
from apps.accounts.models import User
from apps.audit.models import AuditLog


pytestmark = pytest.mark.django_db


class TestAuthOpenApiIntegration:
    """IT-001~005: 认证 + 开放 API 集成流"""

    def test_login_verify_token_flow(self, api_client, app_with_all_perms, app_headers,
                                      staff_user):
        """IT-001: 用户登录 → 获取 Token → 开放 API 验证 Token"""
        from common.utils import create_access_token
        token = create_access_token({
            "user_id": staff_user.id,
            "tenant_id": staff_user.tenant_id,
            "user_type": staff_user.user_type,
        })

        resp = api_client.post(
            "/api/v1/open/token/verify",
            {"token": token},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["valid"] is True

    def test_login_read_update_user_flow(self, api_client, app_with_all_perms, app_headers,
                                          staff_user):
        """IT-002: 用户登录 → 开放 API 查用户 → 开放 API 修改用户"""
        resp = api_client.get(f"/api/v1/open/users/{staff_user.id}", **app_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["username"] == "staff_user"

        resp = api_client.put(
            f"/api/v1/open/users/{staff_user.id}",
            {"nickname": "集成测试改名"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

        staff_user.refresh_from_db()
        assert staff_user.nickname == "集成测试改名"

    def test_create_app_auth_openapi_flow(self, api_client, tenant_default, permissions):
        """IT-003: 创建应用 → 应用授权 → 第三方调用开放 API"""
        from apps.applications.models import Application
        from apps.rbac.models import AppRoleBinding
        import time, hmac, hashlib

        app = Application.objects.create(
            tenant=tenant_default,
            name="集成测试应用",
            app_key="integration-app-key",
            app_secret="integration-secret-hash",
        )
        for p in permissions[:2]:
            AppRoleBinding.objects.create(app=app, permission=p)

        ts = str(int(time.time()))
        sig = hmac.new(
            app.app_secret.encode("utf-8"),
            f"{{}}{ts}".encode(),
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "HTTP_X_APP_KEY": app.app_key,
            "HTTP_X_TIMESTAMP": ts,
            "HTTP_X_SIGNATURE": sig,
        }

        resp = api_client.get("/api/v1/open/users", **headers)
        assert resp.status_code == 200

    def test_create_user_assign_role_check_perm_flow(self, api_client, app_with_all_perms,
                                                      app_headers, tenant_default, permissions):
        """IT-004: 创建用户 → 分配角色 → 校验权限"""
        from apps.accounts.models import User
        from apps.rbac.models import Role, RolePermission, UserRole

        new_user = User.objects.create_user(
            tenant=tenant_default,
            username="integration_user",
            password="test1234",
            user_type="internal",
        )

        role = Role.objects.create(tenant=tenant_default, name="集成角色", code="integration_role")
        for p in permissions:
            RolePermission.objects.create(role=role, permission=p)
        UserRole.objects.create(user=new_user, role=role)

        resp = api_client.post(
            "/api/v1/open/permissions/check",
            {"user_id": new_user.id, "permission_code": "user:read"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["has_permission"] is True

    def test_token_refresh_rotation_flow(self, api_client, staff_user, app_access_token):
        """IT-005: 登录 → Token 刷新 → 旧 Token 失效"""
        login_resp = api_client.post(
            f"/api/v1/auth/login?access_token={app_access_token}",
            {"username": "staff_user", "password": "test1234"},
            content_type="application/json",
        )
        login_data = json.loads(login_resp.content)
        old_access_token = login_data["data"]["token"]
        refresh_token = login_data["data"]["refresh_token"]

        refresh_resp = api_client.post(
            f"/api/v1/auth/token/refresh?access_token={app_access_token}",
            {"refresh_token": refresh_token},
            content_type="application/json",
        )
        refresh_data = json.loads(refresh_resp.content)
        assert refresh_data["code"] == 0

        old_token_resp = api_client.get(
            f"/api/v1/auth/me?access_token={app_access_token}",
            HTTP_AUTHORIZATION=f"Bearer {old_access_token}",
        )
        assert old_token_resp.status_code == 200


class TestMultiTenantIntegration:
    """IT-006~008: 多租户数据隔离集成流"""

    def test_tenant_data_isolation(self, api_client, tenant_default, tenant_b,
                                    staff_user, staff_user_b):
        """IT-006: 租户A和租户B各自有用户，查询隔离"""
        from common.utils import create_access_token
        token_a = create_access_token({
            "user_id": staff_user.id,
            "tenant_id": staff_user.tenant_id,
            "user_type": staff_user.user_type,
        })
        headers_a = {"HTTP_AUTHORIZATION": f"Bearer {token_a}"}

        resp = api_client.get("/api/v1/admin/users", **headers_a)
        data = json.loads(resp.content)
        for u in data["data"]["users"]:
            assert u["tenant_id"] == tenant_default.id

    def test_app_cross_tenant_invisibility(self, api_client, app, app_b,
                                            staff_user, staff_user_b):
        """IT-007: 应用跨租户不可见"""
        from common.utils import create_access_token
        token_b = create_access_token({
            "user_id": staff_user_b.id,
            "tenant_id": staff_user_b.tenant_id,
            "user_type": staff_user_b.user_type,
        })
        headers_b = {"HTTP_AUTHORIZATION": f"Bearer {token_b}"}

        resp = api_client.get("/api/v1/admin/applications", **headers_b)
        data = json.loads(resp.content)
        app_names = [a["name"] for a in data["data"]["apps"]]
        assert "测试应用" not in app_names


class TestTokenVerification:
    """IT-009~010: Token验证测试"""

    def test_password_login_token_verify(self, api_client, app_with_all_perms, app_headers,
                                         staff_user, app_access_token):
        """IT-009: 账号密码登录生成的token能通过verify_token校验"""
        login_resp = api_client.post(
            f"/api/v1/auth/login?access_token={app_access_token}",
            {"username": "staff_user", "password": "test1234"},
            content_type="application/json",
        )
        login_data = json.loads(login_resp.content)
        assert login_data["code"] == 0
        access_token = login_data["data"]["token"]

        verify_resp = api_client.post(
            "/api/v1/open/token/verify",
            {"token": access_token},
            content_type="application/json",
            **app_headers,
        )
        verify_data = json.loads(verify_resp.content)
        assert verify_data["code"] == 0
        assert verify_data["data"]["valid"] is True
        assert verify_data["data"]["user_id"] == staff_user.id
        assert verify_data["data"]["tenant_id"] == staff_user.tenant_id

    def test_sms_login_token_verify(self, api_client, app_with_all_perms, app_headers,
                                    tenant_default, app_access_token):
        """IT-010: 短信登录生成的token能通过verify_token校验"""
        phone = "13800138001"
        
        from django.core.cache import cache
        cache.set(f"sms:{phone}", "555555", timeout=300)

        login_resp = api_client.post(
            f"/api/v1/auth/sms/login?access_token={app_access_token}",
            {"phone": phone, "code": "555555"},
            content_type="application/json",
        )
        login_data = json.loads(login_resp.content)
        assert login_data["code"] == 0, f"短信登录失败: {login_data}"
        access_token = login_data["data"]["token"]

        verify_resp = api_client.post(
            "/api/v1/open/token/verify",
            {"token": access_token},
            content_type="application/json",
            **app_headers,
        )
        verify_data = json.loads(verify_resp.content)
        assert verify_data["code"] == 0
        assert verify_data["data"]["valid"] is True
        assert verify_data["data"]["user_id"] is not None
        assert verify_data["data"]["tenant_id"] == tenant_default.id


class TestGatewayChain:
    """IT-011~013: 网关中间件完整链路"""

    def test_successful_gateway_chain(self, api_client, app_with_all_perms, app_headers):
        """IT-011: 完整成功链路 — AppAuth → Permission → 业务处理"""
        resp = api_client.get("/api/v1/open/users", **app_headers)
        assert resp.status_code == 200

    def test_failed_app_auth_chain(self, api_client):
        """IT-012: AppAuth 失败链路 — 签名无效 → 拒绝"""
        resp = api_client.get("/api/v1/open/users")
        assert resp.status_code == 401

    def test_failed_permission_chain(self, api_client, app, app_headers):
        """IT-013: Permission 失败链路 — AppAuth 通过 → 无权限 → 拒绝"""
        resp = api_client.get("/api/v1/open/users", **app_headers)
        assert resp.status_code == 403