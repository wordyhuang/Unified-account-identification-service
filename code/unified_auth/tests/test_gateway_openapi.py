import json
import time
import hmac
import hashlib
import pytest

pytestmark = pytest.mark.django_db


class TestGatewayOpenApiToken:
    """TC-GW-001~005: 获取应用 Access Token (POST /api/v1/open/token)"""

    def test_get_app_token_success(self, api_client, app):
        """TC-GW-001: 获取应用Token — 成功"""
        resp = api_client.post(
            "/api/v1/open/token",
            {"app_key": app.app_key, "app_secret": app.app_secret},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "access_token" in data["data"]
        assert data["data"]["expires_in"] == 7200

    def test_get_app_token_invalid_app_key(self, api_client):
        """TC-GW-002: 获取应用Token — 无效AppKey"""
        resp = api_client.post(
            "/api/v1/open/token",
            {"app_key": "invalid_key", "app_secret": "any_secret"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == -10501
        assert "AppKey" in data["message"] and "无效" in data["message"]

    def test_get_app_token_invalid_secret(self, api_client, app):
        """TC-GW-003: 获取应用Token — 无效AppSecret"""
        resp = api_client.post(
            "/api/v1/open/token",
            {"app_key": app.app_key, "app_secret": "wrong_secret"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_get_app_token_missing_fields(self, api_client):
        """TC-GW-004: 获取应用Token — 缺少参数"""
        resp = api_client.post(
            "/api/v1/open/token",
            {"app_key": "only_key"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_get_app_token_disabled_app(self, api_client, disabled_app):
        """TC-GW-005: 获取应用Token — 应用已禁用"""
        resp = api_client.post(
            "/api/v1/open/token",
            {"app_key": disabled_app.app_key, "app_secret": disabled_app.app_secret},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == -10501


class TestGatewayTokenVerify:
    """TC-GW-006~008: 验证用户Token (POST /api/v1/open/token/verify)"""

    def test_verify_token_success(self, api_client, app_with_all_perms, app_headers, staff_user):
        """TC-GW-006: 验证Token — 有效Token"""
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
        assert data["data"]["user_id"] == staff_user.id
        assert data["data"]["tenant_id"] == staff_user.tenant_id
        assert data["data"]["user_type"] == "internal"

    def test_verify_token_invalid(self, api_client, app_with_all_perms, app_headers):
        """TC-GW-007: 验证Token — 无效Token"""
        resp = api_client.post(
            "/api/v1/open/token/verify",
            {"token": "invalid.jwt.token"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["valid"] is False
        assert data["data"]["user_id"] is None

    def test_verify_token_no_permission(self, api_client, app, app_headers):
        """TC-GW-008: 验证Token — 应用无权限"""
        from common.utils import create_access_token

        token = create_access_token({"user_id": 1, "tenant_id": 1, "user_type": "internal"})
        resp = api_client.post(
            "/api/v1/open/token/verify",
            {"access_token": token},
            content_type="application/json",
            **app_headers,
        )
        assert resp.status_code == 403


class TestGatewayUsers:
    """TC-GW-009~020: 用户管理接口"""

    def test_list_users(self, api_client, app_with_all_perms, app_headers, staff_user):
        """TC-GW-009: 查询用户列表 — 成功"""
        resp = api_client.get("/api/v1/open/users", **app_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "users" in data["data"]
        assert "total" in data["data"]

    def test_list_users_with_filters(self, api_client, app_with_all_perms, app_headers, staff_user):
        """TC-GW-010: 查询用户列表 — 带筛选参数"""
        resp = api_client.get(
            "/api/v1/open/users?user_type=internal&status=1&keyword=staff",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_get_user_detail(self, api_client, app_with_all_perms, app_headers, staff_user):
        """TC-GW-011: 获取用户详情 — 成功"""
        resp = api_client.get(f"/api/v1/open/users/{staff_user.id}", **app_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["username"] == "staff_user"
        assert "tags" in data["data"]
        assert isinstance(data["data"]["tags"], list)

    def test_get_user_detail_not_found(self, api_client, app_with_all_perms, app_headers):
        """TC-GW-012: 获取用户详情 — 用户不存在"""
        resp = api_client.get("/api/v1/open/users/99999", **app_headers)
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_create_user_success(self, api_client, app_with_all_perms, app_headers, tenant_default):
        """TC-GW-013: 创建用户 — 成功"""
        resp = api_client.post(
            "/api/v1/open/users",
            {
                "username": "gateway_new_user",
                "password": "pass123456",
                "user_type": "internal",
                "nickname": "网关测试用户",
            },
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["username"] == "gateway_new_user"
        assert data["data"]["user_type"] == "internal"
        assert "tags" in data["data"]

    def test_create_user_duplicate_username(self, api_client, app_with_all_perms, app_headers, staff_user):
        """TC-GW-014: 创建用户 — 用户名已存在"""
        resp = api_client.post(
            "/api/v1/open/users",
            {"username": "staff_user", "password": "pass1234", "user_type": "internal"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == -10602
        assert "已存在" in data["message"]

    def test_create_user_missing_fields(self, api_client, app_with_all_perms, app_headers):
        """TC-GW-015: 创建用户 — 缺少必填字段"""
        resp = api_client.post(
            "/api/v1/open/users",
            {"username": "incomplete"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_update_user_success(self, api_client, app_with_all_perms, app_headers, staff_user):
        """TC-GW-016: 更新用户信息 — 成功"""
        resp = api_client.put(
            f"/api/v1/open/users/{staff_user.id}",
            {"nickname": "UpdatedNickname", "email": "updated@example.com"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        staff_user.refresh_from_db()
        assert staff_user.nickname == "UpdatedNickname"

    def test_update_user_phone_duplicate(self, api_client, app_with_all_perms, app_headers, tenant_default, staff_user):
        """TC-GW-017: 更新用户 — 手机号本租户重复"""
        from apps.accounts.models import User

        other_user = User.objects.create_user(
            tenant=tenant_default, username="other_user", password="test1234", phone="13900139000"
        )
        resp = api_client.put(
            f"/api/v1/open/users/{other_user.id + 1 if other_user.id == staff_user.id else staff_user.id}",
            {"phone": "13900139000"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == -10602
        assert "已被占用" in data["message"]

    def test_update_user_status(self, api_client, app_with_all_perms, app_headers, staff_user):
        """TC-GW-018: 更新用户状态 — 禁用"""
        resp = api_client.patch(
            f"/api/v1/open/users/{staff_user.id}/status",
            {"status": 0},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["status"] == 0
        assert "user_uuid" in data["data"]

    def test_update_user_status_enable(self, api_client, app_with_all_perms, app_headers, disabled_user):
        """TC-GW-019: 更新用户状态 — 启用"""
        resp = api_client.patch(
            f"/api/v1/open/users/{disabled_user.id}/status",
            {"status": 1},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["status"] == 1

    def test_update_user_status_invalid(self, api_client, app_with_all_perms, app_headers, staff_user):
        """TC-GW-020: 更新用户状态 — 无效状态值"""
        resp = api_client.patch(
            f"/api/v1/open/users/{staff_user.id}/status",
            {"status": 99},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0


class TestGatewayPermissionCheck:
    """TC-GW-021~024: 权限检查接口 (POST /api/v1/open/permissions/check)"""

    def test_check_permission_has(self, api_client, app_with_all_perms, app_headers, staff_user_role):
        """TC-GW-021: 检查权限 — 有权限"""
        resp = api_client.post(
            "/api/v1/open/permissions/check",
            {"user_id": staff_user_role.id, "permission_code": "user:read"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["has_permission"] is True
        assert "user_uuid" in data["data"]

    def test_check_permission_none(self, api_client, app_with_all_perms, app_headers, normal_user):
        """TC-GW-022: 检查权限 — 无权限"""
        resp = api_client.post(
            "/api/v1/open/permissions/check",
            {"user_id": normal_user.id, "permission_code": "nonexist:perm"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["has_permission"] is False

    def test_check_permission_invalid_user(self, api_client, app_with_all_perms, app_headers):
        """TC-GW-023: 检查权限 — 用户不存在"""
        resp = api_client.post(
            "/api/v1/open/permissions/check",
            {"user_id": 99999, "permission_code": "user:read"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_check_permission_missing_fields(self, api_client, app_with_all_perms, app_headers):
        """TC-GW-024: 检查权限 — 缺少参数"""
        resp = api_client.post(
            "/api/v1/open/permissions/check",
            {"user_id": 1},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0


class TestGatewayUserProfileByToken:
    """TC-GW-025~032: 通过Token获取/修改用户资料"""

    def test_get_profile_by_token_success(self, api_client, app_with_all_perms, app_headers, staff_user):
        """TC-GW-025: 获取用户资料 — 成功"""
        from common.utils import create_access_token

        token = create_access_token({
            "user_id": staff_user.id,
            "tenant_id": staff_user.tenant_id,
            "user_type": staff_user.user_type,
        })
        resp = api_client.get(
            "/api/v1/open/users/me/profile",
            {"access_token": token},
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["user_id"] == staff_user.id
        assert data["data"]["username"] == "staff_user"
        assert "tags" in data["data"]
        assert isinstance(data["data"]["tags"], list)

    def test_get_profile_by_token_invalid(self, api_client, app_with_all_perms, app_headers):
        """TC-GW-026: 获取用户资料 — 无效Token"""
        resp = api_client.get(
            "/api/v1/open/users/me/profile",
            {"access_token": "invalid.jwt.token"},
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_get_profile_by_token_disabled_user(self, api_client, app_with_all_perms, app_headers, disabled_user):
        """TC-GW-027: 获取用户资料 — 用户已禁用"""
        from common.utils import create_access_token

        token = create_access_token({
            "user_id": disabled_user.id,
            "tenant_id": disabled_user.tenant_id,
            "user_type": disabled_user.user_type,
        })
        resp = api_client.get(
            "/api/v1/open/users/me/profile",
            {"access_token": token},
            **app_headers,
        )
        assert resp.status_code == 404

    def test_update_profile_by_token_success(self, api_client, app_with_all_perms, app_headers, staff_user):
        """TC-GW-028: 修改用户资料 — 成功"""
        from common.utils import create_access_token

        token = create_access_token({
            "user_id": staff_user.id,
            "tenant_id": staff_user.tenant_id,
            "user_type": staff_user.user_type,
        })
        resp = api_client.put(
            "/api/v1/open/users/me/profile",
            {
                "access_token": token,
                "real_name": "张三",
                "gender": "male",
                "job_title": "高级工程师",
                "company": "测试公司",
                "tags": ["技术", "管理"],
            },
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["profile_id"] > 0

    def test_update_profile_by_token_invalid(self, api_client, app_with_all_perms, app_headers):
        """TC-GW-029: 修改用户资料 — 无效Token"""
        resp = api_client.put(
            "/api/v1/open/users/me/profile",
            {"access_token": "invalid.jwt.token", "real_name": "测试"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_update_profile_by_token_missing_token(self, api_client, app_with_all_perms, app_headers):
        """TC-GW-030: 修改用户资料 — 缺少Token"""
        resp = api_client.put(
            "/api/v1/open/users/me/profile",
            {"real_name": "测试"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_update_profile_partial(self, api_client, app_with_all_perms, app_headers, staff_user):
        """TC-GW-031: 修改用户资料 — 部分更新"""
        from common.utils import create_access_token
        from apps.accounts.models import UserProfile

        UserProfile.objects.create(user=staff_user, real_name="旧名字", bio="旧简介", company="旧公司")
        token = create_access_token({
            "user_id": staff_user.id,
            "tenant_id": staff_user.tenant_id,
            "user_type": staff_user.user_type,
        })
        resp = api_client.put(
            "/api/v1/open/users/me/profile",
            {"access_token": token, "real_name": "新名字"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

        profile = UserProfile.objects.get(user=staff_user)
        assert profile.real_name == "新名字"
        assert profile.bio == "旧简介"
        assert profile.company == "旧公司"

    def test_get_profile_no_permission(self, api_client, app, app_headers, staff_user):
        """TC-GW-032: 获取用户资料 — 应用无权限"""
        from common.utils import create_access_token

        token = create_access_token({
            "user_id": staff_user.id,
            "tenant_id": staff_user.tenant_id,
            "user_type": staff_user.user_type,
        })
        resp = api_client.get(
            "/api/v1/open/users/me/profile",
            {"access_token": token},
            **app_headers,
        )
        assert resp.status_code == 403


class TestGatewayWechatApi:
    """TC-GW-033~038: 微信小程序辅助接口"""

    def test_get_wechat_access_token_not_configured(self, api_client, app_with_all_perms, app_headers):
        """TC-GW-033: 获取微信AccessToken — 未配置"""
        resp = api_client.get("/api/v1/open/wechat/access_token", **app_headers)
        data = json.loads(resp.content)
        assert data["code"] == -10801

    def test_get_wechat_access_token_no_permission(self, api_client, app, app_headers):
        """TC-GW-034: 获取微信AccessToken — 无权限"""
        resp = api_client.get("/api/v1/open/wechat/access_token", **app_headers)
        assert resp.status_code == 403

    def test_get_wechat_phone_not_configured(self, api_client, app_with_all_perms, app_headers):
        """TC-GW-035: 获取微信手机号 — 未配置"""
        resp = api_client.post(
            "/api/v1/open/wechat/phone",
            {"code": "mock_code"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == -10801

    def test_get_wechat_phone_missing_code(self, api_client, app_with_all_perms, app_headers):
        """TC-GW-036: 获取微信手机号 — 缺少参数"""
        resp = api_client.post(
            "/api/v1/open/wechat/phone",
            {},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_get_wechat_phone_no_permission(self, api_client, app, app_headers):
        """TC-GW-037: 获取微信手机号 — 无权限"""
        resp = api_client.post(
            "/api/v1/open/wechat/phone",
            {"code": "mock_code"},
            content_type="application/json",
            **app_headers,
        )
        assert resp.status_code == 403


class TestGatewayAuthApi:
    """TC-GW-039~050: 用户认证接口"""

    def test_password_login_success(self, api_client, app_access_token, staff_user):
        """TC-GW-039: 密码登录 — 成功"""
        resp = api_client.post(
            f"/api/v1/auth/login?access_token={app_access_token}",
            {"username": "staff_user", "password": "test1234"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "token" in data["data"]
        assert "refresh_token" in data["data"]
        assert data["data"]["user_id"] == staff_user.id

    def test_password_login_wrong_password(self, api_client, app_access_token, staff_user):
        """TC-GW-040: 密码登录 — 密码错误"""
        resp = api_client.post(
            f"/api/v1/auth/login?access_token={app_access_token}",
            {"username": "staff_user", "password": "wrong_pass"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == -10602
        assert "密码错误" in data["message"]

    def test_password_login_user_not_found(self, api_client, app_access_token):
        """TC-GW-041: 密码登录 — 用户不存在"""
        resp = api_client.post(
            f"/api/v1/auth/login?access_token={app_access_token}",
            {"username": "nonexist", "password": "test1234"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == -10101

    def test_password_login_disabled_user(self, api_client, app_access_token, disabled_user):
        """TC-GW-042: 密码登录 — 用户已禁用"""
        resp = api_client.post(
            f"/api/v1/auth/login?access_token={app_access_token}",
            {"username": "disabled_user", "password": "test1234"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == -10102
        assert "已被禁用" in data["message"]

    def test_sms_send_success(self, api_client, app_access_token):
        """TC-GW-043: 发送短信验证码 — 成功"""
        resp = api_client.post(
            f"/api/v1/auth/sms/send?access_token={app_access_token}",
            {"phone": "13800138000"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["phone"] == "13800138000"

    def test_sms_send_missing_phone(self, api_client, app_access_token):
        """TC-GW-044: 发送短信验证码 — 缺少手机号"""
        resp = api_client.post(
            f"/api/v1/auth/sms/send?access_token={app_access_token}",
            {},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_sms_login_success(self, api_client, app_access_token, tenant_default):
        """TC-GW-045: 短信登录 — 成功（新建外部用户）"""
        from django.core.cache import cache

        cache.set("sms:13800138000", "123456", timeout=300)
        resp = api_client.post(
            f"/api/v1/auth/sms/login?access_token={app_access_token}",
            {"phone": "13800138000", "code": "123456"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "token" in data["data"]
        assert "refresh_token" in data["data"]
        assert data["data"]["is_new"] is True

    def test_sms_login_wrong_code(self, api_client, app_access_token, tenant_default):
        """TC-GW-046: 短信登录 — 验证码错误"""
        from django.core.cache import cache

        cache.set("sms:13800138000", "123456", timeout=300)
        resp = api_client.post(
            f"/api/v1/auth/sms/login?access_token={app_access_token}",
            {"phone": "13800138000", "code": "654321"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == -10301

    def test_sms_verify_success(self, api_client, app_access_token, tenant_default):
        """TC-GW-057: 短信验证码验证 — 成功"""
        from django.core.cache import cache

        cache.set("sms:13800138000", "123456", timeout=300)
        resp = api_client.post(
            f"/api/v1/auth/sms/verify?access_token={app_access_token}",
            {"phone": "13800138000", "code": "123456"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["verified"] is True

    def test_sms_verify_wrong_code(self, api_client, app_access_token, tenant_default):
        """TC-GW-058: 短信验证码验证 — 验证码错误"""
        from django.core.cache import cache

        cache.set("sms:13800138000", "123456", timeout=300)
        resp = api_client.post(
            f"/api/v1/auth/sms/verify?access_token={app_access_token}",
            {"phone": "13800138000", "code": "654321"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == -10301

    def test_sms_verify_expired(self, api_client, app_access_token, tenant_default):
        """TC-GW-059: 短信验证码验证 — 验证码已过期"""
        resp = api_client.post(
            f"/api/v1/auth/sms/verify?access_token={app_access_token}",
            {"phone": "13800138001", "code": "123456"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == -10302
        assert "已过期" in data["message"]

    def test_sms_verify_missing_fields(self, api_client, app_access_token):
        """TC-GW-060: 短信验证码验证 — 缺少参数"""
        resp = api_client.post(
            f"/api/v1/auth/sms/verify?access_token={app_access_token}",
            {"phone": "13800138000"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_refresh_token_success(self, api_client, app_access_token, staff_user):
        """TC-GW-047: 刷新Token — 成功"""
        # 先登录获取 refresh_token
        login_resp = api_client.post(
            f"/api/v1/auth/login?access_token={app_access_token}",
            {"username": "staff_user", "password": "test1234"},
            content_type="application/json",
        )
        refresh_token = json.loads(login_resp.content)["data"]["refresh_token"]

        resp = api_client.post(
            f"/api/v1/auth/token/refresh?access_token={app_access_token}",
            {"refresh_token": refresh_token},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "token" in data["data"]
        assert "refresh_token" in data["data"]

    def test_refresh_token_invalid(self, api_client, app_access_token):
        """TC-GW-048: 刷新Token — 无效Token"""
        resp = api_client.post(
            f"/api/v1/auth/token/refresh?access_token={app_access_token}",
            {"refresh_token": "invalid_refresh_token"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_get_auth_userinfo(self, api_client, app_access_token, staff_auth_headers):
        """TC-GW-049: 获取当前用户信息 — 成功"""
        resp = api_client.get(f"/api/v1/auth/me?access_token={app_access_token}", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["username"] == "staff_user"
        assert "tags" in data["data"]

    def test_update_auth_me(self, api_client, app_access_token, staff_auth_headers, staff_user):
        """TC-GW-051: 更新当前用户信息 — 成功"""
        resp = api_client.put(
            f"/api/v1/auth/me?access_token={app_access_token}",
            {"nickname": "NewNickname", "email": "new@example.com"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        staff_user.refresh_from_db()
        assert staff_user.nickname == "NewNickname"

    def test_change_password_success(self, api_client, app_access_token, staff_auth_headers):
        """TC-GW-052: 修改密码 — 成功"""
        resp = api_client.patch(
            f"/api/v1/auth/me/password?access_token={app_access_token}",
            {"old_password": "test1234", "new_password": "newpass1234"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_change_password_wrong_old(self, api_client, app_access_token, staff_auth_headers):
        """TC-GW-053: 修改密码 — 原密码错误"""
        resp = api_client.patch(
            f"/api/v1/auth/me/password?access_token={app_access_token}",
            {"old_password": "wrong_pass", "new_password": "newpass1234"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == -10602
        assert "原密码错误" in data["message"]

    def test_get_auth_me_profile(self, api_client, app_access_token, staff_auth_headers):
        """TC-GW-054: 获取用户资料 — 成功"""
        resp = api_client.get(f"/api/v1/auth/me/profile?access_token={app_access_token}", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "id" in data["data"]
        assert "tags" in data["data"]

    def test_update_auth_me_profile(self, api_client, app_access_token, staff_auth_headers):
        """TC-GW-055: 更新用户资料 — 成功"""
        resp = api_client.put(
            f"/api/v1/auth/me/profile?access_token={app_access_token}",
            {"real_name": "张三", "gender": "male", "job_title": "工程师", "company": "测试公司"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "profile_id" in data["data"]

    def test_logout(self, api_client, app_access_token, staff_auth_headers):
        """TC-GW-056: 登出 — 成功"""
        resp = api_client.post(f"/api/v1/auth/logout?access_token={app_access_token}", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0