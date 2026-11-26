"""自助凭证码（邀请码/资料补全码）与强制改密策略测试。"""
import json
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.accounts.models import User, UserProfile
from apps.invites.models import InviteCode, ProfileCompletionCode


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    """每个用例开始时清空缓存，避免限流计数器跨用例累积。"""
    cache.clear()


@pytest.fixture
def invite_code(tenant_default):
    return InviteCode.objects.create(
        tenant=tenant_default,
        code="a" * 32,
        short_code="abc12345",
        remark="研发团队",
        allowed_phones=None,
        user_type="external",
    )


@pytest.fixture
def whitelist_code(tenant_default):
    return InviteCode.objects.create(
        tenant=tenant_default,
        code="b" * 32,
        short_code="bcd23456",
        allowed_phones=["13800000001", "13800000002"],
        user_type="external",
    )


@pytest.fixture
def expired_code(tenant_default):
    return InviteCode.objects.create(
        tenant=tenant_default,
        code="c" * 32,
        short_code="cde34567",
        expires_at=timezone.now() - timedelta(hours=1),
    )


@pytest.fixture
def exhausted_code(tenant_default):
    return InviteCode.objects.create(
        tenant=tenant_default,
        code="d" * 32,
        short_code="def45678",
        max_uses=1,
        used_count=1,
    )


# ==================== 邀请码：管理端 ====================


