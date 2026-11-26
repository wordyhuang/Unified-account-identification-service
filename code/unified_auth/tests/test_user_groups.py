"""用户组与应用准入控制测试。

覆盖：判定函数、管理端接口、Token 中间件、刷新令牌、邀请码自动入组。
对应方案：document/用户组与应用准入控制方案_v1.0.md
"""

import json

import pytest

from apps.accounts.models import User
from apps.applications.models import Application
from apps.invites.models import InviteCode, generate_code, generate_short_code
from apps.users.access import (
    REASON_GROUP_DENIED,
    REASON_GROUP_EXTERNAL_DENIED,
    REASON_GROUP_MATCHED,
    REASON_LEGACY_DENIED,
    REASON_LEGACY_EXPLICIT,
    REASON_LEGACY_TYPE_MATCH,
    REASON_OPEN_TYPE_MATCH,
    evaluate_app_access,
)
from apps.users.models import AppGroupBinding, UserAppAccess, UserGroup, UserGroupMember
from common.utils import create_access_token, decode_access_token, generate_refresh_token


pytestmark = pytest.mark.django_db


# ==================== 公共夹具 ====================


@pytest.fixture
def internal_app(tenant_default):
    return Application.objects.create(
        tenant=tenant_default,
        name="内部应用",
        app_key="group_app_key_001",
        app_secret="group_app_secret",
        default_access_user_types=["internal"],
    )


@pytest.fixture
def open_app(tenant_default):
    return Application.objects.create(
        tenant=tenant_default,
        name="开放应用",
        app_key="group_app_key_open",
        app_secret="group_app_secret",
        default_access_user_types=["internal", "external"],
    )


@pytest.fixture
def group_a(tenant_default):
    return UserGroup.objects.create(tenant=tenant_default, name="财务组", code="finance")


@pytest.fixture
def group_b(tenant_default):
    return UserGroup.objects.create(tenant=tenant_default, name="审计组", code="audit")


def _bind(app, group):
    return AppGroupBinding.objects.create(app=app, group=group)


def _join(group, user):
    return UserGroupMember.objects.create(group=group, user=user)


def _app_token(user, app):
    token = create_access_token({
        "user_id": user.id,
        "tenant_id": user.tenant_id,
        "user_type": user.user_type,
        "app_id": app.id,
    })
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def _app_level_token(app):
    """应用级 Token：/api/v1/auth/* 要求 URL 携带 access_token。"""
    return create_access_token({
        "app_id": app.id,
        "tenant_id": app.tenant_id,
        "token_type": "app",
    })


def _me_url(app):
    return f"/api/v1/auth/me?access_token={_app_level_token(app)}"


# ==================== 判定函数 ====================


