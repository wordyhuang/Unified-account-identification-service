from django.contrib import admin
from .models import Tenant, SocialAccount


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "status", "created_at")
    search_fields = ("name", "slug")
    list_filter = ("status",)


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "open_id", "created_at")
    search_fields = ("open_id", "user__username")
    list_filter = ("provider",)
