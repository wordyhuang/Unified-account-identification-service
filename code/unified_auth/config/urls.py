from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from django.http import HttpResponseRedirect
from apps.admin_panel import views as admin_views


def admin_panel_view(request):
    return render(request, "admin_panel/index.html")


def favicon_view(request):
    return HttpResponseRedirect("/static/admin_panel/favicon.svg")


urlpatterns = [
    path('favicon.ico', favicon_view),
    path('admin/', admin.site.urls),
    path('admin-panel/', admin_panel_view, name="admin-panel"),
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/open/', include('apps.openapi.urls')),
    path('api/v1/admin/', include('apps.admin_panel.urls')),
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
]