class TestEvaluateAccess:
    def test_legacy_type_match_when_no_binding(self, internal_app, normal_user):
        allowed, reason, gid = evaluate_app_access(normal_user, internal_app)
        assert allowed is True
        assert reason == REASON_LEGACY_TYPE_MATCH
        assert gid is None

    def test_legacy_denied_for_type_mismatch(self, internal_app, external_user):
        allowed, reason, _ = evaluate_app_access(external_user, internal_app)
        assert allowed is False
        assert reason == REASON_LEGACY_DENIED

    def test_legacy_explicit_access(self, internal_app, external_user):
        UserAppAccess.objects.create(user=external_user, app=internal_app, status="active")
        allowed, reason, _ = evaluate_app_access(external_user, internal_app)
        assert allowed is True
        assert reason == REASON_LEGACY_EXPLICIT

    def test_group_mode_denies_non_member(self, internal_app, group_a, normal_user):
        _bind(internal_app, group_a)
        allowed, reason, gid = evaluate_app_access(normal_user, internal_app)
        assert allowed is False
        assert reason == REASON_GROUP_DENIED
        assert gid is None

    def test_group_mode_allows_member(self, internal_app, group_a, normal_user):
        _bind(internal_app, group_a)
        _join(group_a, normal_user)
        allowed, reason, gid = evaluate_app_access(normal_user, internal_app)
        assert allowed is True
        assert reason == REASON_GROUP_MATCHED
        assert gid == group_a.id

    def test_group_mode_ignores_explicit_access(
        self, internal_app, group_a, normal_user
    ):
        _bind(internal_app, group_a)
        UserAppAccess.objects.create(user=normal_user, app=internal_app, status="active")
        allowed, reason, _ = evaluate_app_access(normal_user, internal_app)
        assert allowed is False
        assert reason == REASON_GROUP_DENIED

    def test_group_mode_multi_group_or(self, internal_app, group_a, group_b, normal_user):
        _bind(internal_app, group_a)
        _bind(internal_app, group_b)
        _join(group_b, normal_user)
        allowed, reason, gid = evaluate_app_access(normal_user, internal_app)
        assert allowed is True
        assert gid == group_b.id

    def test_group_mode_denies_external_user(self, internal_app, group_a, external_user):
        _bind(internal_app, group_a)
        _join(group_a, external_user)
        allowed, reason, _ = evaluate_app_access(external_user, internal_app)
        assert allowed is False
        assert reason == REASON_GROUP_EXTERNAL_DENIED

    def test_open_app_ignores_group(self, open_app, group_a, normal_user):
        _bind(open_app, group_a)
        allowed, reason, _ = evaluate_app_access(normal_user, open_app)
        assert allowed is True
        assert reason == REASON_OPEN_TYPE_MATCH

    def test_bound_group_disabled_denies(self, internal_app, group_a, normal_user):
        _bind(internal_app, group_a)
        _join(group_a, normal_user)
        group_a.status = False
        group_a.save(update_fields=["status"])
        allowed, reason, _ = evaluate_app_access(normal_user, internal_app)
        assert allowed is False
        assert reason == REASON_GROUP_DENIED

    def test_cross_tenant_denied(self, internal_app, user_b):
        allowed, reason, _ = evaluate_app_access(user_b, internal_app)
        assert allowed is False


# ==================== Token 中间件 ====================


class TestTokenMiddleware:
    def test_group_non_member_gets_403(self, api_client, internal_app, group_a, normal_user):
        _bind(internal_app, group_a)
        resp = api_client.get(_me_url(internal_app), **_app_token(normal_user, internal_app))
        assert resp.status_code == 403

    def test_group_member_passes(self, api_client, internal_app, group_a, normal_user):
        _bind(internal_app, group_a)
        _join(group_a, normal_user)
        resp = api_client.get(_me_url(internal_app), **_app_token(normal_user, internal_app))
        assert resp.status_code == 200

    def test_open_app_passes_without_group(self, api_client, open_app, group_a, normal_user):
        _bind(open_app, group_a)
        resp = api_client.get(_me_url(open_app), **_app_token(normal_user, open_app))
        assert resp.status_code == 200

    def test_refresh_keeps_app_context(self, api_client, internal_app, group_a, normal_user):
        _bind(internal_app, group_a)
        refresh_token = generate_refresh_token({
            "user_id": normal_user.id,
            "tenant_id": normal_user.tenant_id,
            "user_type": normal_user.user_type,
            "app_id": internal_app.id,
        })
        resp = api_client.post(
            "/api/v1/auth/token/refresh",
            {"refresh_token": refresh_token},
            content_type="application/json",
        )
        assert resp.status_code == 200
        new_token = json.loads(resp.content)["data"]["token"]
        payload = decode_access_token(new_token)
        assert payload.get("app_id") == internal_app.id

        # 刷新后的 token 仍受组约束
        me = api_client.get(
            _me_url(internal_app), HTTP_AUTHORIZATION=f"Bearer {new_token}"
        )
        assert me.status_code == 403


# ==================== 用户组管理接口 ====================


