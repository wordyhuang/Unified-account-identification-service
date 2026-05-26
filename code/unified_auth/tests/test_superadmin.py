import json
import pytest
from apps.accounts.models import Tenant


pytestmark = pytest.mark.django_db


class TestSuperadminGlobalStats:
    """TC-SUPER-001: 全局统计"""

    def test_global_stats(self, api_client, superadmin_headers, tenant_default, staff_user):
        """TC-SUPER-001: 全局统计"""
        resp = api_client.get("/api/v1/superadmin/global-stats", **superadmin_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "total_tenants" in data["data"]
        assert "total_users" in data["data"]
        assert "total_apps" in data["data"]


class TestSuperadminTenants:
    """TC-SUPER-002~007: 租户管理"""

    def test_tenant_list(self, api_client, superadmin_headers, tenant_default, tenant_b):
        """TC-SUPER-002: 租户列表"""
        resp = api_client.get("/api/v1/superadmin/tenants", **superadmin_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "tenants" in data["data"]
        assert data["data"]["total"] >= 2

    def test_create_tenant(self, api_client, superadmin_headers):
        """TC-SUPER-003: 创建租户"""
        resp = api_client.post(
            "/api/v1/superadmin/tenants",
            {"name": "新企业", "slug": "newco"},
            content_type="application/json",
            **superadmin_headers,
        )
        data = json.loads(resp.content)
        assert resp.status_code == 201
        assert data["data"]["name"] == "新企业"

    def test_create_tenant_duplicate_slug(self, api_client, superadmin_headers, tenant_default):
        """TC-SUPER-004: 创建租户 — slug 重复"""
        resp = api_client.post(
            "/api/v1/superadmin/tenants",
            {"name": "重复", "slug": "default"},
            content_type="application/json",
            **superadmin_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_tenant_detail(self, api_client, superadmin_headers, tenant_default):
        """TC-SUPER-005: 租户详情"""
        resp = api_client.get(
            f"/api/v1/superadmin/tenants/{tenant_default.id}",
            **superadmin_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["name"] == tenant_default.name

    def test_update_tenant(self, api_client, superadmin_headers, tenant_default):
        """TC-SUPER-006: 修改租户"""
        resp = api_client.put(
            f"/api/v1/superadmin/tenants/{tenant_default.id}",
            {"name": "已更新企业名"},
            content_type="application/json",
            **superadmin_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

        tenant_default.refresh_from_db()
        assert tenant_default.name == "已更新企业名"

    def test_delete_tenant(self, api_client, superadmin_headers):
        """TC-SUPER-007: 删除租户"""
        from apps.accounts.models import Tenant
        temp_tenant = Tenant.objects.create(name="临时租户", slug="temp")
        resp = api_client.delete(
            f"/api/v1/superadmin/tenants/{temp_tenant.id}",
            **superadmin_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0


class TestSuperadminImpersonate:
    """TC-SUPER-008~011: 模拟租户"""

    def test_impersonate(self, api_client, superadmin_headers, tenant_default):
        """TC-SUPER-008: 模拟进入租户"""
        resp = api_client.post(
            f"/api/v1/superadmin/impersonate/{tenant_default.id}",
            **superadmin_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["impersonated"] is True
        assert data["data"]["tenant_id"] == tenant_default.id

    def test_impersonate_access_admin_api(self, api_client, impersonate_headers):
        """TC-SUPER-009: 模拟模式下访问企业管理员 API"""
        resp = api_client.get("/api/v1/admin/users", **impersonate_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "users" in data["data"]

    def test_impersonate_cannot_access_superadmin(self, api_client, impersonate_headers):
        """TC-SUPER-010: 模拟模式下禁止访问超级管理员 API"""
        resp = api_client.get("/api/v1/superadmin/tenants", **impersonate_headers)
        assert resp.status_code == 403

    def test_impersonate_exit(self, api_client, impersonate_headers):
        """TC-SUPER-011: 退出模拟模式"""
        resp = api_client.post(
            "/api/v1/superadmin/impersonate/exit",
            **impersonate_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["impersonated"] is False


class TestSuperadminAuditLogs:
    """TC-SUPER-012: 全局审计日志"""

    def test_global_audit_logs(self, api_client, superadmin_headers, audit_logs):
        """TC-SUPER-012: 全局审计日志"""
        resp = api_client.get(
            "/api/v1/superadmin/audit-logs?page=1&page_size=20",
            **superadmin_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "logs" in data["data"]


class TestSuperadminStats:
    """TC-SUPER-013~019: 超级管理员统计报表"""

    def test_global_api_stats(self, api_client, superadmin_headers):
        """TC-SUPER-013: 全局 API 调用统计"""
        resp = api_client.get("/api/v1/superadmin/api-stats?days=7", **superadmin_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_tenant_growth(self, api_client, superadmin_headers):
        """TC-SUPER-014: 租户增长趋势"""
        resp = api_client.get("/api/v1/superadmin/stats/tenant-growth?days=30", **superadmin_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_tenant_activity_ranking(self, api_client, superadmin_headers, tenant_default):
        """TC-SUPER-015: 租户活跃度排行"""
        resp = api_client.get("/api/v1/superadmin/stats/tenant-activity-ranking", **superadmin_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_global_user_growth(self, api_client, superadmin_headers):
        """TC-SUPER-016: 全局用户增长趋势"""
        resp = api_client.get("/api/v1/superadmin/stats/global-user-growth?days=30", **superadmin_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_global_login_trend(self, api_client, superadmin_headers, audit_logs):
        """TC-SUPER-017: 全局登录趋势"""
        resp = api_client.get("/api/v1/superadmin/stats/global-login-trend?days=7", **superadmin_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_global_login_distribution(self, api_client, superadmin_headers, audit_logs):
        """TC-SUPER-018: 全局登录分布"""
        resp = api_client.get("/api/v1/superadmin/stats/global-login-distribution", **superadmin_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_app_call_ranking(self, api_client, superadmin_headers):
        """TC-SUPER-019: 应用调用排行"""
        resp = api_client.get("/api/v1/superadmin/stats/app-call-ranking", **superadmin_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0


class TestSuperadminApiAuth:
    """TC-SUPER-020~021: 超级管理员 API 权限"""

    def test_admin_token_access_superadmin(self, api_client, staff_auth_headers):
        """TC-SUPER-020: 企业管理员 Token 访问超级管理员 API"""
        resp = api_client.get("/api/v1/superadmin/tenants", **staff_auth_headers)
        assert resp.status_code == 403

    def test_superadmin_api_no_token(self, api_client):
        """TC-SUPER-021: 超级管理员 API — 无 Token"""
        resp = api_client.get("/api/v1/superadmin/tenants")
        assert resp.status_code == 401