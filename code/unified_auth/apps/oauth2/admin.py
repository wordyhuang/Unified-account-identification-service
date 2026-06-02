from django.contrib import admin
from .models import AuthCode


@admin.register(AuthCode)
class AuthCodeAdmin(admin.ModelAdmin):
    list_display = ("code_short", "app", "user", "is_used", "expires_at", "created_at")
    list_filter = ("is_used", "app")
    readonly_fields = ("code", "app", "user", "redirect_uri", "state", "expires_at", "is_used", "created_at")

    def code_short(self, obj):
        return obj.code[:20] + "..."
    code_short.short_description = "授权码"