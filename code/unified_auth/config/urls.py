from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from django.http import HttpResponseRedirect
from apps.admin_panel import views as admin_views


def admin_panel_index(request):
    return HttpResponseRedirect("/admin-panel/dashboard/")


def admin_panel_page(request, template):
    """管理后台页面视图：仅渲染模板，认证守卫在前端（common.js requireAuth）"""
    return render(request, "admin_panel/{}.html".format(template))


# 管理后台多页路由：页面路径 → 模板名（不含扩展名）
ADMIN_PANEL_ROUTES = [
    ("login/", "login", "admin-panel-login"),
    ("dashboard/", "dashboard", "admin-panel-dashboard"),
    ("users/", "users", "admin-panel-users"),
    ("applications/", "applications", "admin-panel-applications"),
    ("roles/", "roles", "admin-panel-roles"),
    ("departments/", "departments", "admin-panel-departments"),
    ("tags/", "tags", "admin-panel-tags"),
    ("audit/", "audit", "admin-panel-audit"),
    ("sms-config/", "sms_config", "admin-panel-sms-config"),
    ("login-test/", "login_test", "admin-panel-login-test"),
    ("superadmin/dashboard/", "superadmin_dashboard", "admin-panel-superadmin-dashboard"),
    ("superadmin/tenants/", "superadmin_tenants", "admin-panel-superadmin-tenants"),
    ("superadmin/audit/", "superadmin_audit", "admin-panel-superadmin-audit"),
    ("superadmin/report/", "superadmin_report", "admin-panel-superadmin-report"),
    ("superadmin/api-stats/", "superadmin_api_stats", "admin-panel-superadmin-api-stats"),
    ("superadmin/config/", "superadmin_config", "admin-panel-superadmin-config"),
    ("superadmin/workdesktop-version/", "superadmin_workdesktop_version", "admin-panel-superadmin-workdesktop-version"),
]


def favicon_view(request):
    return HttpResponseRedirect("/static/admin_panel/favicon.svg")


urlpatterns = [
    path('favicon.ico', favicon_view),
    path('admin/', admin.site.urls),
    path('admin-panel/', admin_panel_index, name="admin-panel"),
] + [
    path('admin-panel/' + route, admin_panel_page, {"template": template}, name=name)
    for route, template, name in ADMIN_PANEL_ROUTES
] + [
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/open/', include('apps.openapi.urls')),
    path('oauth/', include('apps.oauth2.urls')),
    path('api/v1/admin/', include('apps.admin_panel.urls')),
    path('api/v1/admin/', include('apps.tags.urls')),
    path('api/v1/superadmin/global-stats', admin_views.superadmin_global_stats, name="superadmin-global-stats"),
    path('api/v1/superadmin/platform-config', admin_views.superadmin_platform_config, name="superadmin-platform-config"),
    path('api/v1/superadmin/tenants', admin_views.superadmin_tenants_view, name="superadmin-tenants"),
    path('api/v1/superadmin/tenants/<int:tenant_id>', admin_views.superadmin_tenant_detail_view, name="superadmin-tenant-detail"),
    path('api/v1/superadmin/impersonate/<int:tenant_id>', admin_views.superadmin_impersonate, name="superadmin-impersonate"),
    path('api/v1/superadmin/impersonate/exit', admin_views.superadmin_impersonate_exit, name="superadmin-impersonate-exit"),
    path('api/v1/superadmin/audit-logs', admin_views.superadmin_audit_logs_view, name="superadmin-audit-logs"),
    path('api/v1/superadmin/audit-logs/export', admin_views.audit_logs_export_view, name="superadmin-audit-logs-export"),
    path('api/v1/superadmin/api-stats', admin_views.superadmin_api_stats_view, name="superadmin-api-stats"),
    path('api/v1/superadmin/stats/tenant-growth', admin_views.superadmin_tenant_growth_view, name="superadmin-stats-tenant-growth"),
    path('api/v1/superadmin/stats/tenant-activity-ranking', admin_views.superadmin_tenant_activity_ranking_view, name="superadmin-stats-tenant-activity-ranking"),
    path('api/v1/superadmin/stats/global-user-growth', admin_views.superadmin_global_user_growth_view, name="superadmin-stats-global-user-growth"),
    path('api/v1/superadmin/stats/global-login-trend', admin_views.superadmin_global_login_trend_view, name="superadmin-stats-global-login-trend"),
    path('api/v1/superadmin/stats/global-login-distribution', admin_views.superadmin_global_login_distribution_view, name="superadmin-stats-global-login-distribution"),
    path('api/v1/superadmin/stats/app-call-ranking', admin_views.superadmin_app_call_ranking_view, name="superadmin-stats-app-call-ranking"),
    path('api/v1/superadmin/report/tenants', admin_views.superadmin_report_tenants, name="superadmin-report-tenants"),
    path('api/v1/superadmin/report/apps', admin_views.superadmin_report_apps, name="superadmin-report-apps"),
    path('api/v1/superadmin/report/endpoint-stats', admin_views.superadmin_report_endpoint_stats, name="superadmin-report-endpoint-stats"),
    path('api/v1/superadmin/workdesktop-version', admin_views.workdesktop_version_view, name="superadmin-workdesktop-version"),
    path('api/v1/superadmin/workdesktop-version/install', admin_views.workdesktop_version_install_view, name="superadmin-workdesktop-version-install"),
]
