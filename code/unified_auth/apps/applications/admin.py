from django.contrib import admin
from .models import Application
from apps.users.admin import TenantFilteredAdminMixin


@admin.register(Application)
class ApplicationAdmin(TenantFilteredAdminMixin, admin.ModelAdmin):
    list_display = ("name", "app_key", "tenant", "status", "created_at")
    search_fields = ("name", "app_key")
    list_filter = ("status", "tenant")
    readonly_fields = ("app_key", "app_secret")
