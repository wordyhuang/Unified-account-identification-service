"""回调地址职责分离测试：callback_urls 仅供 OAuth2，cors_origins 管 CORS 与页面对接信任基准。"""

import pytest
from django.test import override_settings

from apps.applications.models import Application
from apps.invites.services import url_allowed_for_app

pytestmark = pytest.mark.django_db


@pytest.fixture
def split_app(tenant_default):
    app = Application.objects.create(
        tenant=tenant_default,
        name="拆分测试应用",
        app_key="split-test-key",
        app_secret="split-test-secret",
        callback_urls=["https://oauth.example.com/callback"],
        cors_origins=["https://pages.example.com"],
    )
    return app


class TestCallbackFieldSeparation:
    @override_settings(DEBUG=True)
    def test_url_allowed_for_app_uses_cors_origins(self, split_app):
        """页面对接/Webhook 信任基准是 cors_origins，与 callback_urls 无关。"""
        assert url_allowed_for_app(split_app, "https://pages.example.com/webhook")
        assert not url_allowed_for_app(split_app, "https://oauth.example.com/other")

    def test_oauth_redirect_still_uses_callback_urls(self, split_app):
        """OAuth2 redirect_uri 白名单仍是 callback_urls。"""
        from apps.oauth2.utils import validate_redirect_uri

        assert validate_redirect_uri(split_app, "https://oauth.example.com/callback")
        assert not validate_redirect_uri(split_app, "https://pages.example.com/callback")

    @override_settings(DEBUG=True)
    def test_dynamic_cors_uses_cors_origins(self, split_app):
        """CORS 白名单来自 cors_origins 与注册页地址，不含 callback_urls 的 origin。"""
        from middlewares.dynamic_cors import allowed_origins

        origins = allowed_origins()
        assert "https://pages.example.com" in origins
        assert "https://oauth.example.com" not in origins

    @override_settings(DEBUG=True)
    def test_admin_create_with_cors_origins(self, api_client, staff_auth_headers):
        """创建应用可分别配置两个白名单，注册页地址按 cors_origins 同源校验。"""
        resp = api_client.post(
            "/api/v1/admin/applications",
            {
                "name": "拆分创建",
                "callback_urls": ["https://oauth.example.com/callback"],
                "cors_origins": ["https://pages.example.com"],
                "registration_page_url": "https://pages.example.com/register",
            },
            content_type="application/json",
            **staff_auth_headers,
        )
        assert resp.status_code == 201, resp.content
        data = resp.json()["data"]
        assert data["callback_urls"] == ["https://oauth.example.com/callback"]
        assert data["cors_origins"] == ["https://pages.example.com"]

    def test_admin_create_page_url_must_match_cors_origins(self, api_client, staff_auth_headers):
        """注册页地址与 cors_origins 不同源时拒绝（即使 callback_urls 同源）。"""
        resp = api_client.post(
            "/api/v1/admin/applications",
            {
                "name": "跨源拒绝",
                "callback_urls": ["https://pages.example.com/callback"],
                "registration_page_url": "https://pages.example.com/register",
            },
            content_type="application/json",
            **staff_auth_headers,
        )
        assert resp.status_code == 400

    @override_settings(DEBUG=True)
    def test_admin_update_cors_origins(self, api_client, staff_auth_headers, split_app):
        """编辑应用可更新 cors_origins。"""
        resp = api_client.put(
            f"/api/v1/admin/applications/{split_app.id}",
            {"name": "拆分测试应用", "cors_origins": ["https://new.example.com"]},
            content_type="application/json",
            **staff_auth_headers,
        )
        assert resp.status_code == 200, resp.content
        split_app.refresh_from_db()
        assert split_app.cors_origins == ["https://new.example.com"]
        # 旧 cors_origins 移除后，原同源地址不再放行
        assert not url_allowed_for_app(split_app, "https://pages.example.com/webhook")
