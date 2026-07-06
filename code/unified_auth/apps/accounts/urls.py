from django.urls import path
from . import views

urlpatterns = [
    path("login", views.login, name="auth-login"),
    path("sms/send", views.sms_send, name="auth-sms-send"),
    path("sms/verify", views.sms_verify, name="auth-sms-verify"),
    path("sms/login", views.sms_login, name="auth-sms-login"),
    path("social/login", views.social_login, name="auth-social-login"),
    path("token/refresh", views.refresh, name="auth-refresh"),
    path("logout", views.logout, name="auth-logout"),
    path("me", views.userinfo, name="auth-me"),
    path("me/password", views.change_password, name="auth-change-password"),
    path("me/profile", views.profile, name="auth-profile"),
]
