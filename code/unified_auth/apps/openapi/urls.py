from django.urls import path
from . import views

urlpatterns = [
    path("verify_token", views.verify_token, name="open-verify-token"),
    path("users", views.users_view, name="open-users"),
    path("users/<int:user_id>", views.user_detail_view, name="open-user-detail"),
    path("users/<int:user_id>/status", views.update_user_status, name="open-update-user-status"),
    path("check_permission", views.check_permission, name="open-check-permission"),
]
