import json
import io
import csv
import pytest
from apps.accounts.models import User, Department
from apps.applications.models import Application
from apps.rbac.models import Role, RolePermission, ApiPermission


pytestmark = pytest.mark.django_db


class TestAdminDashboard:
    """TC-ADMIN-001~002: 仪表盘"""

    def test_stats(self, api_client, staff_user, staff_auth_headers, app):
        """TC-ADMIN-001: 仪表盘统计"""
        resp = api_client.get("/api/v1/admin/stats", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "total_users" in data["data"]
        assert "active_users" in data["data"]
        assert "total_apps" in data["data"]
        assert "active_apps" in data["data"]
        assert "today_new_users" in data["data"]
        assert "total_roles" in data["data"]

    def test_recent_activities(self, api_client, staff_auth_headers, audit_logs):
        """TC-ADMIN-002: 最近动态"""
        resp = api_client.get("/api/v1/admin/recent-activities", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "activities" in data["data"]


class TestAdminUsers:
    """TC-ADMIN-003~016: 用户管理"""

    def test_user_list_pagination(self, api_client, staff_auth_headers, staff_user, normal_user, external_user):
        """TC-ADMIN-003: 用户列表 — 分页"""
        resp = api_client.get("/api/v1/admin/users?page=1&page_size=20", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "users" in data["data"]
        assert "total" in data["data"]
        assert data["data"]["page"] == 1

    def test_user_list_filter_staff(self, api_client, staff_auth_headers, staff_user, normal_user, external_user):
        """TC-ADMIN-004: 用户列表 — 筛选租户管理员"""
        resp = api_client.get("/api/v1/admin/users?page=1&page_size=20&is_staff=1", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["total"] == 1
        assert data["data"]["users"][0]["is_staff"] is True

    def test_user_list_filter_regular(self, api_client, staff_auth_headers, staff_user, normal_user, external_user):
        """TC-ADMIN-004B: 用户列表 — 筛选普通用户"""
        resp = api_client.get("/api/v1/admin/users?page=1&page_size=20&is_staff=0", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["total"] == 2
        for u in data["data"]["users"]:
            assert u["is_staff"] is False

    def test_create_user_success(self, api_client, staff_auth_headers):
        """TC-ADMIN-005: 创建用户 — 成功"""
        resp = api_client.post(
            "/api/v1/admin/users",
            {"username": "admin_new_user", "password": "test1234", "user_type": "internal"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert resp.status_code == 201
        assert data["data"]["username"] == "admin_new_user"

    def test_create_user_duplicate(self, api_client, staff_auth_headers, staff_user):
        """TC-ADMIN-006: 创建用户 — 用户名重复"""
        resp = api_client.post(
            "/api/v1/admin/users",
            {"username": "staff_user", "password": "test1234", "user_type": "internal"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_get_user_detail(self, api_client, staff_auth_headers, staff_user):
        """TC-ADMIN-007: 获取用户详情"""
        resp = api_client.get(f"/api/v1/admin/users/{staff_user.id}", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["username"] == "staff_user"

    def test_get_user_detail_other_tenant(self, api_client, staff_auth_headers, user_b):
        """TC-ADMIN-008: 获取用户详情 — 其他租户用户（数据隔离）"""
        resp = api_client.get(f"/api/v1/admin/users/{user_b.id}", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_update_user(self, api_client, staff_auth_headers, staff_user):
        """TC-ADMIN-009: 修改用户信息"""
        resp = api_client.put(
            f"/api/v1/admin/users/{staff_user.id}",
            {"nickname": "管理员改名"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

        staff_user.refresh_from_db()
        assert staff_user.nickname == "管理员改名"

    def test_toggle_user_status(self, api_client, staff_auth_headers, normal_user):
        """TC-ADMIN-010: 启用/禁用用户"""
        resp = api_client.patch(
            f"/api/v1/admin/users/{normal_user.id}/status",
            {"status": 0},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["status"] == 0

        resp = api_client.patch(
            f"/api/v1/admin/users/{normal_user.id}/status",
            {"status": 1},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["status"] == 1

    def test_reset_password(self, api_client, staff_auth_headers, normal_user):
        """TC-ADMIN-011: 重置用户密码"""
        resp = api_client.post(
            f"/api/v1/admin/users/{normal_user.id}/reset-password",
            {"new_password": "newpass5678"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

        normal_user.refresh_from_db()
        assert normal_user.check_password("newpass5678")

    def test_delete_user(self, api_client, staff_auth_headers, tenant_default):
        """TC-ADMIN-012: 删除用户"""
        from apps.accounts.models import User
        temp_user = User.objects.create_user(
            tenant=tenant_default,
            username="delete_me",
            password="test1234",
            user_type="internal",
        )
        resp = api_client.delete(
            f"/api/v1/admin/users/{temp_user.id}",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_batch_status(self, api_client, staff_auth_headers, normal_user, external_user):
        """TC-ADMIN-013: 批量启用/禁用用户"""
        resp = api_client.post(
            "/api/v1/admin/users/batch-status",
            {"user_ids": [normal_user.id, external_user.id], "status": 0},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["updated_count"] == 2

    def test_batch_delete(self, api_client, staff_auth_headers, tenant_default):
        """TC-ADMIN-014: 批量删除用户"""
        from apps.accounts.models import User
        u1 = User.objects.create_user(tenant=tenant_default, username="batch_del_1", password="test1234", user_type="internal")
        u2 = User.objects.create_user(tenant=tenant_default, username="batch_del_2", password="test1234", user_type="internal")
        resp = api_client.post(
            "/api/v1/admin/users/batch-delete",
            {"user_ids": [u1.id, u2.id]},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_export_users_csv(self, api_client, staff_auth_headers):
        """TC-ADMIN-015: 导出用户 CSV"""
        resp = api_client.get("/api/v1/admin/users/export", **staff_auth_headers)
        assert resp.status_code == 200
        assert resp.get("Content-Type", "").startswith("text/csv")

    def test_import_users(self, api_client, staff_auth_headers):
        """TC-ADMIN-016: 导入用户"""
        csv_content = "用户名,用户类型,密码\nimport_user1,internal,pass1234\nimport_user2,internal,pass5678"
        resp = api_client.post(
            "/api/v1/admin/users/import",
            {"csv_content": csv_content},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["created"] == 2


class TestAdminApplications:
    """TC-ADMIN-017~024: 应用管理"""

    def test_app_list(self, api_client, staff_auth_headers, app):
        """TC-ADMIN-017: 应用列表"""
        resp = api_client.get("/api/v1/admin/applications", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "apps" in data["data"]

    def test_create_app(self, api_client, staff_auth_headers):
        """TC-ADMIN-018: 创建应用"""
        resp = api_client.post(
            "/api/v1/admin/applications",
            {"name": "新应用", "callback_urls": ["https://example.com/callback"],
             "default_access_user_types": ["internal"]},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert resp.status_code == 201
        assert data["data"]["name"] == "新应用"
        assert "app_key" in data["data"]

    def test_get_app_detail(self, api_client, staff_auth_headers, app):
        """TC-ADMIN-019: 获取应用详情"""
        resp = api_client.get(f"/api/v1/admin/applications/{app.id}", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["name"] == app.name
        assert "permission_ids" in data["data"]
        assert isinstance(data["data"]["permission_ids"], list)

    def test_get_app_detail_with_permissions(self, api_client, staff_auth_headers, app_with_all_perms):
        """TC-ADMIN-019: 获取应用详情（带权限）"""
        resp = api_client.get(f"/api/v1/admin/applications/{app_with_all_perms.id}", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert len(data["data"]["permission_ids"]) > 0

    def test_update_app(self, api_client, staff_auth_headers, app):
        """TC-ADMIN-020: 修改应用"""
        resp = api_client.put(
            f"/api/v1/admin/applications/{app.id}",
            {"name": "已更新应用名"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_update_app_with_permissions(self, api_client, staff_auth_headers, app, permissions):
        """TC-ADMIN-020: 修改应用（带权限更新）"""
        perm_ids = [p.id for p in permissions[:3]]
        resp = api_client.put(
            f"/api/v1/admin/applications/{app.id}",
            {"name": "更新应用名", "permission_ids": perm_ids},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["permission_ids"] == perm_ids

        from apps.rbac.models import AppRoleBinding
        bindings = AppRoleBinding.objects.filter(app=app)
        assert len(bindings) == 3

    def test_toggle_app_status(self, api_client, staff_auth_headers, app):
        """TC-ADMIN-021: 启用/禁用应用"""
        resp = api_client.patch(
            f"/api/v1/admin/applications/{app.id}/status",
            {"status": False},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["status"] is False

        resp = api_client.patch(
            f"/api/v1/admin/applications/{app.id}/status",
            {"status": True},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["status"] is True

    def test_regenerate_secret(self, api_client, staff_auth_headers, app):
        """TC-ADMIN-022: 重新生成应用密钥"""
        resp = api_client.post(
            f"/api/v1/admin/applications/{app.id}/regenerate-secret",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "app_secret_raw" in data["data"]

    def test_app_permissions(self, api_client, staff_auth_headers, app, permissions):
        """TC-ADMIN-023: 应用权限配置"""
        resp = api_client.get(
            f"/api/v1/admin/applications/{app.id}/permissions",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_app_api_stats(self, api_client, staff_auth_headers, app):
        """TC-ADMIN-024: 应用 API 调用统计"""
        resp = api_client.get(
            f"/api/v1/admin/applications/{app.id}/api-stats?days=7",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0


class TestAdminRoles:
    """TC-ADMIN-025~033: 角色权限"""

    def test_permissions_list(self, api_client, staff_auth_headers, permissions):
        """TC-ADMIN-025: 权限列表"""
        resp = api_client.get("/api/v1/admin/permissions", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert len(data["data"]["permissions"]) > 0

    def test_role_list(self, api_client, staff_auth_headers, role_with_all_perms):
        """TC-ADMIN-026: 角色列表"""
        resp = api_client.get("/api/v1/admin/roles", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "roles" in data["data"]

    def test_create_role(self, api_client, staff_auth_headers, permissions):
        """TC-ADMIN-027: 创建角色"""
        perm_ids = [p.id for p in permissions[:3]]
        resp = api_client.post(
            "/api/v1/admin/roles",
            {"name": "测试角色", "code": "test_role", "permission_ids": perm_ids},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert resp.status_code == 201
        assert data["data"]["name"] == "测试角色"

    def test_create_role_duplicate_code(self, api_client, staff_auth_headers, role_with_all_perms):
        """TC-ADMIN-028: 创建角色 — code 重复"""
        resp = api_client.post(
            "/api/v1/admin/roles",
            {"name": "重复", "code": "admin", "permission_ids": []},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] < 0

    def test_get_role_detail(self, api_client, staff_auth_headers, role_with_all_perms):
        """TC-ADMIN-029: 获取角色详情"""
        resp = api_client.get(
            f"/api/v1/admin/roles/{role_with_all_perms.id}",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert data["data"]["name"] == role_with_all_perms.name

    def test_update_role(self, api_client, staff_auth_headers, role_without_perms, permissions):
        """TC-ADMIN-030: 修改角色"""
        perm_ids = [p.id for p in permissions[:2]]
        resp = api_client.put(
            f"/api/v1/admin/roles/{role_without_perms.id}",
            {"name": "已更新角色", "permission_ids": perm_ids},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_copy_role(self, api_client, staff_auth_headers, role_with_all_perms):
        """TC-ADMIN-031: 复制角色"""
        resp = api_client.post(
            f"/api/v1/admin/roles/{role_with_all_perms.id}/copy",
            {"name": "角色副本", "code": "role_copy"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert resp.status_code == 201
        assert data["data"]["name"] == "角色副本"


class TestAdminAuditLogs:
    """TC-ADMIN-032~033: 审计日志"""

    def test_audit_log_list(self, api_client, staff_auth_headers, audit_logs):
        """TC-ADMIN-032: 审计日志列表"""
        resp = api_client.get(
            "/api/v1/admin/audit-logs?page=1&page_size=20",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "logs" in data["data"]
        assert data["data"]["total"] >= 20

    def test_audit_log_export(self, api_client, staff_auth_headers, audit_logs):
        """TC-ADMIN-033: 审计日志导出"""
        resp = api_client.get(
            "/api/v1/admin/audit-logs/export",
            **staff_auth_headers,
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.get("Content-Type", "")


class TestAdminDepartments:
    """TC-ADMIN-034~036: 部门管理"""

    def test_create_department(self, api_client, staff_auth_headers):
        """TC-ADMIN-034: 部门 — 创建"""
        resp = api_client.post(
            "/api/v1/admin/departments",
            {"name": "研发部", "parent_id": None, "sort_order": 1},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert resp.status_code == 201

    def test_department_tree(self, api_client, staff_auth_headers, department):
        """TC-ADMIN-035: 部门 — 树形列表"""
        resp = api_client.get("/api/v1/admin/departments", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0
        assert "departments" in data["data"]

    def test_update_department(self, api_client, staff_auth_headers, department):
        """TC-ADMIN-036: 部门 — 编辑"""
        resp = api_client.put(
            f"/api/v1/admin/departments/{department.id}",
            {"name": "技术部"},
            content_type="application/json",
            **staff_auth_headers,
        )
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_delete_department_with_children(self, api_client, staff_auth_headers, department):
        """TC-ADMIN-036: 部门 — 删除（有子节点时）"""
        from apps.accounts.models import Department
        Department.objects.create(
            tenant_id=department.tenant_id,
            name="子部门",
            parent=department,
        )
        resp = api_client.delete(
            f"/api/v1/admin/departments/{department.id}",
            **staff_auth_headers,
        )
        assert resp.status_code == 400


class TestAdminStats:
    """TC-ADMIN-037~041: 统计报表"""

    def test_login_trend(self, api_client, staff_auth_headers, audit_logs):
        """TC-ADMIN-037: 登录趋势图"""
        resp = api_client.get("/api/v1/admin/stats/login-trend?days=7", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_login_distribution(self, api_client, staff_auth_headers, audit_logs):
        """TC-ADMIN-038: 登录方式分布"""
        resp = api_client.get("/api/v1/admin/stats/login-distribution", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_user_growth(self, api_client, staff_auth_headers):
        """TC-ADMIN-039: 用户增长趋势"""
        resp = api_client.get("/api/v1/admin/stats/user-growth?days=30", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_user_type_distribution(self, api_client, staff_auth_headers):
        """TC-ADMIN-040: 用户类型分布"""
        resp = api_client.get("/api/v1/admin/stats/user-type-distribution", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0

    def test_active_users(self, api_client, staff_auth_headers):
        """TC-ADMIN-041: 活跃用户统计"""
        resp = api_client.get("/api/v1/admin/stats/active-users?days=30", **staff_auth_headers)
        data = json.loads(resp.content)
        assert data["code"] == 0


class TestAdminApiAuth:
    """TC-ADMIN-042~043: 管理 API 权限"""

    def test_admin_api_no_token(self, api_client):
        """TC-ADMIN-042: 管理 API — 无 Token 访问"""
        resp = api_client.get("/api/v1/admin/stats")
        assert resp.status_code == 401

    def test_normal_user_access_admin(self, api_client, normal_auth_headers):
        """TC-ADMIN-043: 管理 API — 普通用户访问（需 is_staff）"""
        resp = api_client.get("/api/v1/admin/stats", **normal_auth_headers)
        assert resp.status_code == 403