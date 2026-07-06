import json
import hashlib
import pytest
from django.test import Client
from apps.applications.models import Application
from urllib.parse import urlparse, parse_qs


ORIGINAL_OAUTH_SECRET = "my_oauth_secret_key"


class TestOAuth2:
    def test_authorize_missing_params(self, api_client):
        resp = api_client.get("/oauth/authorize")
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_authorize_invalid_app(self, api_client):
        resp = api_client.get(
            "/oauth/authorize?app_id=999&redirect_uri=http://example.com/callback&response_type=code"
        )
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_authorize_redirect_uri_not_in_whitelist(self, api_client, app):
        resp = api_client.get(
            f"/oauth/authorize?app_id={app.id}&redirect_uri=http://evil.com/hack&response_type=code"
        )
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_authorize_redirect_to_login(self, api_client, app):
        app.callback_urls = ["http://example.com/callback"]
        app.save()
        resp = api_client.get(
            f"/oauth/authorize?app_id={app.id}&redirect_uri=http://example.com/callback&response_type=code"
        )
        assert resp.status_code == 302

    def test_token_exchange_wrong_grant_type(self, api_client):
        resp = api_client.post(
            "/oauth/token",
            {"grant_type": "password", "code": "xxx"},
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    @pytest.mark.django_db
    def test_token_exchange_invalid_code(self, api_client, app):
        resp = api_client.post(
            "/oauth/token",
            {"grant_type": "authorization_code", "code": "invalid",
             "app_id": app.id, "app_secret": "test_secret",
             "redirect_uri": "http://example.com/callback"},
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    @pytest.mark.django_db
    def test_full_oauth2_flow(self, api_client, app, staff_user):
        """完整 OAuth2 授权码流程"""
        app.callback_urls = ["http://example.com/callback"]
        app.app_secret = ORIGINAL_OAUTH_SECRET
        app.save()

        api_client.force_login(staff_user)

        resp = api_client.get(
            f"/oauth/authorize?app_id={app.id}"
            f"&redirect_uri=http://example.com/callback"
            f"&response_type=code&state=test_state_123"
        )

        resp = api_client.post("/oauth/authorize/confirm")
        assert resp.status_code == 302

        callback_url = resp["Location"]
        parsed = urlparse(callback_url)
        params = parse_qs(parsed.query)
        assert "code" in params
        assert params["state"][0] == "test_state_123"

        code = params["code"][0]

        resp = api_client.post(
            "/oauth/token",
            {"grant_type": "authorization_code", "code": code,
             "app_id": app.id, "app_secret": ORIGINAL_OAUTH_SECRET,
             "redirect_uri": "http://example.com/callback"},
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
        assert data["data"]["user_id"] == staff_user.id

    @pytest.mark.django_db
    def test_oauth2_code_one_time_use(self, api_client, app, staff_user):
        """OAuth2 授权码一次性使用"""
        app.callback_urls = ["http://example.com/callback"]
        app.app_secret = ORIGINAL_OAUTH_SECRET
        app.save()
        api_client.force_login(staff_user)

        api_client.get(
            f"/oauth/authorize?app_id={app.id}"
            f"&redirect_uri=http://example.com/callback"
            f"&response_type=code"
        )
        resp = api_client.post("/oauth/authorize/confirm")
        callback_url = resp["Location"]
        code = parse_qs(urlparse(callback_url).query)["code"][0]

        resp1 = api_client.post(
            "/oauth/token",
            {"grant_type": "authorization_code", "code": code,
             "app_id": app.id, "app_secret": ORIGINAL_OAUTH_SECRET,
             "redirect_uri": "http://example.com/callback"},
        )
        assert json.loads(resp1.content)["code"] == 0

        resp2 = api_client.post(
            "/oauth/token",
            {"grant_type": "authorization_code", "code": code,
             "app_id": app.id, "app_secret": ORIGINAL_OAUTH_SECRET,
             "redirect_uri": "http://example.com/callback"},
        )
        data2 = json.loads(resp2.content)
        assert data2["code"] < 0