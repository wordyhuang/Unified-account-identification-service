import json
import time
import pytest
from django.core.cache import cache


pytestmark = pytest.mark.django_db


class TestPasswordLogin:
    """TC-AUTH-001~006: 密码登录"""

    def test_login_success(self, api_client, staff_user):
        """TC-AUTH-001: 密码登录 — 成功"""
        resp = api_client.post(
            "/api/v1/auth/login",
            {"username": "staff_user", "password": "test1234"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
        assert data["data"]["user_id"] == staff_user.id
        assert data["data"]["username"] == "staff_user"

    def test_login_wrong_password(self, api_client):
        """TC-AUTH-002: 密码登录 — 密码错误"""
        resp = api_client.post(
            "/api/v1/auth/login",
            {"username": "staff_user", "password": "wrong"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_login_user_not_found(self, api_client):
        """TC-AUTH-003: 密码登录 — 用户名不存在"""
        resp = api_client.post(
            "/api/v1/auth/login",
            {"username": "nonexist", "password": "test1234"},
            content_type="application/json",
        )
        assert resp.status_code == 404
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_login_disabled_user(self, api_client, disabled_user):
        """TC-AUTH-004: 密码登录 — 用户已禁用"""
        resp = api_client.post(
            "/api/v1/auth/login",
            {"username": "disabled_user", "password": "test1234"},
            content_type="application/json",
        )
        assert resp.status_code == 403
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_login_missing_params(self, api_client):
        """TC-AUTH-005: 密码登录 — 参数缺失"""
        resp = api_client.post(
            "/api/v1/auth/login",
            {},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_login_superadmin(self, api_client):
        """超级管理员密码登录 — 环境变量配置"""
        resp = api_client.post(
            "/api/v1/auth/login",
            {"username": "admin", "password": "admin123456"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["is_superadmin"] is True
        assert data["data"]["is_superuser"] is True


class TestSmsLogin:
    """TC-AUTH-007~011: 短信验证码"""

    def test_sms_send_success(self, api_client):
        """TC-AUTH-007: 短信验证码 — 发送成功"""
        resp = api_client.post(
            "/api/v1/auth/sms/send",
            {"phone": "13800138000"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_sms_send_invalid_phone(self, api_client):
        """TC-AUTH-008: 短信验证码 — 手机号格式错误"""
        resp = api_client.post(
            "/api/v1/auth/sms/send",
            {},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_sms_login_success(self, api_client, tenant_default):
        """TC-AUTH-009: 短信验证码登录 — 成功"""
        api_client.post(
            "/api/v1/auth/sms/send",
            {"phone": "13900139000"},
            content_type="application/json",
        )
        cache.set("sms:13900139000", "123456", timeout=300)
        resp = api_client.post(
            "/api/v1/auth/sms/login",
            {"phone": "13900139000", "code": "123456"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "access_token" in data["data"]

    def test_sms_login_wrong_code(self, api_client, tenant_default):
        """TC-AUTH-010: 短信验证码登录 — 验证码错误"""
        cache.set("sms:13700137000", "123456", timeout=300)
        resp = api_client.post(
            "/api/v1/auth/sms/login",
            {"phone": "13700137000", "code": "000000"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_sms_login_expired_code(self, api_client, tenant_default):
        """TC-AUTH-011: 短信验证码登录 — 验证码过期"""
        resp = api_client.post(
            "/api/v1/auth/sms/login",
            {"phone": "13600136000", "code": "123456"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0


class TestSocialLogin:
    """TC-AUTH-012~013: 社交登录"""

    def test_social_login_success(self, api_client, tenant_default):
        """TC-AUTH-012: 社交登录 — 成功"""
        resp = api_client.post(
            "/api/v1/auth/social/login",
            {"provider": "wechat_mp", "code": "mock_code"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "access_token" in data["data"]

    def test_social_login_unsupported_provider(self, api_client, tenant_default):
        """TC-AUTH-013: 社交登录 — 不支持的 provider"""
        resp = api_client.post(
            "/api/v1/auth/social/login",
            {"provider": "unknown", "code": "xxx"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0


class TestTokenRefresh:
    """TC-AUTH-014~016: Token 刷新"""

    def test_refresh_success(self, api_client, staff_user):
        """TC-AUTH-014: Token 刷新 — 成功"""
        login_resp = api_client.post(
            "/api/v1/auth/login",
            {"username": "staff_user", "password": "test1234"},
            content_type="application/json",
        )
        refresh_token = json.loads(login_resp.content)["data"]["refresh_token"]

        resp = api_client.post(
            "/api/v1/auth/refresh",
            {"refresh_token": refresh_token},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]

    def test_refresh_invalid_token(self, api_client):
        """TC-AUTH-015: Token 刷新 — 无效 refresh_token"""
        resp = api_client.post(
            "/api/v1/auth/refresh",
            {"refresh_token": "invalid-uuid"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_refresh_token_rotation(self, api_client, staff_user):
        """TC-AUTH-016: Token 刷新 — token 轮换策略（旧token一次性失效）"""
        login_resp = api_client.post(
            "/api/v1/auth/login",
            {"username": "staff_user", "password": "test1234"},
            content_type="application/json",
        )
        refresh_token = json.loads(login_resp.content)["data"]["refresh_token"]

        resp1 = api_client.post(
            "/api/v1/auth/refresh",
            {"refresh_token": refresh_token},
            content_type="application/json",
        )
        assert json.loads(resp1.content)["code"] == 0

        resp2 = api_client.post(
            "/api/v1/auth/refresh",
            {"refresh_token": refresh_token},
            content_type="application/json",
        )
        data2 = json.loads(resp2.content)
        assert data2["code"] < 0


class TestLogout:
    """TC-AUTH-017: 登出"""

    def test_logout(self, api_client, staff_auth_headers):
        """TC-AUTH-017: 登出成功"""
        resp = api_client.post(
            "/api/v1/auth/logout",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0


class TestUserInfo:
    """TC-AUTH-018~020: 用户信息"""

    def test_userinfo_success(self, api_client, staff_user, staff_auth_headers):
        """TC-AUTH-018: 获取用户信息 — 成功"""
        resp = api_client.get("/api/v1/auth/userinfo", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["username"] == "staff_user"
        assert "user_type" in data["data"]
        assert "email" in data["data"]
        assert "phone" in data["data"]
        assert "nickname" in data["data"]
        assert "status" in data["data"]

    def test_userinfo_no_token(self, api_client):
        """TC-AUTH-019: 获取用户信息 — 无 Token"""
        resp = api_client.get("/api/v1/auth/userinfo")
        assert resp.status_code == 401

    def test_userinfo_invalid_token(self, api_client, invalid_token_headers):
        """TC-AUTH-020: 获取用户信息 — 无效 Token"""
        resp = api_client.get("/api/v1/auth/userinfo", **invalid_token_headers)
        assert resp.status_code == 401

    def test_userinfo_expired_token(self, api_client, expired_token_headers):
        """TC-AUTH-020: 获取用户信息 — Token 过期"""
        resp = api_client.get("/api/v1/auth/userinfo", **expired_token_headers)
        assert resp.status_code == 401


class TestUpdateUserInfo:
    """TC-AUTH-021: 修改用户信息"""

    def test_update_userinfo_success(self, api_client, staff_user, staff_auth_headers):
        """TC-AUTH-021: 修改用户信息 — 成功"""
        resp = api_client.put(
            "/api/v1/auth/userinfo",
            {"nickname": "新昵称", "email": "new@test.com"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

        staff_user.refresh_from_db()
        assert staff_user.nickname == "新昵称"
        assert staff_user.email == "new@test.com"


class TestChangePassword:
    """TC-AUTH-022~024: 修改密码"""

    def test_change_password_success(self, api_client, staff_user, staff_auth_headers):
        """TC-AUTH-022: 修改密码 — 成功"""
        resp = api_client.patch(
            "/api/v1/auth/userinfo/password",
            {"old_password": "test1234", "new_password": "newpass5678"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

        staff_user.refresh_from_db()
        assert staff_user.check_password("newpass5678")

    def test_change_password_wrong_old(self, api_client, staff_auth_headers):
        """TC-AUTH-023: 修改密码 — 旧密码错误"""
        resp = api_client.patch(
            "/api/v1/auth/userinfo/password",
            {"old_password": "wrong", "new_password": "newpass5678"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_change_password_weak_new(self, api_client, staff_auth_headers):
        """TC-AUTH-024: 修改密码 — 新密码强度不足（过短）"""
        resp = api_client.patch(
            "/api/v1/auth/userinfo/password",
            {"old_password": "test1234", "new_password": "123"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0