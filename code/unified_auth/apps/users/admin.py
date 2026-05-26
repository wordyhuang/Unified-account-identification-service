from django.contrib import admin
from apps.accounts.models import User


class TenantFilteredAdminMixin:
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'tenant_id'):
            return qs.filter(tenant_id=request.user.tenant_id)
        return qs

    def save_model(self, request, obj, form, change):
        if not change and hasattr(request.user, 'tenant_id'):
            obj.tenant_id = request.user.tenant_id
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "tenant" and not request.user.is_superuser:
            kwargs["queryset"] = db_field.remote_field.model.objects.filter(
                id=request.user.tenant_id
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(User)
class UserAdmin(TenantFilteredAdminMixin, admin.ModelAdmin):
    list_display = ("username", "tenant", "user_type", "email", "phone", "is_staff", "status", "last_login_at")
    list_filter = ("user_type", "status", "tenant")
    search_fields = ("username", "email", "phone")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("基本信息", {"fields": ("tenant", "user_type", "nickname", "email", "phone", "avatar", "department")}),
        ("状态", {"fields": ("status", "is_staff", "is_superuser", "last_login_at")}),
    )