class TestUserGroupAdminAPI:
    def test_create_and_list(self, api_client, staff_auth_headers):
        resp = api_client.post(
            "/api/v1/admin/user-groups",
            {"name": "财务组", "code": "finance", "description": "财务人员"},
            content_type="application/json",
            **staff_auth_headers,
        )
        assert resp.status_code == 201
        group_id = json.loads(resp.content)["data"]["id"]

        listing = api_client.get("/api/v1/admin/user-groups", **staff_auth_headers)
        body = json.loads(listing.content)
        assert body["code"] == 0
        assert body["data"]["total"] == 1
        assert body["data"]["items"][0]["id"] == group_id

    def test_duplicate_name_rejected(self, api_client, staff_auth_headers, group_a):
        resp = api_client.post(
            "/api/v1/admin/user-groups",
            {"name": group_a.name},
            content_type="application/json",
            **staff_auth_headers,
        )
        assert resp.status_code == 400

    def test_update_and_delete(self, api_client, staff_auth_headers, group_a):
        resp = api_client.patch(
            f"/api/v1/admin/user-groups/{group_a.id}",
            {"name": "财务中心", "status": False},
            content_type="application/json",
            **staff_auth_headers,
        )
        assert resp.status_code == 200
        group_a.refresh_from_db()
        assert group_a.name == "财务中心"
        assert group_a.status is False

        deleted = api_client.delete(
            f"/api/v1/admin/user-groups/{group_a.id}", **staff_auth_headers
        )
        assert deleted.status_code == 200
        assert not UserGroup.objects.filter(id=group_a.id).exists()

    def test_members_replace(self, api_client, staff_auth_headers, group_a, normal_user):
        resp = api_client.put(
            f"/api/v1/admin/user-groups/{group_a.id}/members",
            {"user_ids": [normal_user.id]},
            content_type="application/json",
            **staff_auth_headers,
        )
        assert resp.status_code == 200
        body = json.loads(resp.content)
        assert body["data"]["added"] == [normal_user.id]

        listing = api_client.get(
            f"/api/v1/admin/user-groups/{group_a.id}/members", **staff_auth_headers
        )
        items = json.loads(listing.content)["data"]["items"]
        assert len(items) == 1
        assert items[0]["user_id"] == normal_user.id

    def test_members_cross_tenant_rejected(
        self, api_client, staff_auth_headers, group_a, user_b
    ):
        resp = api_client.put(
            f"/api/v1/admin/user-groups/{group_a.id}/members",
            {"user_ids": [user_b.id]},
            content_type="application/json",
            **staff_auth_headers,
        )
        assert resp.status_code == 400


# ==================== 应用绑组与诊断 ====================


class TestAppGroupAdminAPI:
    def test_bind_and_serialize(self, api_client, staff_auth_headers, internal_app, group_a):
        resp = api_client.put(
            f"/api/v1/admin/applications/{internal_app.id}/groups",
            {"group_ids": [group_a.id]},
            content_type="application/json",
            **staff_auth_headers,
        )
        assert resp.status_code == 200
        body = json.loads(resp.content)["data"]
        assert body["group_ids"] == [group_a.id]
        assert body["group_mode"] is True

        listing = api_client.get("/api/v1/admin/applications", **staff_auth_headers)
        apps = json.loads(listing.content)["data"]["apps"]
        target = [a for a in apps if a["id"] == internal_app.id][0]
        assert target["group_ids"] == [group_a.id]
        assert target["group_mode"] is True

    def test_bind_cross_tenant_group_rejected(
        self, api_client, staff_auth_headers, internal_app, tenant_b
    ):
        foreign = UserGroup.objects.create(tenant=tenant_b, name="外部组")
        resp = api_client.put(
            f"/api/v1/admin/applications/{internal_app.id}/groups",
            {"group_ids": [foreign.id]},
            content_type="application/json",
            **staff_auth_headers,
        )
        assert resp.status_code == 400

    def test_bind_limit(self, api_client, staff_auth_headers, internal_app, tenant_default):
        groups = [
            UserGroup.objects.create(tenant=tenant_default, name=f"组{i}")
            for i in range(21)
        ]
        resp = api_client.put(
            f"/api/v1/admin/applications/{internal_app.id}/groups",
            {"group_ids": [g.id for g in groups]},
            content_type="application/json",
            **staff_auth_headers,
        )
        assert resp.status_code == 400

    def test_diagnosis_allowed_and_denied(
        self, api_client, staff_auth_headers, internal_app, group_a, normal_user
    ):
        _bind(internal_app, group_a)
        url = (
            f"/api/v1/admin/applications/{internal_app.id}/access-diagnosis"
            f"?user_id={normal_user.id}"
        )
        denied = json.loads(api_client.get(url, **staff_auth_headers).content)["data"]
        assert denied["allowed"] is False
        assert denied["matched_group"] is None

        _join(group_a, normal_user)
        allowed = json.loads(api_client.get(url, **staff_auth_headers).content)["data"]
        assert allowed["allowed"] is True
        assert allowed["matched_group"]["id"] == group_a.id


