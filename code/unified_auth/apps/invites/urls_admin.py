from django.urls import path
from . import admin_views

# 管理端 API：挂在 /api/v1/admin/ 下（与 apps.tags.urls 同样的 include 方式）
urlpatterns = [
    path("invite-codes", admin_views.invite_codes_view, name="admin-invite-codes"),
    path("invite-codes/<int:code_id>", admin_views.invite_code_detail_view, name="admin-invite-code-detail"),
    path("profile-completion-codes", admin_views.completion_codes_view, name="admin-completion-codes"),
    path("profile-completion-codes/<int:code_id>", admin_views.completion_code_detail_view, name="admin-completion-code-detail"),
    path("profile-completion-fields", admin_views.completion_fields_view, name="admin-completion-fields"),
    path("invite-brand", admin_views.invite_brand_view, name="admin-invite-brand"),
    path("invite-fields", admin_views.invite_fields_registry_view, name="admin-invite-fields"),
    path("invite-appearance/preview", admin_views.appearance_preview_view, name="admin-invite-appearance-preview"),
]
