from django.urls import path
from . import views

urlpatterns = [
    path("token", views.app_token, name="open-app-token"),
    path("token/verify", views.verify_token, name="open-verify-token"),
    path("users", views.users_view, name="open-users"),
    path("users/<int:user_id>", views.user_detail_view, name="open-user-detail"),
    path("users/<int:user_id>/status", views.update_user_status, name="open-update-user-status"),
    path("permissions/check", views.check_permission, name="open-check-permission"),
    path("users/me/profile", views.user_profile_by_token, name="open-user-profile-by-token"),
    path("users/<int:user_id>/profile", views.user_profile_by_app, name="open-user-profile-by-app"),
    # 微信小程序辅助接口
    path("wechat/access_token", views.get_access_token, name="open-wechat-access-token"),
    path("wechat/phone", views.get_phone_number, name="open-wechat-phone"),
]