# ==================== 邀请码自动入组 ====================


def _make_invite(tenant, app, **kwargs):
    return InviteCode.objects.create(
        tenant=tenant,
        code=generate_code(32),
        short_code=generate_short_code(8),
        user_type=kwargs.pop("user_type", "internal"),
        app=app,
        **kwargs,
    )


# ==================== 审计日志 ====================


class TestAudit:
    def test_group_members_and_binding_audited(
        self, api_client, staff_auth_headers, internal_app, group_a, normal_user
    ):
        from apps.audit.models import AuditLog

        api_client.put(
            f"/api/v1/admin/user-groups/{group_a.id}/members",
            {"user_ids": [normal_user.id]},
            content_type="application/json",
            **staff_auth_headers,
        )
        api_client.put(
            f"/api/v1/admin/applications/{internal_app.id}/groups",
            {"group_ids": [group_a.id]},
            content_type="application/json",
            **staff_auth_headers,
        )
        actions = set(
            AuditLog.objects.filter(tenant_id=internal_app.tenant_id)
            .values_list("action", flat=True)
        )
        assert "admin.user_group.members_update" in actions
        assert "admin.app.groups_update" in actions


# ==================== 邀请码自动入组 ====================


def _make_invite(tenant, app, **kwargs):
    return InviteCode.objects.create(
        tenant=tenant,
        code=generate_code(32),
        short_code=generate_short_code(8),
        user_type=kwargs.pop("user_type", "internal"),
        app=app,
        **kwargs,
    )


class TestInviteAutoGroup:
    def test_requires_auto_group_when_app_in_group_mode(
        self, api_client, staff_auth_headers, internal_app, group_a
    ):
        _bind(internal_app, group_a)
        resp = api_client.post(
            "/api/v1/admin/invite-codes",
            {"app_id": internal_app.id, "user_type": "internal", "max_uses": 5},
            content_type="application/json",
            **staff_auth_headers,
        )
        assert resp.status_code == 400

    def test_auto_group_must_be_bound_to_app(
        self, api_client, staff_auth_headers, internal_app, group_a, group_b
    ):
        _bind(internal_app, group_a)
        resp = api_client.post(
            "/api/v1/admin/invite-codes",
            {
                "app_id": internal_app.id,
                "user_type": "internal",
                "max_uses": 5,
                "auto_group_ids": [group_b.id],
            },
            content_type="application/json",
            **staff_auth_headers,
        )
        assert resp.status_code == 400

    def test_create_with_auto_group(
        self, api_client, staff_auth_headers, internal_app, group_a
    ):
        _bind(internal_app, group_a)
        resp = api_client.post(
            "/api/v1/admin/invite-codes",
            {
                "app_id": internal_app.id,
                "user_type": "internal",
                "max_uses": 5,
                "auto_group_ids": [group_a.id],
            },
            content_type="application/json",
            **staff_auth_headers,
        )
        assert resp.status_code == 200
        assert json.loads(resp.content)["data"]["auto_group_ids"] == [group_a.id]

    def test_external_invite_not_required(
        self, api_client, staff_auth_headers, internal_app, group_a
    ):
        _bind(internal_app, group_a)
        resp = api_client.post(
            "/api/v1/admin/invite-codes",
            {"app_id": internal_app.id, "user_type": "external", "max_uses": 5},
            content_type="application/json",
            **staff_auth_headers,
        )
        assert resp.status_code == 200

    def test_register_joins_auto_group(self, api_client, tenant_default, internal_app, group_a):
        _bind(internal_app, group_a)
        invite = _make_invite(
            tenant_default, internal_app, auto_group_ids=[group_a.id]
        )
        resp = api_client.post(
            f"/api/v1/public/invite/{invite.code}/register",
            {"username": "group_user", "password": "pass123456"},
            content_type="application/json",
        )
        assert json.loads(resp.content)["code"] == 0
        user = User.objects.get(tenant=tenant_default, username="group_user")
        assert UserGroupMember.objects.filter(group=group_a, user=user).exists()
        # 注册后可直接通过该应用准入
        allowed, _, _ = evaluate_app_access(user, internal_app)
        assert allowed is True
