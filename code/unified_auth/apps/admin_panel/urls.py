from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    path("stats", views.stats, name="admin-stats"),
    path("stats/login-trend", views.login_trend_view, name="admin-login-trend"),
    path("stats/login-distribution", views.login_distribution_view, name="admin-login-distribution"),
    path("stats/user-growth", views.user_growth_view, name="admin-user-growth"),
    path("stats/user-type-distribution", views.user_type_distribution_view, name="admin-user-type-distribution"),
    path("stats/active-users", views.active_users_view, name="admin-active-users"),
    path("recent-activities", views.recent_activities, name="admin-recent-activities"),
    path("users", views.users_view, name="admin-users"),
    path("users/<int:user_id>", views.user_detail_view, name="admin-user-detail"),
    path("users/<int:user_id>/status", views.user_status_view, name="admin-user-status"),
    path("users/<int:user_id>/reset-password", views.user_reset_password_view, name="admin-user-reset-password"),
    path("users/<int:user_id>/roles", views.user_roles_view, name="admin-user-roles"),
    path("users/<int:user_id>/profile", views.user_profile_view, name="admin-user-profile"),
    path("users/<int:user_id>/tags", views.user_tags_set_view, name="admin-user-tags-set"),
    path("login", views.admin_login_view, name="admin-login"),
    path("login-test", views.user_login_test_view, name="admin-login-test"),
    path("users/batch-status", views.user_batch_status_view, name="admin-user-batch-status"),
    path("users/batch-user-type", views.user_batch_user_type_view, name="admin-user-batch-user-type"),
    path("users/batch-delete", views.user_batch_delete_view, name="admin-user-batch-delete"),
    path("users/export", views.users_export_view, name="admin-users-export"),
    path("users/import", views.users_import_view, name="admin-users-import"),
    path("applications", views.apps_view, name="admin-apps"),
    path("applications/<int:app_id>", views.app_detail_view, name="admin-app-detail"),
    path("applications/<int:app_id>/status", views.app_status_view, name="admin-app-status"),
    path("applications/<int:app_id>/secret", views.app_secret_view, name="admin-app-secret"),
    path("applications/<int:app_id>/regenerate-secret", views.app_regenerate_secret_view, name="admin-app-regenerate-secret"),
    path("applications/<int:app_id>/roles", views.app_roles_view, name="admin-app-roles"),
    path("applications/<int:app_id>/permissions", views.app_permissions_view, name="admin-app-permissions"),
    path("applications/<int:app_id>/api-stats", views.app_api_stats_view, name="admin-app-api-stats"),
    path("permissions", views.permissions_view, name="admin-permissions"),
    path("roles", views.roles_view, name="admin-roles"),
    path("roles/<int:role_id>", views.role_detail_view, name="admin-role-detail"),
    path("roles/<int:role_id>/copy", views.role_copy_view, name="admin-role-copy"),
    path("departments", views.departments_view, name="admin-departments"),
    path("departments/<int:dept_id>", views.department_detail_view, name="admin-department-detail"),
    path("audit-logs", views.audit_logs_view, name="admin-audit-logs"),
    path("audit-logs/export", views.audit_logs_export_view, name="admin-audit-logs-export"),
    path("tenant-sms-config", views.tenant_sms_config_view, name="admin-tenant-sms-config"),
    path("tenant-sms-config/test", views.tenant_sms_config_test_view, name="admin-tenant-sms-config-test"),
]

superadmin_urlpatterns = [
    path("global-stats", views.superadmin_global_stats, name="superadmin-global-stats"),
    path("platform-config", views.superadmin_platform_config, name="superadmin-platform-config"),
    path("tenants", views.superadmin_tenants_view, name="superadmin-tenants"),
    path("tenants/<int:tenant_id>", views.superadmin_tenant_detail_view, name="superadmin-tenant-detail"),
    path("impersonate/<int:tenant_id>", views.superadmin_impersonate, name="superadmin-impersonate"),
    path("impersonate/exit", views.superadmin_impersonate_exit, name="superadmin-impersonate-exit"),
    path("audit-logs", views.superadmin_audit_logs_view, name="superadmin-audit-logs"),
    path("audit-logs/export", views.audit_logs_export_view, name="superadmin-audit-logs-export"),
    path("api-stats", views.superadmin_api_stats_view, name="superadmin-api-stats"),
    path("stats/tenant-growth", views.superadmin_tenant_growth_view, name="superadmin-tenant-growth"),
    path("stats/tenant-activity-ranking", views.superadmin_tenant_activity_ranking_view, name="superadmin-tenant-activity-ranking"),
    path("stats/global-user-growth", views.superadmin_global_user_growth_view, name="superadmin-global-user-growth"),
    path("stats/global-login-trend", views.superadmin_global_login_trend_view, name="superadmin-global-login-trend"),
    path("stats/global-login-distribution", views.superadmin_global_login_distribution_view, name="superadmin-global-login-distribution"),
    path("stats/app-call-ranking", views.superadmin_app_call_ranking_view, name="superadmin-app-call-ranking"),
]

# 重新定义 urlpatterns，让 admin 路由和 superadmin 路由可以通过命名空间区分
# 这是一个临时方案，实际使用时需要根据引入方式区分
# 当使用 include('apps.admin_panel.urls', namespace='superadmin') 时，需要改变 urlpatterns
# 但为了兼容两者，我们保持不变，实际使用时会有问题
# 更好的方法是创建两个单独的 urls 模块，或者在 config/urls.py 中直接定义路由