class TestInviteCodeAdmin:
    def test_create_invite_code(self, api_client, staff_auth_headers, tenant_default):
        resp = api_client.post(
            "/api/v1/admin/invite-codes",
            {"remark": "团队邀请", "allowed_phones": ["13800000003"], "user_type": "external"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["code"] and len(data["data"]["code"]) == 32
        assert data["data"]["short_code"]
        assert "/s/" in data["data"]["short_url"]
        assert "/invite/" in data["data"]["page_url"]
        assert data["data"]["allowed_phones"] == ["13800000003"]

    def test_create_invite_code_invalid_phones(self, api_client, staff_auth_headers):
        resp = api_client.post(
            "/api/v1/admin/invite-codes",
            {"allowed_phones": "not-a-list"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == -10602

    def test_list_invite_codes(self, api_client, staff_auth_headers, invite_code):
        resp = api_client.get(
            "/api/v1/admin/invite-codes", **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["total"] >= 1

    def test_disable_invite_code(self, api_client, staff_auth_headers, invite_code):
        resp = api_client.patch(
            f"/api/v1/admin/invite-codes/{invite_code.id}",
            {"status": 0},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        invite_code.refresh_from_db()
        assert invite_code.status == 0

    def test_patch_invite_code_config(self, api_client, staff_auth_headers, invite_code):
        """配置可修改：备注/白名单/次数/有效期/用户类型，并支持清除有效期。"""
        resp = api_client.patch(
            f"/api/v1/admin/invite-codes/{invite_code.id}",
            {
                "remark": "新备注",
                "allowed_phones": ["13800001111", "13800001112"],
                "max_uses": 50,
                "user_type": "internal",
                "expires_at": "2027-01-01T00:00:00",
            },
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        invite_code.refresh_from_db()
        assert invite_code.remark == "新备注"
        assert invite_code.allowed_phones == ["13800001111", "13800001112"]
        assert invite_code.max_uses == 50
        assert invite_code.user_type == "internal"
        assert invite_code.expires_at is not None

        # 清除有效期（传 null）
        resp = api_client.patch(
            f"/api/v1/admin/invite-codes/{invite_code.id}",
            {"expires_at": None},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        invite_code.refresh_from_db()
        assert invite_code.expires_at is None

    def test_patch_invite_max_uses_below_used_count(self, api_client, staff_auth_headers, invite_code):
        invite_code.used_count = 5
        invite_code.save(update_fields=["used_count"])
        resp = api_client.patch(
            f"/api/v1/admin/invite-codes/{invite_code.id}",
            {"max_uses": 3},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == -10602

    def test_patch_invite_invalid_phones(self, api_client, staff_auth_headers, invite_code):
        resp = api_client.patch(
            f"/api/v1/admin/invite-codes/{invite_code.id}",
            {"allowed_phones": "bad-format"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == -10602


# ==================== 邀请码：公开 API ====================


class TestInvitePublic:
    def test_invite_info(self, api_client, invite_code):
        resp = api_client.get(f"/api/v1/public/invite/{invite_code.code}")
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["require_phone"] is False
        assert data["data"]["user_type"] == "external"

    def test_register_success(self, api_client, invite_code, tenant_default):
        resp = api_client.post(
            f"/api/v1/public/invite/{invite_code.code}/register",
            {"username": "invited_user", "password": "pass123456", "nickname": "受邀人"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

        user = User.objects.get(tenant=tenant_default, username="invited_user")
        assert user.user_type == "external"
        assert user.check_password("pass123456")
        invite_code.refresh_from_db()
        assert invite_code.used_count == 1

    def test_register_whitelist_miss(self, api_client, whitelist_code):
        resp = api_client.post(
            f"/api/v1/public/invite/{whitelist_code.code}/register",
            {"phone": "13999999999", "username": "outsider", "password": "pass123456"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == -10704
        assert not User.objects.filter(username="outsider").exists()

    def test_register_whitelist_hit(self, api_client, whitelist_code, tenant_default):
        resp = api_client.post(
            f"/api/v1/public/invite/{whitelist_code.code}/register",
            {"phone": "13800000001", "username": "invited2", "password": "pass123456"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        user = User.objects.get(tenant=tenant_default, username="invited2")
        assert user.phone == "13800000001"

    def test_register_duplicate_username(self, api_client, invite_code, normal_user):
        resp = api_client.post(
            f"/api/v1/public/invite/{invite_code.code}/register",
            {"username": normal_user.username, "password": "pass123456"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == -10602

    def test_expired_code_rejected(self, api_client, expired_code):
        resp = api_client.get(f"/api/v1/public/invite/{expired_code.code}")
        data = json.loads(resp.content)
        assert data["code"] == -10702

    def test_exhausted_code_rejected(self, api_client, exhausted_code):
        resp = api_client.get(f"/api/v1/public/invite/{exhausted_code.code}")
        data = json.loads(resp.content)
        assert data["code"] == -10703

    def test_disabled_code_rejected(self, api_client, invite_code):
        invite_code.status = 0
        invite_code.save(update_fields=["status"])
        resp = api_client.get(f"/api/v1/public/invite/{invite_code.code}")
        data = json.loads(resp.content)
        assert data["code"] == -10701

    def test_short_link_redirect_invite(self, api_client, invite_code):
        resp = api_client.get(f"/s/{invite_code.short_code}")
        assert resp.status_code == 302
        assert f"/invite/{invite_code.code}" in resp["Location"]


# ==================== 资料补全码：管理端 ====================


class TestCompletionCodeAdmin:
    def test_create_single_mode(self, api_client, staff_auth_headers, normal_user):
        resp = api_client.post(
            "/api/v1/admin/profile-completion-codes",
            {"mode": "single", "user_id": normal_user.id, "fields": ["real_name", "job_title"]},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["mode"] == "single"
        assert data["data"]["username"] == normal_user.username
        assert data["data"]["field_labels"] == ["真实姓名", "职位"]

    def test_create_single_mode_requires_user(self, api_client, staff_auth_headers):
        resp = api_client.post(
            "/api/v1/admin/profile-completion-codes",
            {"mode": "single", "fields": ["real_name"]},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == -10601

    def test_create_rejects_unknown_field(self, api_client, staff_auth_headers, normal_user):
        resp = api_client.post(
            "/api/v1/admin/profile-completion-codes",
            {"mode": "single", "user_id": normal_user.id, "fields": ["id_card"]},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == -10602

    def test_create_shared_mode(self, api_client, staff_auth_headers):
        resp = api_client.post(
            "/api/v1/admin/profile-completion-codes",
            {"mode": "shared", "fields": ["real_name", "wechat"], "max_uses": 10},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["mode"] == "shared"

    def test_patch_single_code_config(self, api_client, staff_auth_headers, single_code):
        """单人模式配置可修改：字段/允许多次/次数上限/有效期。"""
        resp = api_client.patch(
            f"/api/v1/admin/profile-completion-codes/{single_code.id}",
            {
                "fields": ["real_name", "wechat"],
                "allow_repeated": True,
                "max_uses": 5,
                "expires_at": "2027-01-01T00:00:00",
            },
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        single_code.refresh_from_db()
        assert single_code.fields == ["real_name", "wechat"]
        assert single_code.allow_repeated is True
        assert single_code.max_uses == 5
        assert single_code.expires_at is not None

    def test_patch_single_code_rebind_user(self, api_client, staff_auth_headers, tenant_default, single_code, normal_user):
        """单人模式支持换绑同租户用户。"""
        other = User.objects.create(
            tenant=tenant_default, username="rebind_target", user_type="external"
        )
        other.set_password("pass123456")
        other.save(update_fields=["password"])
        resp = api_client.patch(
            f"/api/v1/admin/profile-completion-codes/{single_code.id}",
            {"user_id": other.id},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["username"] == "rebind_target"
        single_code.refresh_from_db()
        assert single_code.user_id == other.id

    def test_patch_mode_immutable(self, api_client, staff_auth_headers, single_code):
        """创建后 mode 不可变更。"""
        resp = api_client.patch(
            f"/api/v1/admin/profile-completion-codes/{single_code.id}",
            {"mode": "shared"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == -10602

    def test_patch_invalid_fields(self, api_client, staff_auth_headers, single_code):
        resp = api_client.patch(
            f"/api/v1/admin/profile-completion-codes/{single_code.id}",
            {"fields": ["id_card"]},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == -10602

    def test_patch_max_uses_below_used_count(self, api_client, staff_auth_headers, single_code):
        single_code.used_count = 3
        single_code.save(update_fields=["used_count"])
        resp = api_client.patch(
            f"/api/v1/admin/profile-completion-codes/{single_code.id}",
            {"max_uses": 2},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == -10602


# ==================== 资料补全码：公开 API（单人模式） ====================


@pytest.fixture
def single_code(tenant_default, normal_user):
    return ProfileCompletionCode.objects.create(
        tenant=tenant_default,
        user=normal_user,
        code="e" * 32,
        short_code="efg56789",
        mode="single",
        fields=["real_name", "job_title", "nickname"],
    )


class TestCompletionSingle:
    def test_info_with_prefill(self, api_client, single_code, normal_user):
        resp = api_client.get(f"/api/v1/public/profile-completion/{single_code.code}")
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["mode"] == "single"
        assert data["data"]["prefill"]["nickname"] == normal_user.nickname

    def test_submit_updates_profile_and_consumes_code(self, api_client, single_code, normal_user):
        resp = api_client.put(
            f"/api/v1/public/profile-completion/{single_code.code}/submit",
            {"real_name": "张三", "job_title": "工程师", "nickname": "三哥"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

        normal_user.refresh_from_db()
        assert normal_user.nickname == "三哥"
        profile = UserProfile.objects.get(user=normal_user)
        assert profile.real_name == "张三"
        assert profile.job_title == "工程师"

        single_code.refresh_from_db()
        assert single_code.status == 0

    def test_allow_repeated_keeps_code_active(self, api_client, tenant_default, normal_user):
        code = ProfileCompletionCode.objects.create(
            tenant=tenant_default,
            user=normal_user,
            code="f" * 32,
            short_code="fgh67890",
            mode="single",
            fields=["job_title"],
            allow_repeated=True,
        )
        for title in ("工程师", "高级工程师"):
            resp = api_client.put(
                f"/api/v1/public/profile-completion/{code.code}/submit",
                {"job_title": title},
                content_type="application/json",
            )
            assert json.loads(resp.content)["code"] == 0
        code.refresh_from_db()
        assert code.status == 1
        assert code.used_count == 2

    def test_submit_rejects_unknown_field(self, api_client, single_code):
        resp = api_client.put(
            f"/api/v1/public/profile-completion/{single_code.code}/submit",
            {"id_card": "123"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == -10602


# ==================== 资料补全码：公开 API（多人通用模式） ====================


@pytest.fixture
def shared_code(tenant_default):
    return ProfileCompletionCode.objects.create(
        tenant=tenant_default,
        code="0" * 32,
        short_code="ghi78901",
        mode="shared",
        fields=["real_name", "wechat"],
        max_uses=5,
    )


@pytest.fixture
def phone_user(tenant_default):
    return User.objects.create_user(
        tenant=tenant_default,
        username="phone_user",
        password="test1234",
        phone="13800000011",
        user_type="internal",
    )


class TestCompletionShared:
    def test_info_requires_verify(self, api_client, shared_code):
        resp = api_client.get(f"/api/v1/public/profile-completion/{shared_code.code}")
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["mode"] == "shared"
        assert "prefill" not in data["data"]

    def test_verify_rejects_unknown_phone(self, api_client, shared_code):
        resp = api_client.post(
            f"/api/v1/public/profile-completion/{shared_code.code}/verify",
            {"phone": "13999990000"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == -10101

    def test_verify_rejected_for_single_mode(self, api_client, single_code):
        resp = api_client.post(
            f"/api/v1/public/profile-completion/{single_code.code}/verify",
            {"phone": "13800000011"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == -10602

    def test_verify_and_login_and_submit(self, api_client, shared_code, phone_user):
        # 1. 发送验证码（mock 短信渠道）
        resp = api_client.post(
            f"/api/v1/public/profile-completion/{shared_code.code}/verify",
            {"phone": phone_user.phone},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

        # 2. 从缓存读取验证码并登录，签发受限会话
        sms_code = cache.get(f"sms:pc:{shared_code.code}:{phone_user.phone}")
        assert sms_code
        resp = api_client.post(
            f"/api/v1/public/profile-completion/{shared_code.code}/login",
            {"phone": phone_user.phone, "sms_code": sms_code},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        session_token = data["data"]["session_token"]
        assert data["data"]["prefill"] is not None

        # 3. 携带会话凭证提交补全
        resp = api_client.put(
            f"/api/v1/public/profile-completion/{shared_code.code}/submit",
            {"real_name": "李四", "wechat": "lisi_wx"},
            content_type="application/json",
            HTTP_X_COMPLETION_TOKEN=session_token,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

        phone_user.refresh_from_db()
        profile = UserProfile.objects.get(user=phone_user)
        assert profile.real_name == "李四"
        assert profile.wechat == "lisi_wx"

        shared_code.refresh_from_db()
        assert shared_code.used_count == 1
        assert shared_code.status == 1  # 未达上限，仍可用

    def test_submit_without_session_rejected(self, api_client, shared_code):
        resp = api_client.put(
            f"/api/v1/public/profile-completion/{shared_code.code}/submit",
            {"real_name": "王五"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == -10705

    def test_submit_with_wrong_session_rejected(self, api_client, shared_code):
        resp = api_client.put(
            f"/api/v1/public/profile-completion/{shared_code.code}/submit",
            {"real_name": "王五"},
            content_type="application/json",
            HTTP_X_COMPLETION_TOKEN="fake-token",
        )
        data = json.loads(resp.content)
        assert data["code"] == -10705

    def test_short_link_redirect_completion(self, api_client, shared_code):
        resp = api_client.get(f"/s/{shared_code.short_code}")
        assert resp.status_code == 302
        assert f"/profile-completion/{shared_code.code}" in resp["Location"]


# ==================== 强制改密闭环 ====================


def _auth_url(path, token):
    """auth 接口需追加应用级 access_token 查询参数"""
    sep = "&" if "?" in path else "?"
    return f"{path}{sep}access_token={token}"


class TestMustChangePassword:
    def test_login_returns_flag(self, api_client, staff_user, tenant_default, app_access_token):
        resp = api_client.post(
            _auth_url("/api/v1/auth/login", app_access_token),
            {"username": "staff_user", "password": "test1234"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["must_change_password"] is False

    def test_full_interception_after_admin_reset(self, api_client, staff_auth_headers, normal_user, app, app_access_token):
        # 管理员重置密码
        resp = api_client.post(
            f"/api/v1/admin/users/{normal_user.id}/reset-password",
            content_type="application/json",
            **staff_auth_headers,
        )
        new_password = json.loads(resp.content)["data"]["password"]

        # 登录成功但返回强制改密标志
        resp = api_client.post(
            _auth_url("/api/v1/auth/login", app_access_token),
            {"username": normal_user.username, "password": new_password},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["must_change_password"] is True
        token = data["data"]["token"]
        auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        # 白名单外路径被拦截（403 PASSWORD_CHANGE_REQUIRED）
        resp = api_client.get(_auth_url("/api/v1/auth/me/profile", app_access_token), **auth)
        data = json.loads(resp.content)
        assert resp.status_code == 403
        assert data["code"] == -10104

        # 白名单内路径放行：修改密码
        resp = api_client.patch(
            _auth_url("/api/v1/auth/me/password", app_access_token),
            {"old_password": new_password, "new_password": "brandnew123"},
            content_type="application/json",
            **auth,
        )
        assert json.loads(resp.content)["code"] == 0

        # 改密后标志清除，路径放行
        resp = api_client.get(_auth_url("/api/v1/auth/me/profile", app_access_token), **auth)
        assert resp.status_code == 200

        normal_user.refresh_from_db()
        assert normal_user.must_change_password is False
        assert normal_user.check_password("brandnew123")

    def test_old_password_invalid_after_reset(self, api_client, staff_auth_headers, normal_user, app_access_token):
        api_client.post(
            f"/api/v1/admin/users/{normal_user.id}/reset-password",
            content_type="application/json",
            **staff_auth_headers,
        )
        resp = api_client.post(
            _auth_url("/api/v1/auth/login", app_access_token),
            {"username": normal_user.username, "password": "test1234"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] != 0


# ==================== 邀请码防刷策略 ====================


class TestInviteAntiAbuse:
    def test_create_default_max_uses(self, api_client, staff_auth_headers):
        """未传 max_uses 时后端强制默认 10，杜绝不限次数邀请码。"""
        resp = api_client.post(
            "/api/v1/admin/invite-codes",
            {"remark": "默认次数"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["max_uses"] == 10

    def test_create_max_uses_range(self, api_client, staff_auth_headers):
        """max_uses 超出 1-1000 范围时拒绝。"""
        for value in (0, 2000):
            resp = api_client.post(
                "/api/v1/admin/invite-codes",
                {"max_uses": value},
                content_type="application/json",
                **staff_auth_headers,
            )
            data = json.loads(resp.content)
            assert data["code"] == -10602

    def test_register_ip_rate_limit(self, api_client, invite_code):
        """同一 IP 每分钟最多 3 次注册尝试（含失败），超出返回 -10401。"""
        for i in range(3):
            resp = api_client.post(
                f"/api/v1/public/invite/{invite_code.code}/register",
                {"username": f"rate_user_{i}", "password": "pass123456"},
                content_type="application/json",
            )
            data = json.loads(resp.content)
            assert data["code"] == 0
        resp = api_client.post(
            f"/api/v1/public/invite/{invite_code.code}/register",
            {"username": "rate_user_3", "password": "pass123456"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert resp.status_code == 429
        assert data["code"] == -10401
        assert not User.objects.filter(username="rate_user_3").exists()

    def test_register_daily_limit_per_code(self, api_client, invite_code):
        """单个邀请码每日成功注册达到上限后返回 -10401。"""
        from django.conf import settings as dj_settings
        from apps.invites.views import _invite_daily_key

        cache.set(
            _invite_daily_key(invite_code.id),
            dj_settings.INVITE_REGISTER_CODE_DAILY_LIMIT,
            90000,
        )
        resp = api_client.post(
            f"/api/v1/public/invite/{invite_code.code}/register",
            {"username": "daily_user", "password": "pass123456"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert resp.status_code == 429
        assert data["code"] == -10401
        assert not User.objects.filter(username="daily_user").exists()

    def test_daily_limit_not_shared_across_codes(self, api_client, invite_code, whitelist_code, tenant_default):
        """每日上限按码隔离：A 码达上限不影响 B 码。"""
        from django.conf import settings as dj_settings
        from apps.invites.views import _invite_daily_key

        cache.set(_invite_daily_key(invite_code.id), dj_settings.INVITE_REGISTER_CODE_DAILY_LIMIT, 90000)
        resp = api_client.post(
            f"/api/v1/public/invite/{whitelist_code.code}/register",
            {"username": "other_code_user", "phone": "13800000001", "password": "pass123456"},
            content_type="application/json",
        )
        data = json.loads(resp.content)
        assert data["code"] == 0


# ==================== 码级页面外观 ====================


class TestAppearanceResolve:
    """resolve_appearance 字段级回退链与校验。"""

    def test_code_level_overrides_tenant_level(self, tenant_default):
        from apps.invites.appearance import resolve_appearance

        class FakeCode:
            appearance = {"theme_color": "#1E40AF", "title": "码级标题"}

        result = resolve_appearance(FakeCode(), tenant_default, "invite")
        assert result["theme_color"] == "#1E40AF"
        assert result["title"] == "码级标题"
        # 未配置项回退租户默认
        assert result["welcome"] == tenant_default.invite_welcome or result["welcome"] == ""

    def test_field_level_fallback_to_tenant(self, tenant_default):
        from apps.invites.appearance import resolve_appearance

        tenant_default.invite_theme_color = "#0F766E"
        tenant_default.save()

        class FakeCode:
            appearance = {"theme_color": "#1E40AF"}

        result = resolve_appearance(FakeCode(), tenant_default, "invite")
        # 码级已配置
        assert result["theme_color"] == "#1E40AF"
        # 码级未配置 → 租户默认或系统内置
        assert result["button_text"] == "注册账号"

    def test_tenant_title_fallback_to_tenant_name(self, tenant_default):
        """邀请页标题回退链：品牌名称 > 企业名称 > 系统默认。"""
        from apps.invites.appearance import resolve_appearance

        class FakeCode:
            appearance = None

        result = resolve_appearance(FakeCode(), tenant_default, "invite")
        assert result["title"] == "默认企业"

    def test_system_defaults_by_page_type(self, tenant_default):
        from apps.invites.appearance import resolve_appearance

        class FakeCode:
            appearance = None

        invite_r = resolve_appearance(FakeCode(), None, "invite")
        completion_r = resolve_appearance(FakeCode(), None, "completion")
        assert invite_r["button_text"] == "注册账号"
        assert completion_r["button_text"] == "提交资料"
        assert invite_r["title"] == "账号邀请注册"
        assert completion_r["title"] == "资料补全"

    def test_illegal_keys_filtered(self, tenant_default):
        from apps.invites.appearance import normalize_appearance

        out, err = normalize_appearance({"theme_color": "#112233", "hacked": "<script>"})
        assert err is None
        assert "hacked" not in out
        assert out["theme_color"] == "#112233"

    def test_invalid_color_rejected(self):
        from apps.invites.appearance import normalize_appearance

        out, err = normalize_appearance({"theme_color": "red"})
        assert out is None
        assert "theme_color" in err

    def test_invalid_image_rejected(self):
        from apps.invites.appearance import normalize_appearance

        out, err = normalize_appearance({"logo": "http://insecure.com/x.png"})
        assert out is None
        assert "logo" in err

    def test_empty_value_deletes_key(self):
        from apps.invites.appearance import normalize_appearance

        out, err = normalize_appearance({"theme_color": "", "title": "  ", "welcome": None, "button_text": "提交"})
        assert err is None
        assert "theme_color" not in out and "title" not in out and "welcome" not in out
        assert out["button_text"] == "提交"

    def test_clear_returns_none(self):
        from apps.invites.appearance import normalize_appearance

        out, err = normalize_appearance(None)
        assert out is None and err is None


class TestAppearanceAdminAPI:
    """码级外观管理接口。"""

    def test_create_with_appearance(self, api_client, staff_auth_headers):
        resp = api_client.post(
            "/api/v1/admin/invite-codes",
            {"remark": "外观码", "appearance": {"theme_color": "#1E40AF", "button_text": "加入我们"}},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["appearance"]["theme_color"] == "#1E40AF"
        assert data["data"]["appearance"]["button_text"] == "加入我们"
        # 未配置项回退租户/系统默认
        assert data["data"]["appearance_effective"]["theme_color"] == "#1E40AF"

    def test_create_default_appearance_null(self, api_client, staff_auth_headers):
        resp = api_client.post(
            "/api/v1/admin/invite-codes", {"remark": "无外观"},
            content_type="application/json", **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["data"]["appearance"] is None

    def test_patch_appearance_and_clear(self, api_client, staff_auth_headers, invite_code):
        # 设置
        resp = api_client.patch(
            f"/api/v1/admin/invite-codes/{invite_code.id}",
            {"appearance": {"theme_color": "#1E40AF", "logo": "https://cdn.example.com/logo.png"}},
            content_type="application/json", **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["appearance"]["theme_color"] == "#1E40AF"

        # 清除（null）→ 回退默认
        resp = api_client.patch(
            f"/api/v1/admin/invite-codes/{invite_code.id}",
            {"appearance": None},
            content_type="application/json", **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["data"]["appearance"] is None
        assert data["data"]["appearance_effective"]["theme_color"] != "#1E40AF"

    def test_patch_appearance_empty_dict(self, api_client, staff_auth_headers, invite_code):
        resp = api_client.patch(
            f"/api/v1/admin/invite-codes/{invite_code.id}",
            {"appearance": {}},
            content_type="application/json", **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["data"]["appearance"] == {}
        # {} 与 null 渲染结果一致：全部走默认
        assert data["data"]["appearance_effective"]["button_text"] in ("注册账号", "")

    def test_patch_invalid_appearance_rejected(self, api_client, staff_auth_headers, invite_code):
        resp = api_client.patch(
            f"/api/v1/admin/invite-codes/{invite_code.id}",
            {"appearance": {"theme_color": "not-a-color"}},
            content_type="application/json", **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert resp.status_code == 400
        assert "theme_color" in data["message"]

    def test_completion_create_with_appearance(self, api_client, staff_auth_headers, normal_user):
        resp = api_client.post(
            "/api/v1/admin/profile-completion-codes",
            {"mode": "single", "user_id": normal_user.id, "fields": ["nickname"],
             "appearance": {"theme_color": "#059669", "button_text": "完善资料"}},
            content_type="application/json", **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["appearance"]["button_text"] == "完善资料"
        assert data["data"]["appearance_effective"]["button_text"] == "完善资料"

    def test_appearance_audit_log_contains_changes(self, api_client, staff_auth_headers, tenant_default, invite_code):
        resp = api_client.patch(
            f"/api/v1/admin/invite-codes/{invite_code.id}",
            {"appearance": {"theme_color": "#1E40AF"}},
            content_type="application/json", **staff_auth_headers,
        )
        assert json.loads(resp.content)["code"] == 0
        from apps.audit.models import AuditLog
        log = AuditLog.objects.filter(
            action="admin.invite_code.update", resource_id=invite_code.id
        ).latest("id")
        assert "appearance" in log.detail["changed"]
        assert "theme_color:+" in log.detail["appearance_changed"]


class TestAppearancePreview:
    """外观预览接口与预览页。"""

    def test_preview_returns_token_and_effective(self, api_client, staff_auth_headers, tenant_default):
        tenant_default.invite_theme_color = "#0F766E"
        tenant_default.save()
        resp = api_client.post(
            "/api/v1/admin/invite-appearance/preview",
            {"page_type": "invite", "appearance": {"theme_color": "#1E40AF"}},
            content_type="application/json", **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["appearance_effective"]["theme_color"] == "#1E40AF"
        # 码级未配置的项回退租户默认
        assert data["data"]["appearance_effective"]["welcome"] == ""
        assert data["data"]["preview_token"].startswith("pv_")

    def test_preview_page_renders_and_token_reusable(self, api_client, staff_auth_headers):
        resp = api_client.post(
            "/api/v1/admin/invite-appearance/preview",
            {"page_type": "completion", "appearance": {"button_text": "完善资料", "footer_text": "示例页脚"}},
            content_type="application/json", **staff_auth_headers,
        )
        token = json.loads(resp.content)["data"]["preview_token"]

        # 抽屉 iframe 与「新窗口完整预览」共享同一 token，TTL 内可重复访问
        page1 = api_client.get(f"/appearance-preview/{token}")
        assert page1.status_code == 200
        assert "完善资料".encode() in page1.content
        assert "示例页脚".encode() in page1.content

        page2 = api_client.get(f"/appearance-preview/{token}")
        assert page2.status_code == 200

    def test_preview_invalid_token_404(self, api_client):
        assert api_client.get("/appearance-preview/pv_notexist").status_code == 404

    def test_preview_invalid_page_type(self, api_client, staff_auth_headers):
        resp = api_client.post(
            "/api/v1/admin/invite-appearance/preview",
            {"page_type": "other", "appearance": {}},
            content_type="application/json", **staff_auth_headers,
        )
        assert resp.status_code == 400


class TestAppearancePublic:
    """公开接口下发解析后外观。"""

    def test_invite_info_brand_uses_resolved_title(self, api_client, invite_code, tenant_default):
        resp = api_client.get(f"/api/v1/public/invite/{invite_code.code}")
        data = json.loads(resp.content)
        assert data["code"] == 0
        # brand.name 兼容旧结构，取解析后标题（租户名回退）
        assert data["data"]["brand"]["name"] == "默认企业"
        # appearance 含全部 7 个键
        appearance = data["data"]["appearance"]
        assert set(appearance.keys()) == {
            "logo", "title", "welcome", "theme_color",
            "background", "button_text", "footer_text",
        }
        assert appearance["button_text"] == "注册账号"

    def test_invite_info_code_level_appearance(self, api_client, tenant_default):
        code = InviteCode.objects.create(
            tenant=tenant_default, code="e" * 32, short_code="efg45678",
            appearance={"theme_color": "#1E40AF", "button_text": "加入我们", "footer_text": "内部系统"},
        )
        resp = api_client.get(f"/api/v1/public/invite/{code.code}")
        data = json.loads(resp.content)["data"]
        assert data["appearance"]["theme_color"] == "#1E40AF"
        assert data["appearance"]["button_text"] == "加入我们"
        assert data["texts"]["submit"] == "加入我们"
        assert data["brand"]["theme_color"] == "#1E40AF"

    def test_completion_info_contains_appearance(self, api_client, tenant_default, normal_user):
        code = ProfileCompletionCode.objects.create(
            tenant=tenant_default, user=normal_user, code="f" * 32, short_code="fgh56789",
            mode="single", fields=["nickname"],
            appearance={"theme_color": "#059669", "footer_text": "HR 系统"},
        )
        resp = api_client.get(f"/api/v1/public/profile-completion/{code.code}")
        data = json.loads(resp.content)["data"]
        assert data["appearance"]["theme_color"] == "#059669"
        assert data["appearance"]["footer_text"] == "HR 系统"
        assert data["appearance"]["button_text"] == "提交资料"

    def test_xss_text_rendered_as_text_in_preview(self, api_client, staff_auth_headers):
        resp = api_client.post(
            "/api/v1/admin/invite-appearance/preview",
            {"page_type": "invite", "appearance": {"footer_text": "<script>alert(1)</script>"}},
            content_type="application/json", **staff_auth_headers,
        )
        token = json.loads(resp.content)["data"]["preview_token"]
        page = api_client.get(f"/appearance-preview/{token}")
        assert page.status_code == 200
        assert b"<script>alert(1)</script>" not in page.content  # 已转义
        assert b"&lt;script&gt;" in page.content
