from django.urls import path
from . import views

urlpatterns = [
    path("login", views.login, name="auth-login"),
    path("sms/send", views.sms_send, name="auth-sms-send"),
    path("sms/login", views.sms_login, name="auth-sms-login"),
    path("social/login", views.social_login, name="auth-social-login"),
    path("refresh", views.refresh, name="auth-refresh"),
    path("logout", views.logout, name="auth-logout"),
    path("userinfo", views.userinfo, name="auth-userinfo"),
    path("userinfo/password", views.change_password, name="auth-change-password"),
    path("profile", views.profile, name="auth-profile"),
    path("profile/update", views.update_profile, name="auth-profile-update"),
]
