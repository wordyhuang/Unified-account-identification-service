import json
import time
import pytest
from django.core.cache import cache
from django.test.utils import override_settings
from apps.accounts.models import User
from common.utils import create_access_token


pytestmark = pytest.mark.django_db


def _url(path, token):
    """为 auth 接口路径追加 access_token 查询参数"""
    sep = "&" if "?" in path else "?"
    return f"{path}{sep}access_token={token}"


class TestPasswordLogin:
    """TC-AUTH-001~006: 密码登录"""

    def test_login_success(self, api_client, staff_user, app_access_token):
        """TC-AUTH-001: 密码登录 — 成功"""
        resp = api_client.post(
            _url("/api/v1/auth/login", app_access_token),
            {"username": "staff_user", "password": "test1234"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "token" in data["data"]
        assert "refresh_token" in data["data"]
        assert data["data"]["user_id"] == staff_user.id
        assert data["data"]["username"] == "staff_user"

    def test_login_wrong_password(self, api_client, app_access_token):
        """TC-AUTH-002: 密码登录 — 密码错误"""
        resp = api_client.post(
            _url("/api/v1/auth/login", app_access_token),
            {"username": "staff_user", "password": "wrong"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_login_user_not_found(self, api_client, app_access_token):
        """TC-AUTH-003: 密码登录 — 用户名不存在"""
        resp = api_client.post(
            _url("/api/v1/auth/login", app_access_token),
            {"username": "nonexist", "password": "test1234"},
            content_type="application/json",
        )
        assert resp.status_code == 404
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_login_disabled_user(self, api_client, disabled_user, app_access_token):
        """TC-AUTH-004: 密码登录 — 用户已禁用"""
        resp = api_client.post(
            _url("/api/v1/auth/login", app_access_token),
            {"username": "disabled_user", "password": "test1234"},
            content_type="application/json",
        )
        assert resp.status_code == 403
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_login_missing_params(self, api_client, app_access_token):
        """TC-AUTH-005: 密码登录 — 参数缺失"""
        resp = api_client.post(
            _url("/api/v1/auth/login", app_access_token),
            {},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_login_superadmin(self, api_client, app_access_token):
        """超级管理员密码登录 — 环境变量配置"""
        resp = api_client.post(
            _url("/api/v1/auth/login", app_access_token),
            {"username": "admin", "password": "admin123456"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["is_superadmin"] is True
        assert data["data"]["is_superuser"] is True


class TestSmsLogin:
    """TC-AUTH-007~011: 短信验证码"""

    def test_sms_send_success(self, api_client, app_access_token):
        """TC-AUTH-007: 短信验证码 — 发送成功"""
        resp = api_client.post(
            _url("/api/v1/auth/sms/send", app_access_token),
            {"phone": "13800138000"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_sms_send_invalid_phone(self, api_client, app_access_token):
        """TC-AUTH-008: 短信验证码 — 手机号格式错误"""
        resp = api_client.post(
            _url("/api/v1/auth/sms/send", app_access_token),
            {},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_sms_login_success(self, api_client, tenant_default, app_access_token):
        """TC-AUTH-009: 短信验证码登录 — 成功"""
        api_client.post(
            _url("/api/v1/auth/sms/send", app_access_token),
            {"phone": "13900139000"},
            content_type="application/json",
        )
        cache.set("sms:13900139000", "123456", timeout=300)
        resp = api_client.post(
            _url("/api/v1/auth/sms/login", app_access_token),
            {"phone": "13900139000", "code": "123456"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "token" in data["data"]

    def test_sms_login_wrong_code(self, api_client, tenant_default, app_access_token):
        """TC-AUTH-010: 短信验证码登录 — 验证码错误"""
        cache.set("sms:13700137000", "123456", timeout=300)
        resp = api_client.post(
            _url("/api/v1/auth/sms/login", app_access_token),
            {"phone": "13700137000", "code": "000000"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_sms_login_expired_code(self, api_client, tenant_default, app_access_token):
        """TC-AUTH-011: 短信验证码登录 — 验证码过期"""
        resp = api_client.post(
            _url("/api/v1/auth/sms/login", app_access_token),
            {"phone": "13600136000", "code": "123456"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_sms_login_existing_user_by_username(self, api_client, tenant_default, app_access_token):
        """TC-AUTH-011b: 短信登录 — 用户名就是手机号的已存在用户"""
        phone = "13812345678"

        # 先创建一个用户，用户名就是手机号（模拟之前用该手机号作为用户名注册的用户）
        existing_user = User.objects.create(
            tenant=tenant_default,
            username=phone,  # 用户名就是手机号
            user_type="external",
            nickname="已有用户",
        )

        # 设置短信验证码
        cache.set(f"sms:{phone}", "555555", timeout=300)

        # 短信登录
        resp = api_client.post(
            _url("/api/v1/auth/sms/login", app_access_token),
            {"phone": phone, "code": "555555"},
            content_type="application/json",
        )
        data = json.loads(resp.content)

        # 应该成功登录，返回的是已有用户
        assert data["code"] == 0, f"期望成功，实际返回: {data}"
        assert data["data"]["user_id"] == existing_user.id
        assert data["data"]["is_new"] is False

    # --- 短信验证码单独验证 ---

    def test_sms_verify_success(self, api_client, app_access_token):
        """TC-AUTH-012: 短信验证码校验 — 验证码正确"""
        cache.set("sms:13800138000", "123456", timeout=300)
        resp = api_client.post(
            _url("/api/v1/auth/sms/verify", app_access_token),
            {"phone": "13800138000", "code": "123456"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["verified"] is True

    def test_sms_verify_wrong_code(self, api_client, app_access_token):
        """TC-AUTH-013: 短信验证码校验 — 验证码错误"""
        cache.set("sms:13800138000", "123456", timeout=300)
        resp = api_client.post(
            _url("/api/v1/auth/sms/verify", app_access_token),
            {"phone": "13800138000", "code": "000000"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == -10301

    def test_sms_verify_expired_code(self, api_client, app_access_token):
        """TC-AUTH-014: 短信验证码校验 — 验证码过期"""
        resp = api_client.post(
            _url("/api/v1/auth/sms/verify", app_access_token),
            {"phone": "13800138000", "code": "123456"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == -10302

    def test_sms_verify_missing_params(self, api_client, app_access_token):
        """TC-AUTH-015: 短信验证码校验 — 缺少参数"""
        resp = api_client.post(
            _url("/api/v1/auth/sms/verify", app_access_token),
            {},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == -10602


class TestSocialLogin:
    """TC-AUTH-016~017: 社交登录"""

    @override_settings(MOCK_ENABLED=True)
    def test_social_login_success(self, api_client, tenant_default, app_access_token):
        """TC-AUTH-012: 社交登录 — 成功"""
        resp = api_client.post(
            _url("/api/v1/auth/social/login", app_access_token),
            {"provider": "wechat_mp", "code": "mock_code"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "token" in data["data"]

    def test_social_login_unsupported_provider(self, api_client, tenant_default, app_access_token):
        """TC-AUTH-013: 社交登录 — 不支持的 provider"""
        resp = api_client.post(
            _url("/api/v1/auth/social/login", app_access_token),
            {"provider": "unknown", "code": "xxx"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0


class TestWechatLogin:
    """微信 code 换手机号并登录"""

    @override_settings(MOCK_ENABLED=True)
    def test_wechat_login_success_creates_user(self, api_client, tenant_default, app_access_token):
        """微信登录 — 首次登录自动创建用户"""
        resp = api_client.post(
            _url("/api/v1/auth/wechat/login", app_access_token),
            {"code": "mock_code"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0, data
        assert "token" in data["data"]
        assert "refresh_token" in data["data"]
        assert data["data"]["is_new"] is True
        assert User.objects.filter(phone="138mock_cod", tenant=tenant_default).exists()

    @override_settings(MOCK_ENABLED=True)
    def test_wechat_login_existing_user(self, api_client, tenant_default, app_access_token):
        """微信登录 — 已存在同手机号用户时直接登录"""
        User.objects.create(
            tenant=tenant_default,
            phone="13800000000",
            username="13800000000",
            user_type="external",
        )
        resp = api_client.post(
            _url("/api/v1/auth/wechat/login", app_access_token),
            {"code": "00000000"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0, data
        assert data["data"]["is_new"] is False
        assert data["data"]["username"] == "13800000000"

    @override_settings(MOCK_ENABLED=True)
    def test_wechat_login_missing_code(self, api_client, app_access_token):
        """微信登录 — 缺少 code"""
        resp = api_client.post(
            _url("/api/v1/auth/wechat/login", app_access_token),
            {},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_wechat_login_not_configured(self, api_client, app_access_token):
        """微信登录 — 应用未配置微信且非 Mock 模式"""
        resp = api_client.post(
            _url("/api/v1/auth/wechat/login", app_access_token),
            {"code": "mock_code"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    @override_settings(MOCK_ENABLED=True)
    def test_wechat_login_same_phone_across_tenants(
        self, api_client, tenant_default, tenant_b, app_b
    ):
        """微信登录 — 不同租户允许重复手机号，自动注册各自租户下的用户"""
        # 租户A 已有 username=phone=13800000000 的用户
        User.objects.create(
            tenant=tenant_default,
            phone="13800000000",
            username="13800000000",
            user_type="external",
        )
        # 租户B 应用 token 请求同一手机号 → 应成功注册租户B 下的同名用户
        token_b = create_access_token({
            "app_id": app_b.id,
            "tenant_id": app_b.tenant_id,
            "token_type": "app",
        })
        resp = api_client.post(
            _url("/api/v1/auth/wechat/login", token_b),
            {"code": "00000000"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0, data
        assert data["data"]["is_new"] is True
        assert data["data"]["username"] == "13800000000"
        # 两个租户各自存在同一手机号/用户名的用户
        assert User.objects.filter(tenant=tenant_default, username="13800000000").exists()
        assert User.objects.filter(tenant=tenant_b, username="13800000000").exists()

    def test_login_same_username_across_tenants(self, api_client, tenant_default, tenant_b, app_b):
        """密码登录 — 同名用户按租户隔离，只能登录应用所属租户下的用户"""
        for tenant in (tenant_default, tenant_b):
            u = User.objects.create(
                tenant=tenant,
                username="cross_tenant_user",
                user_type="internal",
            )
            u.set_password("pass1234")
            u.save(update_fields=["password"])
        # 租户B 应用 token 登录同名账号 → 命中租户B 的用户
        token_b = create_access_token({
            "app_id": app_b.id,
            "tenant_id": app_b.tenant_id,
            "token_type": "app",
        })
        resp = api_client.post(
            _url("/api/v1/auth/login", token_b),
            {"username": "cross_tenant_user", "password": "pass1234"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0, data
        assert data["data"]["user_id"] == User.objects.get(
            tenant=tenant_b, username="cross_tenant_user"
        ).id


class TestTokenRefresh:
    """TC-AUTH-014~016: Token 刷新"""

    def test_refresh_success(self, api_client, staff_user, app_access_token):
        """TC-AUTH-014: Token 刷新 — 成功"""
        login_resp = api_client.post(
            _url("/api/v1/auth/login", app_access_token),
            {"username": "staff_user", "password": "test1234"},
            content_type="application/json",
        )
        refresh_token = json.loads(login_resp.content)["data"]["refresh_token"]

        resp = api_client.post(
            _url("/api/v1/auth/token/refresh", app_access_token),
            {"refresh_token": refresh_token},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "token" in data["data"]
        assert "refresh_token" in data["data"]

    def test_refresh_invalid_token(self, api_client, app_access_token):
        """TC-AUTH-015: Token 刷新 — 无效 refresh_token"""
        resp = api_client.post(
            _url("/api/v1/auth/token/refresh", app_access_token),
            {"refresh_token": "invalid-uuid"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_refresh_token_rotation(self, api_client, staff_user, app_access_token):
        """TC-AUTH-016: Token 刷新 — token 轮换策略（JWT 无状态模式，旧token在有效期内仍可刷新）"""
        login_resp = api_client.post(
            _url("/api/v1/auth/login", app_access_token),
            {"username": "staff_user", "password": "test1234"},
            content_type="application/json",
        )
        refresh_token = json.loads(login_resp.content)["data"]["refresh_token"]

        resp1 = api_client.post(
            _url("/api/v1/auth/token/refresh", app_access_token),
            {"refresh_token": refresh_token},
            content_type="application/json",
        )
        assert json.loads(resp1.content)["code"] == 0

        resp2 = api_client.post(
            _url("/api/v1/auth/token/refresh", app_access_token),
            {"refresh_token": refresh_token},
            content_type="application/json",
        )
        data2 = json.loads(resp2.content)
        # JWT 模式的 refresh token 在有效期内无服务端状态，旧 token 仍可刷新
        assert data2["code"] == 0


class TestLogout:
    """TC-AUTH-017: 登出"""

    def test_logout(self, api_client, staff_auth_headers, app_access_token):
        """TC-AUTH-017: 登出成功"""
        resp = api_client.post(
            _url("/api/v1/auth/logout", app_access_token),
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0


class TestUserInfo:
    """TC-AUTH-018~020: 用户信息"""

    def test_userinfo_success(self, api_client, staff_user, staff_auth_headers, app_access_token):
        """TC-AUTH-018: 获取用户信息 — 成功"""
        resp = api_client.get(_url("/api/v1/auth/me", app_access_token), **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["username"] == "staff_user"
        assert "user_type" in data["data"]
        assert "email" in data["data"]
        assert "phone" in data["data"]
        assert "nickname" in data["data"]
        assert "status" in data["data"]

    def test_userinfo_no_token(self, api_client, app_access_token):
        """TC-AUTH-019: 获取用户信息 — 无 Token（无 Bearer Token 但仍有 access_token）"""
        resp = api_client.get(_url("/api/v1/auth/me", app_access_token))
        assert resp.status_code == 401

    def test_userinfo_invalid_token(self, api_client, invalid_token_headers, app_access_token):
        """TC-AUTH-020: 获取用户信息 — 无效 Token"""
        resp = api_client.get(_url("/api/v1/auth/me", app_access_token), **invalid_token_headers)
        assert resp.status_code == 401

    def test_userinfo_expired_token(self, api_client, expired_token_headers, app_access_token):
        """TC-AUTH-020: 获取用户信息 — Token 过期"""
        resp = api_client.get(_url("/api/v1/auth/me", app_access_token), **expired_token_headers)
        assert resp.status_code == 401


class TestUpdateUserInfo:
    """TC-AUTH-021: 修改用户信息"""

    def test_update_userinfo_success(self, api_client, staff_user, staff_auth_headers, app_access_token):
        """TC-AUTH-021: 修改用户信息 — 成功"""
        resp = api_client.put(
            _url("/api/v1/auth/me", app_access_token),
            {"nickname": "新昵称", "email": "new@test.com"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

        staff_user.refresh_from_db()
        assert staff_user.nickname == "新昵称"
        assert staff_user.email == "new@test.com"

    def test_update_userinfo_phone_duplicate(self, api_client, staff_user, tenant_default, app_access_token):
        """TC-AUTH-022: 修改用户信息 — 手机号本租户内重复"""
        other = User.objects.create_user(
            tenant=tenant_default, username="other_user",
            password="test1234", phone="13800138000", user_type="internal",
        )
        token = create_access_token({
            "user_id": staff_user.id,
            "tenant_id": staff_user.tenant_id,
            "user_type": staff_user.user_type,
        })
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
        resp = api_client.put(
            _url("/api/v1/auth/me", app_access_token),
            {"phone": "13800138000"},
            content_type="application/json",
            **headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0
        assert "已被占用" in data["message"]

    def test_update_userinfo_phone_same_user(self, api_client, staff_user, staff_auth_headers, app_access_token):
        """TC-AUTH-023: 修改用户信息 — 手机号与自己相同（不报错）"""
        staff_user.phone = "13800138000"
        staff_user.save()
        resp = api_client.put(
            _url("/api/v1/auth/me", app_access_token),
            {"phone": "13800138000"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0


class TestChangePassword:
    """TC-AUTH-022~024: 修改密码"""

    def test_change_password_success(self, api_client, staff_user, staff_auth_headers, app_access_token):
        """TC-AUTH-022: 修改密码 — 成功"""
        resp = api_client.patch(
            _url("/api/v1/auth/me/password", app_access_token),
            {"old_password": "test1234", "new_password": "newpass5678"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

        staff_user.refresh_from_db()
        assert staff_user.check_password("newpass5678")

    def test_change_password_wrong_old(self, api_client, staff_auth_headers, app_access_token):
        """TC-AUTH-023: 修改密码 — 旧密码错误"""
        resp = api_client.patch(
            _url("/api/v1/auth/me/password", app_access_token),
            {"old_password": "wrong", "new_password": "newpass5678"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_change_password_weak_new(self, api_client, staff_auth_headers, app_access_token):
        """TC-AUTH-024: 修改密码 — 新密码强度不足（过短）"""
        resp = api_client.patch(
            _url("/api/v1/auth/me/password", app_access_token),
            {"old_password": "test1234", "new_password": "123"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0


class TestPasswordResetByCode:
    """验证码重置密码（手机号从 token 解析）"""

    def test_send_pwd_code_no_phone(self, api_client, staff_user, staff_auth_headers, app_access_token):
        """发送改密验证码 — 用户未绑定手机号"""
        staff_user.phone = None
        staff_user.save(update_fields=["phone"])
        resp = api_client.post(
            _url("/api/v1/auth/sms/send/pwd", app_access_token),
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_reset_password_success(self, api_client, staff_user, staff_auth_headers, app_access_token):
        """验证码重置密码 — 成功，且旧密码失效"""
        staff_user.phone = "13800138000"
        staff_user.save(update_fields=["phone"])
        cache.set("sms:pwd:13800138000", "888888", timeout=300)

        resp = api_client.post(
            _url("/api/v1/auth/me/password/reset", app_access_token),
            {"code": "888888", "new_password": "newpass5678"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0, data

        staff_user.refresh_from_db()
        assert staff_user.check_password("newpass5678")
        # 验证码已一次性删除
        assert cache.get("sms:pwd:13800138000") is None

    def test_reset_password_wrong_code(self, api_client, staff_user, staff_auth_headers, app_access_token):
        """验证码重置密码 — 验证码错误"""
        staff_user.phone = "13800138000"
        staff_user.save(update_fields=["phone"])
        cache.set("sms:pwd:13800138000", "888888", timeout=300)

        resp = api_client.post(
            _url("/api/v1/auth/me/password/reset", app_access_token),
            {"code": "000000", "new_password": "newpass5678"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_reset_password_expired(self, api_client, staff_user, staff_auth_headers, app_access_token):
        """验证码重置密码 — 验证码过期/不存在"""
        staff_user.phone = "13800138000"
        staff_user.save(update_fields=["phone"])
        cache.delete("sms:pwd:13800138000")

        resp = api_client.post(
            _url("/api/v1/auth/me/password/reset", app_access_token),
            {"code": "888888", "new_password": "newpass5678"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_reset_password_not_bound(self, api_client, staff_user, staff_auth_headers, app_access_token):
        """验证码重置密码 — 用户未绑定手机号"""
        staff_user.phone = None
        staff_user.save(update_fields=["phone"])

        resp = api_client.post(
            _url("/api/v1/auth/me/password/reset", app_access_token),
            {"code": "888888", "new_password": "newpass5678"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_reset_password_no_auth(self, api_client, app_access_token):
        """验证码重置密码 — 无用户 token"""
        resp = api_client.post(
            _url("/api/v1/auth/me/password/reset", app_access_token),
            {"code": "888888", "new_password": "newpass5678"},
            content_type="application/json",
        )
        assert resp.status_code == 401


class TestProfile:
    """TC-AUTH-025~029: 用户资料"""

    def test_get_profile_success(self, api_client, staff_user, staff_auth_headers, app_access_token):
        """TC-AUTH-025: 获取用户资料 — 成功"""
        resp = api_client.get(_url("/api/v1/auth/me/profile", app_access_token), **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "id" in data["data"]
        assert "real_name" in data["data"]
        assert "gender" in data["data"]
        assert "bio" in data["data"]

    def test_get_profile_no_token(self, api_client, app_access_token):
        """TC-AUTH-026: 获取用户资料 — 无 Token"""
        resp = api_client.get(_url("/api/v1/auth/me/profile", app_access_token))
        assert resp.status_code == 401

    def test_update_profile_success(self, api_client, staff_user, staff_auth_headers, app_access_token):
        """TC-AUTH-027: 更新用户资料 — 成功"""
        resp = api_client.put(
            _url("/api/v1/auth/me/profile", app_access_token),
            {"real_name": "张三", "gender": "male", "bio": "测试个人简介", "company": "测试公司"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["profile_id"] > 0

        # 验证数据已持久化
        resp2 = api_client.get(_url("/api/v1/auth/me/profile", app_access_token), **staff_auth_headers)
        data2 = json.loads(resp2.content)
        assert data2["data"]["real_name"] == "张三"
        assert data2["data"]["gender"] == "male"
        assert data2["data"]["bio"] == "测试个人简介"
        assert data2["data"]["company"] == "测试公司"

    def test_update_profile_partial(self, api_client, staff_user, staff_auth_headers, app_access_token):
        """TC-AUTH-028: 更新用户资料 — 部分字段"""
        resp = api_client.put(
            _url("/api/v1/auth/me/profile", app_access_token),
            {"job_title": "高级工程师", "employee_id": "EMP001", "company": "测试公司"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

        resp2 = api_client.get(_url("/api/v1/auth/me/profile", app_access_token), **staff_auth_headers)
        data2 = json.loads(resp2.content)
        assert data2["data"]["job_title"] == "高级工程师"
        assert data2["data"]["employee_id"] == "EMP001"
        assert data2["data"]["company"] == "测试公司"

    def test_update_profile_invalid_gender(self, api_client, staff_auth_headers, app_access_token):
        """TC-AUTH-029: 更新用户资料 — 无效性别值"""
        resp = api_client.put(
            _url("/api/v1/auth/me/profile", app_access_token),
            {"gender": "unknown"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0


class TestAppAuthForAuthEndpoints:
    """TC-AUTH-030~034: 用户认证接口的 access_token 验证"""

    def test_login_missing_access_token(self, api_client):
        """TC-AUTH-030: 密码登录 — 缺少 access_token（应返回 401）"""
        resp = api_client.post(
            "/api/v1/auth/login",
            {"username": "staff_user", "password": "test1234"},
            content_type="application/json",
        )
        assert resp.status_code == 401
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_login_invalid_access_token(self, api_client):
        """TC-AUTH-031: 密码登录 — 无效 access_token"""
        resp = api_client.post(
            "/api/v1/auth/login?access_token=invalid.jwt.token",
            {"username": "staff_user", "password": "test1234"},
            content_type="application/json",
        )
        assert resp.status_code == 401
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_login_user_token_as_access_token(self, api_client, staff_user):
        """TC-AUTH-032: 密码登录 — 使用用户Token代替应用access_token（应拒绝）"""
        user_token = create_access_token({
            "user_id": staff_user.id,
            "tenant_id": staff_user.tenant_id,
            "user_type": staff_user.user_type,
        })
        resp = api_client.post(
            f"/api/v1/auth/login?access_token={user_token}",
            {"username": "staff_user", "password": "test1234"},
            content_type="application/json",
        )
        assert resp.status_code == 401
        data = json.loads(resp.content)
        assert "非应用Token" in data["message"]

    def test_login_disabled_app_access_token(self, api_client, disabled_app):
        """TC-AUTH-033: 密码登录 — 使用已禁用应用的 access_token"""
        from common.utils import create_access_token as cat
        token = cat({
            "app_id": disabled_app.id,
            "tenant_id": disabled_app.tenant_id,
            "token_type": "app",
        })
        resp = api_client.post(
            f"/api/v1/auth/login?access_token={token}",
            {"username": "staff_user", "password": "test1234"},
            content_type="application/json",
        )
        assert resp.status_code == 401
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_me_endpoint_missing_access_token(self, api_client, staff_auth_headers):
        """TC-AUTH-034: 获取用户信息 — 缺少 access_token（有Bearer Token但无access_token）"""
        resp = api_client.get("/api/v1/auth/me", **staff_auth_headers)
        assert resp.status_code == 401
        data = json.loads(resp.content)
        assert "access_token" in data["message"]
