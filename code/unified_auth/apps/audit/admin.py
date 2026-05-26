from django.contrib import admin
from .models import AuditLog
from apps.users.admin import TenantFilteredAdminMixin


@admin.register(AuditLog)
class AuditLogAdmin(TenantFilteredAdminMixin, admin.ModelAdmin):
    list_display = ("actor_name", "action", "resource_type", "resource_id", "created_at")
    list_filter = ("action", "resource_type", "created_at")
    search_fields = ("actor_name",)
    readonly_fields = list_display + ("detail", "ip_address", "user_agent")
