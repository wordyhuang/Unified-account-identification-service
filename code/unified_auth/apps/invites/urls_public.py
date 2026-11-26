from django.urls import path
from . import views

# 公开 API：挂在 /api/v1/public/ 下，无需登录（TokenAuthenticationMiddleware 跳过）
urlpatterns = [
    path("invite/<str:code>", views.invite_info, name="public-invite-info"),
    path("invite/<str:code>/register", views.invite_register, name="public-invite-register"),
    path("profile-completion/<str:code>", views.completion_info, name="public-completion-info"),
    path("profile-completion/<str:code>/verify", views.completion_send_sms, name="public-completion-verify"),
    path("profile-completion/<str:code>/login", views.completion_login, name="public-completion-login"),
    path("profile-completion/<str:code>/submit", views.completion_submit, name="public-completion-submit"),
]
