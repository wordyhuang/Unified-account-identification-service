import json
import time
import hmac
import hashlib
import pytest


pytestmark = pytest.mark.django_db


class TestVerifyToken:
    """TC-OPEN-001~003: 验证 Token"""

    def test_verify_valid_token(self, api_client, app_with_all_perms, app_headers, staff_user):
        """TC-OPEN-001: 验证 Token — 有效 Token"""
        from common.utils import create_access_token
        token = create_access_token({
            "user_id": staff_user.id,
            "tenant_id": staff_user.tenant_id,
            "user_type": staff_user.user_type,
        })
        resp = api_client.post(
            "/api/v1/open/verify_token",
            {"token": token},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["valid"] is True
        assert data["data"]["user_id"] == staff_user.id
        assert data["data"]["tenant_id"] == staff_user.tenant_id

    def test_verify_invalid_token(self, api_client, app_with_all_perms, app_headers):
        """TC-OPEN-002: 验证 Token — 无效 Token"""
        resp = api_client.post(
            "/api/v1/open/verify_token",
            {"token": "invalid.jwt.token"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["valid"] is False

    def test_verify_missing_headers(self, api_client):
        """TC-OPEN-003: 验证 Token — 缺少请求头"""
        resp = api_client.post(
            "/api/v1/open/verify_token",
            {"token": "xxx"},
            content_type="application/json",
        )
        assert resp.status_code == 401


class TestOpenUsers:
    """TC-OPEN-004~012: 开放 API 用户管理"""

    def test_list_users(self, api_client, staff_user, app_with_all_perms, app_headers):
        """TC-OPEN-004: 查询用户列表"""
        resp = api_client.get("/api/v1/open/users", **app_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "users" in data["data"]

    def test_list_users_filter(self, api_client, staff_user, app_with_all_perms, app_headers):
        """TC-OPEN-005: 查询用户列表 — 筛选参数"""
        resp = api_client.get(
            "/api/v1/open/users?user_type=internal&status=1&keyword=staff",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "users" in data["data"]

    def test_create_user_success(self, api_client, app_with_all_perms, app_headers, tenant_default):
        """TC-OPEN-008: 创建用户 — 成功"""
        resp = api_client.post(
            "/api/v1/open/users",
            {"username": "open_new_user", "password": "pass1234", "user_type": "internal"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["username"] == "open_new_user"

    def test_create_user_duplicate(self, api_client, app_with_all_perms, app_headers, staff_user):
        """TC-OPEN-009: 创建用户 — 用户名已存在"""
        resp = api_client.post(
            "/api/v1/open/users",
            {"username": "staff_user", "password": "pass1234", "user_type": "internal"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_create_user_missing_fields(self, api_client, app_with_all_perms, app_headers):
        """TC-OPEN-010: 创建用户 — 缺少必填字段"""
        resp = api_client.post(
            "/api/v1/open/users",
            {"username": "incomplete_user"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_get_user_detail(self, api_client, staff_user, app_with_all_perms, app_headers):
        """TC-OPEN-006: 获取用户详情"""
        resp = api_client.get(f"/api/v1/open/users/{staff_user.id}", **app_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["username"] == "staff_user"

    def test_get_user_detail_not_found(self, api_client, app_with_all_perms, app_headers):
        """TC-OPEN-007: 获取用户详情 — 不存在"""
        resp = api_client.get("/api/v1/open/users/99999", **app_headers)
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_update_user(self, api_client, staff_user, app_with_all_perms, app_headers):
        """TC-OPEN-011: 修改用户信息"""
        resp = api_client.put(
            f"/api/v1/open/users/{staff_user.id}",
            {"nickname": "open_updated"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

        staff_user.refresh_from_db()
        assert staff_user.nickname == "open_updated"

    def test_toggle_user_status(self, api_client, staff_user, app_with_all_perms, app_headers):
        """TC-OPEN-012: 启用/禁用用户"""
        resp = api_client.patch(
            f"/api/v1/open/users/{staff_user.id}/status",
            {"status": 0},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["status"] == 0

        resp = api_client.patch(
            f"/api/v1/open/users/{staff_user.id}/status",
            {"status": 1},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["status"] == 1


class TestCheckPermission:
    """TC-OPEN-013~014: 校验权限"""

    def test_check_permission_has_perm(self, api_client, app_with_all_perms, app_headers,
                                        staff_user_role):
        """TC-OPEN-013: 校验权限 — 有权限"""
        resp = api_client.post(
            "/api/v1/open/check_permission",
            {"user_id": staff_user_role.id, "permission_code": "user:read"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["has_permission"] is True

    def test_check_permission_no_perm(self, api_client, app_with_all_perms, app_headers,
                                       normal_user):
        """TC-OPEN-014: 校验权限 — 无权限"""
        resp = api_client.post(
            "/api/v1/open/check_permission",
            {"user_id": normal_user.id, "permission_code": "nonexist:perm"},
            content_type="application/json",
            **app_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["has_permission"] is False


class TestOpenApiAuth:
    """TC-OPEN-015~019: 开放 API 认证"""

    def test_wrong_signature(self, api_client, app):
        """TC-OPEN-015: 开放 API — 签名错误"""
        bad_headers = {
            "HTTP_X_APP_KEY": app.app_key,
            "HTTP_X_TIMESTAMP": str(int(time.time())),
            "HTTP_X_SIGNATURE": "deadbeef",
        }
        resp = api_client.get("/api/v1/open/users", **bad_headers)
        assert resp.status_code == 401

    def test_missing_app_key(self, api_client):
        """TC-OPEN-016: 开放 API — 缺少 AppKey"""
        resp = api_client.get("/api/v1/open/users")
        assert resp.status_code == 401

    def test_expired_timestamp(self, api_client, app):
        """TC-OPEN-017: 开放 API — 时间戳防重放"""
        old_ts = str(int(time.time()) - 600)
        body_str = json.dumps({}, ensure_ascii=False, separators=(",", ":"))
        message = f"{body_str}{old_ts}"
        signature = hmac.new(
            app.app_secret_hash.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        expired_headers = {
            "HTTP_X_APP_KEY": app.app_key,
            "HTTP_X_TIMESTAMP": old_ts,
            "HTTP_X_SIGNATURE": signature,
        }
        resp = api_client.get("/api/v1/open/users", **expired_headers)
        assert resp.status_code == 401

    def test_disabled_app(self, api_client, disabled_app):
        """TC-OPEN-018: 开放 API — 应用已禁用"""
        timestamp = str(int(time.time()))
        body_str = json.dumps({}, ensure_ascii=False, separators=(",", ":"))
        message = f"{body_str}{timestamp}"
        signature = hmac.new(
            disabled_app.app_secret_hash.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "HTTP_X_APP_KEY": disabled_app.app_key,
            "HTTP_X_TIMESTAMP": timestamp,
            "HTTP_X_SIGNATURE": signature,
        }
        resp = api_client.get("/api/v1/open/users", **headers)
        assert resp.status_code == 401

    def test_no_permission(self, api_client, app, app_headers):
        """TC-OPEN-019: 开放 API — 无接口权限（应用未绑定权限码）"""
        resp = api_client.get("/api/v1/open/users", **app_headers)
        assert resp.status_code == 403