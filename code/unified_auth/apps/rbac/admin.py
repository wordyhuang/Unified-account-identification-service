from django.contrib import admin
from .models import ApiPermission, Role, AppRoleBinding
from apps.users.admin import TenantFilteredAdminMixin


@admin.register(ApiPermission)
class ApiPermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "method", "path", "category")
    list_filter = ("category", "method")
    search_fields = ("code", "name")


@admin.register(Role)
class RoleAdmin(TenantFilteredAdminMixin, admin.ModelAdmin):
    list_display = ("name", "code", "tenant", "created_at")
    filter_horizontal = ("permissions",)


@admin.register(AppRoleBinding)
class AppRoleBindingAdmin(admin.ModelAdmin):
    list_display = ("app", "permission", "created_at")
    list_filter = ("app",)
