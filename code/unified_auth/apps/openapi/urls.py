from django.urls import path
from . import views

urlpatterns = [
    path("verify_token", views.verify_token, name="open-verify-token"),
    path("users", views.users_view, name="open-users"),
    path("users/<int:user_id>", views.user_detail_view, name="open-user-detail"),
    path("users/<int:user_id>/status", views.update_user_status, name="open-update-user-status"),
    path("check_permission", views.check_permission, name="open-check-permission"),
    path("user/profile/by_token", views.user_profile_by_token, name="open-user-profile-by-token"),
    # 微信小程序辅助接口
    path("wechat/access_token", views.get_access_token, name="open-wechat-access-token"),
    path("wechat/get_phone_number", views.get_phone_number, name="open-wechat-phone"),
]
